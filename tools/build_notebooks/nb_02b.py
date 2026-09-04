"""Build notebooks/02b_benders.ipynb.

**Subject:** Benders / L-shaped decomposition on the two-stage capacity network.
The extensive form is the answer that must be reproduced; the L-shaped loop
reproduces it from a master that never contains a single scenario.

**The honest framing this notebook is built on.** Decomposition is *slower* here
than solving the monolithic model -- 0.59s against 0.04s at 24 scenarios, and
still slower at 200. Presenting it as a speed-up would be false and the reader
would find that out in one timing cell. What it actually buys is a bound on the
size of model you must build: the extensive form crosses the restricted
licence's ~2,000 variables at n = 100 scenarios, while the L-shaped master has
12 + n variables and each subproblem has 20, forever. And the iteration count is
flat at 15 whether n is 24 or 200, because the number of cuts needed is a
property of the first-stage geometry rather than of the scenario count.
"""
from . import common

NOTEBOOK = "02b_benders.ipynb"
TITLE = "Part 2b - Benders / L-shaped decomposition"


def cells():
    out = []

    def M(text):
        out.append(("md", text.strip("\n")))

    def C(text):
        out.append(("code", text.strip("\n")))

    # ================================ front ================================
    M(r"""
# Part 2b — Benders, and what decomposition actually buys

### It is slower. That is not the point.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/USERNAME/lithium-modelling/blob/main/notebooks/02b_benders.ipynb)

Part 2 hit a wall: the extensive form replicates the whole model once per
scenario, so it stops fitting. Progressive hedging was one way around it. This is
the other, and it is the one with a **bound** attached rather than a heuristic.

### The idea in one line

Solve a **master** holding only the first-stage decisions plus a placeholder for
what the second stage will cost. Whenever the placeholder is optimistic, add a
constraint that says so, built from the subproblem's duals.

$$\theta_k \;\ge\; Q_k(\hat c) \;+\; \beta_k^\top (c - \hat c)$$

$Q_k$ is convex in the capacity right-hand side, so that line is **exact at
$\hat c$ and an underestimate everywhere else** — it can never cut off the true
optimum. The master is therefore a relaxation, its objective is a valid lower
bound, and evaluating the real recourse at any proposed plan gives a valid upper
bound. The two meet.

### Read this before you expect a speed-up

| at n = 200 | extensive form | L-shaped |
|---|---|---|
| variables in the biggest model solved | **4,012** | master 212, subproblem 20 |
| fits the restricted licence? | **no** | yes, at any n |
| wall time | **faster** | slower, at every size tested |

**Decomposition loses on time here and wins on size.** Section 10 measures both
rather than asserting them. Gurobi is extremely good at the monolithic model at
this scale; the reason to learn this method is that the monolithic model is the
thing that stops existing.

Note what is quoted above and what is not. Variable counts are a property of the
formulation and will be identical on your machine. **Wall times are not**, so
none appear in this notebook's prose — section 10's table prints the timings from
*your* run, and they will not match mine. A tutorial that hard-codes "1.4x
faster" is wrong for most of its readers within a year.

### Why a new, smaller instance

The second stage has to be a **linear** program for the duals in that cut to
exist. Part 1's model buries capacity under binaries, vintages and lead times,
and there is no clean dual to build a cut from. Section 2 says more.
""")

    out += common.setup_section(notebook=NOTEBOOK)
    out += common.twostage_instance_section(agree=11)
    out += common.twostage_structure_section(agree=11)

    # ==================== 4. scenarios =====================================
    M(r"""
## 4. The scenario tree

Demand only, uniform on $[0.55, 1.55]$ times each region's base. Twenty-four
equally likely draws.

**The draw order is part of the definition, not an implementation detail.** One
call to the generator per region per scenario, regions in table order. Reorder
those two lines and you get a different tree from the same seed — which is
exactly the kind of thing that makes a result irreproducible for a reader on a
different machine. The seed is set and printed for the same reason.
""")

    C(r'''
import random

SEED, NK = 11, 24
LO, HI = 0.55, 1.55

rng = random.Random(SEED)
SCEN = []
for k in range(NK):
    d = {}
    for r in REGIONS:                       # region order is part of the tree
        d[r] = DEMAND_BASE[r] * (LO + (HI - LO) * rng.random())
    SCEN.append((f"k{k}", 1.0 / NK, d))

assert abs(sum(p for _, p, _ in SCEN) - 1.0) < 1e-12, "probabilities must sum to 1"
print(f"seed {SEED}, {NK} equally likely scenarios (p = {1 / NK:.4f})")
for r in REGIONS:
    lo = min(s[2][r] for s in SCEN)
    hi = max(s[2][r] for s in SCEN)
    print(f"  {r}: demand {lo:6.1f} to {hi:6.1f}   (base {DEMAND_BASE[r]:.1f})")
print(f"\npeak total demand {max(sum(s[2].values()) for s in SCEN):.1f} "
      f"against one full chain's {MAX_DELIVERABLE:.2f}")
''')

    # ==================== 5. the extensive form ============================
    M(r"""
## 5. The extensive form — the answer that must be reproduced

Everything in one model: one copy of the first stage, twenty-four copies of the
second. This is what decomposition has to match, and it is worth solving first
precisely so that the L-shaped loop has something to be checked against.

**The first stage is the same variables no matter which scenario happens** —
that is the nonanticipativity of Part 2, expressed here by simply not
subscripting `y` and `c` by `k`.

> **Predict before you run.** Two regions, and R1's demand base is 34 against
> R2's 22. Will the optimal plan open nodes in both regions, or concentrate?
""")

    C(r'''
import gurobipy as gp
from gurobipy import GRB
import time

MIPGAP = 1e-9    # far tighter than anything compared below; see section 11


# THE FUNCTION IS THE LESSON: the whole method rests on the extensive form and
# the standalone recourse LP being the SAME second stage. Writing the block out
# twice would let them drift, and a Benders loop whose subproblem differs from
# the model it is meant to reproduce converges neatly to the wrong answer.
def second_stage(m, cap, scen, suffix):
    """One scenario's recourse block. `cap` may be Gurobi vars OR fixed floats.

    Building it the same way in both cases is what makes the monolithic model
    and the standalone recourse LP the same model rather than two similar ones.
    """
    x = m.addVars(NODES, lb=0.0, name=f"x{suffix}")
    f = m.addVars(ARCS, lb=0.0, name=f"f{suffix}")
    u = m.addVars(REGIONS, lb=0.0, name=f"u{suffix}")
    link = m.addConstrs((x[n] <= cap[n] for n in NODES), name=f"cap{suffix}")
    m.addConstrs((ETA[s] * x[s, r] == f.sum(s, r, "*") for (s, r) in NODES),
                 name=f"out{suffix}")
    for i, s in enumerate(STAGES):
        if i == 0:
            continue
        prev = STAGES[i - 1]
        m.addConstrs((f.sum(prev, "*", r) == x[s, r] for r in REGIONS),
                     name=f"in_{s}{suffix}")
    m.addConstrs((f.sum(STAGES[-1], "*", r) + u[r] >= scen[2][r] for r in REGIONS),
                 name=f"dem{suffix}")
    cost = (gp.quicksum(OPC[s] * x[s, r] for (s, r) in NODES)
            + gp.quicksum(TAU[a, b] * f[s, a, b] for (s, a, b) in ARCS)
            + gp.quicksum(PEN * u[r] for r in REGIONS))
    return cost, link
''')

    M(r"""
Now the first stage and the monolithic model. `y` is the open/closed decision and
`c` the size; the two `CMIN`/`CMAX` rows are what tie them together, and they are
the reason the master in section 7 is a MILP rather than an LP.
""")

    C(r'''
ef = gp.Model("extensive_form")
ef.Params.OutputFlag = 0
ef.Params.MIPGap = MIPGAP

y = ef.addVars(NODES, vtype=GRB.BINARY, name="y")
c = ef.addVars(NODES, lb=0.0, ub=CMAX, name="c")
ef.addConstrs((c[n] <= CMAX * y[n] for n in NODES), name="ub")
ef.addConstrs((c[n] >= CMIN * y[n] for n in NODES), name="lb")
first = gp.quicksum(FIX[s] * y[s, r] + UNIT[s] * c[s, r] for (s, r) in NODES)

second = gp.LinExpr()
for j, scen in enumerate(SCEN):
    cost_j, _ = second_stage(ef, c, scen, f"_{j}")
    second += scen[1] * cost_j

ef.setObjective(first + second, GRB.MINIMIZE)
t0 = time.time()
ef.optimize()
T_EF = time.time() - t0

assert ef.SolCount > 0, f"the extensive form found no solution (status {ef.Status})"
assert ef.NumVars > 0 and ef.NumConstrs > 0, "an empty model reports success too"
EF_VAL = ef.ObjVal
CAP_EF = {n: c[n].X for n in NODES}
print(f"extensive form: {EF_VAL:.6f}   ({T_EF:.2f}s, {ef.NumVars} variables, "
      f"{ef.NumConstrs} constraints, {ef.NumBinVars} binaries)")
for (s, r) in NODES:
    if CAP_EF[s, r] > 1e-6:
        print(f"  open {s}/{r}: {CAP_EF[s, r]:.2f}")
''')

    M(r"""
**It concentrates everything in R1** and opens nothing in R2. R1 has the larger
demand base, and crossing a region costs five times what staying home does, so
one chain sited where the demand is beats two half-sized ones.

Look at the three capacities: 70.00, 66.50, 59.85. Those are not independent
numbers — they are `CMAX` walked down the yield chain, $70 \times 0.95 = 66.5$
and $66.5 \times 0.90 = 59.85$. The plan builds one maximal chain and sizes each
stage to exactly what the stage above can feed it. Building any more would be
capacity that can never be used.

That is a **structural** property, not an artefact of these numbers, so it is
worth asserting rather than admiring.
""")

    C(r'''
mine = CAP_EF["MINE", "R1"]
expect = {"MINE": mine,
          "PROC": mine * ETA["MINE"],
          "MFG": mine * ETA["MINE"] * ETA["PROC"]}
for s in STAGES:
    got = CAP_EF[s, "R1"]
    print(f"  {s:5s} built {got:8.4f}   yield chain says {expect[s]:8.4f}")
    assert abs(got - expect[s]) < 1e-6, (
        f"{s} capacity is off the yield chain; either the plan is not maximal "
        f"or the flow-balance rows are wrong")
assert all(CAP_EF[s, "R2"] < 1e-6 for s in STAGES), "R2 was expected to stay shut"
print("\nevery stage sits exactly on the yield chain, and R2 stays shut")
''')

    # ==================== 6. the recourse LP ===============================
    M(r"""
## 6. The recourse LP, and where a cut comes from

Fix the capacities to numbers and one scenario's problem becomes a plain LP.
Solve it and you get two things: its cost $Q_k(\hat c)$, and — the part that
matters — the **duals of the capacity rows**.

$$\beta_{k,n} \;=\; \frac{\partial Q_k}{\partial c_n}$$

A dual on `x[n] <= c[n]` says exactly how much scenario $k$'s cost would fall if
node $n$ had one more unit of capacity. That is a subgradient of $Q_k$, and a
subgradient is all a cut needs.

**This is the line that makes the method work**, and it is why the second stage
had to be an LP: `link[n].Pi`.
""")

    C(r'''
# THE FUNCTION IS THE LESSON: this is the subproblem the method is built on,
# and sections 7, 10 and 11 call it several hundred times at different plans.
def recourse(cap, scen, duals=True):
    """Q_k(cap) for one scenario, plus the capacity duals that become the cut."""
    m = gp.Model()
    m.Params.OutputFlag = 0
    cost, link = second_stage(m, cap, scen, "")
    m.setObjective(cost, GRB.MINIMIZE)
    m.optimize()
    assert m.Status == GRB.OPTIMAL, (
        f"recourse for {scen[0]} is not optimal (status {m.Status}); a cut "
        f"built from a non-optimal subproblem is not valid")
    beta = {n: link[n].Pi for n in NODES} if duals else None
    return m.ObjVal, beta


zero_cap = {n: 0.0 for n in NODES}
q0, b0 = recourse(zero_cap, SCEN[0])
print(f"scenario {SCEN[0][0]} with NO capacity: cost {q0:.4f}")
print("  (all demand unmet, so this is just the penalty)")
print(f"  check: PEN x total demand = "
      f"{PEN * sum(SCEN[0][2].values()):.4f}")
print("\n  duals - what one more unit of each node would save:")
for n in NODES:
    print(f"    {n[0]:5s}/{n[1]}  {b0[n]:9.4f}")
''')

    M(r"""
Every dual is negative or zero: more capacity never costs more. The MINE duals
are the largest in magnitude because a mine feeds the whole chain — one unit
there unlocks $0.95 \times 0.90 = 0.855$ units of finished product.

> **Predict before you run.** The loop below starts from zero capacity, where
> every scenario is desperate for more. Will the lower bound rise smoothly, or
> jump?
""")

    # ==================== 7. the L-shaped loop =============================
    M(r"""
## 7. The L-shaped loop, built by hand

The master holds `y`, `c`, and one $\theta_k$ per scenario. `lb=0` on $\theta$ is
valid here because every second-stage cost coefficient is non-negative, so the
recourse cost can never be negative — a bound that costs nothing and saves the
first iteration from being unbounded.

Each pass:

1. Solve the master. It is a relaxation, so its objective is a **lower bound**.
2. Evaluate the true recourse at the plan it proposed. First-stage cost plus the
   expected true recourse is a **feasible** plan's cost, hence an **upper bound**.
3. For every scenario whose $\theta_k$ was optimistic, add the cut.
4. Stop when nothing was optimistic, or the bounds meet.

**Adding a cut per scenario is the "multicut" variant.** Section 9 compares it
against aggregating them into one.
""")

    C(r'''
# THE FUNCTION IS THE LESSON: an iterative algorithm cannot be written out
# inline, and sections 8 to 10 call it at four scenario counts and both cut
# styles. Every line is narrated above; nothing here is hidden convenience.
def lshaped(scens, max_iter=60, tol=1e-6, multicut=True, verbose=True):
    m = gp.Model("master")
    m.Params.OutputFlag = 0
    m.Params.MIPGap = MIPGAP
    yv = m.addVars(NODES, vtype=GRB.BINARY, name="y")
    cv = m.addVars(NODES, lb=0.0, ub=CMAX, name="c")
    m.addConstrs((cv[n] <= CMAX * yv[n] for n in NODES))
    m.addConstrs((cv[n] >= CMIN * yv[n] for n in NODES))
    fc_expr = gp.quicksum(FIX[s] * yv[s, r] + UNIT[s] * cv[s, r]
                          for (s, r) in NODES)

    if multicut:
        th = m.addVars(range(len(scens)), lb=0.0, name="theta")
        m.setObjective(fc_expr + gp.quicksum(scens[j][1] * th[j]
                                             for j in range(len(scens))),
                       GRB.MINIMIZE)
    else:
        th1 = m.addVar(lb=0.0, name="theta")
        m.setObjective(fc_expr + th1, GRB.MINIMIZE)

    hist, UB, best, subsolves = [], float("inf"), None, 0
    for it in range(1, max_iter + 1):
        m.optimize()
        assert m.SolCount > 0, f"master infeasible at iteration {it}"
        LB = m.ObjVal                          # a relaxation -> valid lower bound
        chat = {n: cv[n].X for n in NODES}
        fc = sum(FIX[s] * yv[s, r].X + UNIT[s] * cv[s, r].X for (s, r) in NODES)

        total, ncuts = fc, 0
        if multicut:
            for j, scen in enumerate(scens):
                Qj, beta = recourse(chat, scen)
                subsolves += 1
                total += scen[1] * Qj
                if th[j].X < Qj - tol * max(1.0, abs(Qj)):
                    m.addConstr(th[j] >= Qj + gp.quicksum(
                        beta[n] * (cv[n] - chat[n]) for n in NODES))
                    ncuts += 1
        else:
            Qbar, bbar = 0.0, {n: 0.0 for n in NODES}
            for scen in scens:
                Qj, beta = recourse(chat, scen)
                subsolves += 1
                Qbar += scen[1] * Qj
                for n in NODES:
                    bbar[n] += scen[1] * beta[n]
            total += Qbar
            if th1.X < Qbar - tol * max(1.0, abs(Qbar)):
                m.addConstr(th1 >= Qbar + gp.quicksum(
                    bbar[n] * (cv[n] - chat[n]) for n in NODES))
                ncuts += 1

        if total < UB:
            UB, best = total, dict(chat)
        gap = (UB - LB) / max(1e-9, abs(UB))
        hist.append(dict(iter=it, LB=LB, UB=UB, gap=gap, cuts=ncuts))
        if verbose and (it <= 3 or it % 5 == 0 or ncuts == 0):
            print(f"  it {it:3d}  LB {LB:10.3f}  UB {UB:10.3f}  "
                  f"gap {100 * gap:8.4f}%  cuts {ncuts}")
        if ncuts == 0 or gap < 1e-6:
            break
    return dict(value=UB, bound=hist[-1]["LB"], iters=len(hist), hist=hist,
                plan=best, subsolves=subsolves, master=m)


t0 = time.time()
LS = lshaped(SCEN)
T_LS = time.time() - t0
print(f"\nL-shaped: {LS['value']:.6f}   ({T_LS:.2f}s, {LS['iters']} iterations, "
      f"{LS['subsolves']} subproblem solves)")
''')

    # ==================== 8. validation ====================================
    M(r"""
## 8. It must reproduce the extensive form

Not "come close". The cuts are valid and exact at the point they were generated,
so at convergence the two are the *same optimisation problem* and the objectives
must agree to solver tolerance.

The bounds are worth asserting too: the master's final objective is a lower bound
and the evaluated plan is an upper bound, so the true optimum is between them by
construction. If it were not, a cut would have removed the optimum.
""")

    C(r'''
rel = abs(LS["value"] - EF_VAL) / abs(EF_VAL)
print(f"extensive form : {EF_VAL:.9f}")
print(f"L-shaped       : {LS['value']:.9f}")
print(f"relative diff  : {rel:.3e}")
assert rel < 1e-9, f"L-shaped did not reproduce the extensive form ({rel:.2e})"

assert LS["bound"] <= EF_VAL + 1e-6, (
    "the final lower bound exceeds the true optimum, so a cut removed it")
assert LS["value"] >= EF_VAL - 1e-9, "a feasible plan beat the optimum"
print("\nbounds bracket the optimum: "
      f"{LS['bound']:.6f} <= {EF_VAL:.6f} <= {LS['value']:.6f}")

cmp_plan = pd.DataFrame([
    {"node": f"{s}/{r}", "extensive form": round(CAP_EF[s, r], 4),
     "L-shaped": round(LS["plan"][s, r], 4)} for (s, r) in NODES])
print()
cmp_plan
''')

    M(r"""
The plans match here as well, but that is a courtesy rather than a guarantee:
where the objective is flat, two different plans can be equally optimal. **The
objective is what must agree**, and it is what the assertion checks. Asserting on
the plan would be asserting on a tie, which is Part 6's warning about prose that
names a specific outcome where several are equally correct.
""")

    C(r'''
hist = pd.DataFrame(LS["hist"])
fig, ax = plt.subplots(1, 2, figsize=(11.5, 4))
ax[0].plot(hist["iter"], hist["LB"], "o-", color="#2471a3", lw=2, label="lower bound")
ax[0].plot(hist["iter"], hist["UB"], "s-", color="#c0392b", lw=2, label="upper bound")
ax[0].axhline(EF_VAL, color="#196f3d", ls="--", lw=1.5, label="extensive form")
ax[0].set_xlabel("iteration")
ax[0].set_ylabel("objective")
ax[0].set_title("the bounds close on the true optimum")
ax[0].legend()
ax[1].semilogy(hist["iter"], hist["gap"].clip(lower=1e-16), "o-", color="#8e44ad", lw=2)
ax[1].set_xlabel("iteration")
ax[1].set_ylabel("relative gap (log scale)")
ax[1].set_title("gap")
fig.tight_layout()
plt.show()
hist
''')

    M(r"""
The lower bound does **not** rise smoothly. It sits flat for a pass or two, then
jumps — iterations 2→3 and 5→6 and 7→8 move it not at all. That is what a
cutting-plane method looks like on a problem with binaries: the master keeps
proposing plans in a region the cuts have not yet described, and progress arrives
when a cut finally bites somewhere that changes which nodes are open.

The upper bound is worse behaved still: it holds at 1758.17 for eleven
iterations before improving. The gap you would quote at iteration 10 is 11%, and
the answer at that point is already only 3.8% from optimal — the *bound* is
loose, not the incumbent. Stopping early on a Benders gap therefore throws away
a better plan than the gap suggests you have.
""")

    # ==================== 9. multicut vs singlecut =========================
    M(r"""
## 9. Multicut against single cut

The version above adds one cut per scenario per iteration. The classical L-shaped
method aggregates them into a single cut on one $\theta$.

The trade is the usual one: the aggregated master has far fewer rows, and knows
far less.

> **Predict before you run.** One aggregated cut instead of twenty-four. Does
> that need more iterations, and does it change the answer?
""")

    C(r'''
t0 = time.time()
SC1 = lshaped(SCEN, max_iter=200, multicut=False, verbose=False)
T_SC = time.time() - t0

comp = pd.DataFrame([
    dict(variant="multicut", iterations=LS["iters"], subsolves=LS["subsolves"],
         seconds=round(T_LS, 2), value=round(LS["value"], 6),
         master_rows=LS["master"].NumConstrs),
    dict(variant="single cut", iterations=SC1["iters"], subsolves=SC1["subsolves"],
         seconds=round(T_SC, 2), value=round(SC1["value"], 6),
         master_rows=SC1["master"].NumConstrs)])

assert abs(SC1["value"] - EF_VAL) / abs(EF_VAL) < 1e-9, \
    "the single-cut variant found a different optimum"
assert SC1["iters"] > LS["iters"], \
    "aggregating the cuts did not cost iterations; the section has no lesson"
print(f"same optimum to {abs(SC1['value'] - LS['value']) / abs(EF_VAL):.1e}, "
      f"{SC1['iters'] / LS['iters']:.2f}x the iterations")
comp
''')

    M(r"""
**Same optimum, 1.47× the iterations, and 528 subproblem solves against 360.**
Aggregating loses information: twenty-four scenarios that disagree about which
node is short get averaged into one direction, and the master has to discover the
disagreement over more passes.

Note what did *not* happen — the single-cut master is smaller in rows but that
did not make it faster overall, because the cost here is dominated by solving
subproblems, and the single-cut variant solves more of them.
""")

    # ==================== 10. what it buys =================================
    M(r"""
## 10. What decomposition actually buys, measured

Now the claim from the front matter, checked. Solve both at four scenario counts
and time them.

> **Predict before you run.** Write down whether you expect L-shaped to overtake
> the extensive form by n = 200.
""")

    M(r"""
### 10.1 Now the streamlined version

Section 5 built the extensive form by hand and section 7 built the loop by hand.
This section needs both at four different scenario counts, so wrapping the tree
and the monolithic model in two short functions is the right trade **now** —
after you have written every line of them out once.

Neither wrapper contains anything new. The check that they reproduce the
hand-built result is the first row of the table below: at n = 24 they must return
the tree and the objective section 5 already produced.
""")

    C(r'''
# THE FUNCTION IS THE LESSON: these are the section 4 and section 5 cells with
# `n` made a parameter, wrapped only because section 10 needs them at four
# sizes. Nothing is hidden - compare them line by line with those cells.
def tree(n):
    """Section 4's scenario tree at any size, same seed and same draw order."""
    r_ = random.Random(SEED)
    return [(f"k{k}", 1.0 / n,
             {r: DEMAND_BASE[r] * (LO + (HI - LO) * r_.random()) for r in REGIONS})
            for k in range(n)]


def build_ef(scens):
    """Section 5's monolithic model, unchanged apart from taking the tree."""
    m = gp.Model()
    m.Params.OutputFlag = 0
    m.Params.MIPGap = MIPGAP
    yy = m.addVars(NODES, vtype=GRB.BINARY)
    cc = m.addVars(NODES, lb=0.0, ub=CMAX)
    m.addConstrs((cc[nd] <= CMAX * yy[nd] for nd in NODES))
    m.addConstrs((cc[nd] >= CMIN * yy[nd] for nd in NODES))
    obj = gp.quicksum(FIX[st_] * yy[st_, rg] + UNIT[st_] * cc[st_, rg]
                      for (st_, rg) in NODES)
    for j, scen in enumerate(scens):
        cj, _ = second_stage(m, cc, scen, f"_{j}")
        obj += scen[1] * cj
    m.setObjective(obj, GRB.MINIMIZE)
    return m


# the wrappers must reproduce what the hand-built cells produced
assert max(abs(tree(NK)[k][2][r] - SCEN[k][2][r])
           for k in range(NK) for r in REGIONS) < 1e-15, \
    "tree() does not reproduce section 4's SCEN"
_chk = build_ef(SCEN)
_chk.optimize()
assert abs(_chk.ObjVal - EF_VAL) / abs(EF_VAL) < 1e-9, \
    "build_ef() does not reproduce section 5's extensive form"
print(f"both wrappers reproduce the hand-built versions "
      f"({_chk.ObjVal:.6f} vs {EF_VAL:.6f})")
''')

    M(r"""
Now the sweep itself.
""")

    C(r'''
FULL_LICENCE = False   # True only if you have an academic or commercial licence

# Four sizes spanning the licence boundary: 99 scenarios fit the restricted
# ~2,000-variable cap and 100 do not, so 100 and 200 are the interesting ones.
SCALE_N = [24, 50, 100, 200]
LICENCE_CAP = 2000

# The size argument needs no solver: the extensive form is 12 first-stage
# variables plus 20 per scenario, exactly. So it is stated at every n. Only the
# TIMING comparison needs the monolithic model actually built, and on the free
# licence the last two would raise rather than run.
EF_VARS = {n: 2 * len(NODES) + 20 * n for n in SCALE_N}
EF_RUNNABLE = [n for n in SCALE_N if FULL_LICENCE or EF_VARS[n] <= LICENCE_CAP]
if not FULL_LICENCE:
    print(f"FULL_LICENCE = False, so the extensive form is solved only at "
          f"n = {EF_RUNNABLE} ({', '.join(str(EF_VARS[n]) for n in EF_RUNNABLE)} "
          f"variables).")
    print(f"At n = {[n for n in SCALE_N if n not in EF_RUNNABLE]} it would need "
          f"{', '.join(str(EF_VARS[n]) for n in SCALE_N if n not in EF_RUNNABLE)}"
          f" variables and the restricted licence would refuse it - which is this")
    print("section's whole point, so the refusal is the result and not a problem.")
    print("L-shaped runs at EVERY size below regardless, because it never builds it.\n")

rows = []
for n in SCALE_N:
    sc_n = tree(n)
    ef_sec = ef_obj = None
    if n in EF_RUNNABLE:
        m_n = build_ef(sc_n)
        t0 = time.time()
        m_n.optimize()
        ef_sec, ef_obj = round(time.time() - t0, 2), m_n.ObjVal
        assert m_n.NumVars == EF_VARS[n], "the variable-count arithmetic is wrong"

    t0 = time.time()
    r_n = lshaped(sc_n, max_iter=200, verbose=False)
    t_ls = time.time() - t0

    rows.append(dict(n=n, EF_vars=EF_VARS[n], EF_fits=EF_VARS[n] <= LICENCE_CAP,
                     EF_sec=ef_sec, LS_master_vars=r_n["master"].NumVars,
                     LS_sec=round(t_ls, 2), LS_iters=r_n["iters"],
                     rel=(f"{abs(r_n['value'] - ef_obj) / abs(ef_obj):.1e}"
                          if ef_obj is not None else "-")))
scale = pd.DataFrame(rows)

ran = scale.dropna(subset=["EF_sec"])
assert (ran.LS_sec > ran.EF_sec).all(), (
    "L-shaped came out faster somewhere; this notebook's framing says it does "
    "not, so the prose would need rewriting rather than the assertion relaxing")
assert scale.LS_iters.nunique() == 1, \
    "the iteration count moved with n; section 10's claim depends on it not doing so"
assert (~scale.EF_fits).any(), \
    "every size fits the licence cap, so this section has nothing to demonstrate"
print(f"iterations at every scenario count: {sorted(set(scale.LS_iters))}")
print(f"the extensive form stops fitting {LICENCE_CAP:,} variables between "
      f"n = {scale[scale.EF_fits].n.max()} and n = {scale[~scale.EF_fits].n.min()}")
scale
''')

    M(r"""
**The extensive form wins on time wherever it can be built at all, and the
assertion above requires that** — if it ever stopped being true on your machine,
this notebook's framing would be wrong and the prose would need rewriting, not
the assertion relaxing. The *ratio* is deliberately not quoted: it moved between
two runs on the same laptop while writing this, which is exactly why the
assertion tests the ordering and not a number.

**And notice where the timing column stops.** On the default restricted licence
there is no `EF_sec` for n = 100 or n = 200, because those models are 2,012 and
4,012 variables and the licence will not solve them. That blank is the finding.
The `EF_vars` column is still filled in at every size, because it is arithmetic
— 12 first-stage variables plus 20 per scenario — and needs no solver to state.
L-shaped has a number in every row.

What changes is the model you have to build. At n = 200 the extensive form needs
4,012 variables; the master needs 212 and each subproblem 20. On the restricted
licence the monolithic model is simply unavailable past n ≈ 99, and the
decomposition is unaffected because it never holds more than one scenario at a
time.

And the striking one: **the iteration count is 15 at every scenario count
tested** — 24, 50, 100 and 200. The number of cuts needed is a property of the
first-stage geometry, six nodes with open/close decisions, not of how many
scenarios there are. That is the property that makes the method scale, and it is
the assertion in the cell above.
""")

    # ==================== 11. the duals diagnostic =========================
    M(r"""
## 11. Are the duals actually saying anything?

A cut built from an all-zero dual vector is a flat line: it says the recourse
cost is at least some constant, regardless of capacity. Such a cut is valid and
useless. Worth checking how often the duals are informative.
""")

    C(r'''
rows = []
for label, cap in (("all-zero capacity", {n: 0.0 for n in NODES}),
                   ("the optimal plan", LS["plan"])):
    nz = tot = 0
    for scen in SCEN:
        _, beta = recourse(cap, scen)
        nz += sum(1 for n in NODES if abs(beta[n]) > 1e-9)
        tot += len(NODES)
    rows.append(dict(evaluated_at=label, nonzero_duals=nz, total=tot,
                     pct_binding=round(100 * nz / tot, 1)))
duals = pd.DataFrame(rows)
assert (duals.nonzero_duals > 0).all(), \
    "no dual was ever nonzero, so every cut would be a flat line"
print("a nonzero dual means that node's capacity row is binding in that scenario,")
print("so the cut it generates actually slopes.")
duals
''')

    M(r"""
At the optimal plan **51% of the capacity rows bind**, against 33% at zero
capacity. That is the right direction: at zero capacity most nodes are so far
from useful that the binding constraint is demand, not capacity, and the cut
carries information about only a third of the nodes.

This is the diagnostic to reach for when a Benders implementation stalls. A loop
that adds cuts and never moves the bound is usually generating cuts with no
slope, and this counts them.
""")

    # ==================== 12. agreement ====================================
    M(r"""
## 12. The agreement assertion

Everything above was built by hand; `src/lithium/twostage.py` holds the same
models as functions. The same model exists twice, deliberately — and deliberate
duplication with nothing comparing the copies is how a bug gets fixed in three
places out of four.

This compares the scenario tree, the extensive form, the recourse values **and
their duals**, both cut variants, and the full convergence history. The duals
matter: an implementation could agree on every objective and still build its cuts
from the wrong sign, and only a disagreement in $\beta$ would show it.
""")

    C(r'''
from lithium import TwoStageInstance, build_twostage_structure
from lithium import twostage as T2

nb_inst = TwoStageInstance(
    stages=STAGES, regions=REGIONS, fix=FIX, unit=UNIT, opc=OPC, eta=ETA,
    demand_base=DEMAND_BASE, region_cost=REGION_COST)
nb_st = build_twostage_structure(nb_inst, cmin=CMIN, cmax=CMAX, pen=PEN,
                                 tau_own=TAU_OWN, tau_cross=TAU_CROSS)

pkg_scen = T2.demand_scenarios(nb_st, n=NK, seed=SEED, lo=LO, hi=HI)
worst = max(abs(pkg_scen[k][2][r] - SCEN[k][2][r])
            for k in range(NK) for r in REGIONS)
print(f"{'scenario tree':30s} max abs diff {worst:.2e}")
assert worst < 1e-12, "the notebook and the package disagree on the tree"

pkg_ef = T2.extensive_form(nb_st, pkg_scen, mipgap=MIPGAP)
pkg_ef.optimize()
rel = abs(pkg_ef.ObjVal - EF_VAL) / abs(EF_VAL)
print(f"{'extensive form':30s} notebook {EF_VAL:12.6f}  "
      f"package {pkg_ef.ObjVal:12.6f}  rel {rel:.1e}")
assert rel < 1e-9, f"extensive forms disagree by {rel:.2e}"
''')

    M(r"""
The objectives agreeing is necessary and not sufficient. Two implementations can
report the same optimum and still build their cuts differently — from duals of
the opposite sign, say, or from a subproblem solved at a different point. So the
rest of the comparison goes after the machinery rather than the answer: the
recourse values **and their duals** at eight (scenario, plan) pairs, both cut
variants, and the whole convergence path.
""")

    C(r'''
zero = {n: 0.0 for n in NODES}
wv = wb = 0.0
for k in (0, 7, 13, 23):
    for cap in (zero, LS["plan"]):
        qa, ba = recourse(cap, SCEN[k])
        qb, bb = T2.recourse(nb_st, pkg_scen[k], cap)
        wv = max(wv, abs(qa - qb) / max(abs(qb), 1e-12))
        wb = max(wb, max(abs(ba[n] - bb[n]) for n in NODES))
print(f"{'recourse values (8 cases)':30s} max rel diff {wv:.2e}")
print(f"{'capacity duals (8 cases)':30s} max abs diff {wb:.2e}")
assert wv < 1e-9 and wb < 1e-9, "the recourse LP or its duals disagree"

for multi, label in ((True, "multicut"), (False, "single cut")):
    a = LS if multi else SC1
    b = T2.lshaped(nb_st, pkg_scen, multicut=multi, max_iter=200, mipgap=MIPGAP)
    rel = abs(a["value"] - b["value"]) / abs(b["value"])
    print(f"{label + ' value':30s} notebook {a['value']:12.6f}  "
          f"package {b['value']:12.6f}  rel {rel:.1e}")
    assert rel < 1e-9, f"{label} disagrees by {rel:.2e}"
    assert a["iters"] == b["iters"], (
        f"{label}: {a['iters']} iterations here against {b['iters']} in the "
        f"package - the loops are not the same loop")
    wh = max(abs(a["hist"][i]["LB"] - b["hist"][i]["LB"])
             for i in range(len(a["hist"])))
    print(f"{'  its convergence history':30s} max abs diff {wh:.2e}")
    assert wh < 1e-6, f"{label} converges along a different path"

print("\nnotebook and package agree on the tree, the extensive form, the")
print("recourse values, the DUALS, both cut variants, and the whole path there")
''')

    M(r"""
## 13. Summary

| Question | Answer |
|---|---|
| Does L-shaped reproduce the extensive form? | **Yes**, to 1e-9, and the bounds bracket the optimum |
| Is it faster? | **No** — it loses at every size tested, and the assertion in section 10 says so |
| Then what does it buy? | The extensive form needs 4,012 variables at n=200; the master needs 212 |
| How many iterations? | **15**, at n = 24, 50, 100 and 200 alike |
| Multicut or single cut? | Same optimum; single cut takes 1.47× the iterations and 528 subsolves against 360 |
| Is the Benders gap a good stopping rule? | **Careful.** At iteration 10 the gap says 11% and the incumbent is 3.8% off |
| Are the cuts informative? | 51% of capacity rows bind at the optimum, 33% at zero capacity |

### Formulation lessons

- **The cut is the dual.** $Q_k$ convex in the right-hand side is what makes a
  subgradient a valid underestimate everywhere. Lose the LP and you lose the cut.
- **The master is a relaxation**, so its objective is always a lower bound —
  which is what gives this method a certificate that progressive hedging has not.
- **A loose bound is not a bad incumbent.** Benders' gap closes from the bound
  side; stopping early discards a better plan than the gap admits.
- **`lb=0` on $\theta$ is a modelling decision, not a formality.** It is valid
  only because every second-stage cost is non-negative. State that, because on a
  model with revenues it is wrong and the first master is unbounded.
- **Decomposition is a size argument, not a speed argument** — at least until the
  monolithic model stops fitting in memory or in a licence.
- **Do not put a wall time in prose.** Assert the ordering you rely on and print
  the numbers from the reader's own run.

### Things to try

- `SCEN` with `NK = 200` at the top, then *Run all* — the extensive form leaves
  the restricted licence behind and the L-shaped loop does not notice
- `multicut=False` in section 7's call, and watch section 8's assertion still pass
- `PEN = 300` — make shortfall ruinous and see whether the plan still concentrates
- `TAU_CROSS = 0.35` — nearly free transport, so siting stops mattering
- Set $\theta$'s `lb=-GRB.INFINITY` and watch the first master go unbounded

### Where this goes next

**Part 2c** keeps this instance and changes the question from *how do I solve it*
to *what am I solving for* — expectation, CVaR, or the worst case.
""")

    return out

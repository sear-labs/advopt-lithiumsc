"""Build notebooks/04ab_planner_and_game.ipynb.

**Subject:** the step from one objective function to two. Part 4a is the
cooperative planner and its Pareto frontier; Part 4b is the first genuine game,
two firms at a fixed price, where the only channel between them is a residual
demand cap.

This notebook emits `common.chain_section()` rather than carrying it over,
because Part 4a **is** that model and 4ab comes first in the series. 04c emits
the same section; 04d and 04e carry the resulting wrapper over with a marker.
Narrated once, in `common.py`.

Section 11 is the most valuable thing here and it is preserved intact: a
comparison that produces a *provably impossible* answer, and two repairs that
each restore the bound while answering different questions. Its three
percentages were stale and are corrected from the run that ships with it.
"""
from . import common

NOTEBOOK = "04ab_planner_and_game.ipynb"
TITLE = "Part 4a / 4b - From cooperative planner to a two-firm game"


def cells():
    out = []

    def M(text):
        out.append(("md", text.strip("\n")))

    def C(text):
        out.append(("code", text.strip("\n")))

    # ================================ front ================================
    M(r"""
# Part 4a / 4b — From cooperative planner to a two-firm game

### Where one objective function stops being enough

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/USERNAME/lithium-modelling/blob/main/notebooks/04ab_planner_and_game.ipynb)

Parts 1–3b all had **one** objective, which means one decision maker. This
notebook takes the first two steps toward rivalry:

| | Model | Method | What it is |
|---|---|---|---|
| **4a** | one planner, two weighted regional costs | MILP, sweep the weight | **Not a game.** A cooperative bound and a Pareto frontier |
| **4b** | two firms, **fixed** price | iterative best response | The first genuine strategic interaction |

Part 4c (endogenous price), 4d (Stackelberg via KKT) and 4e (policy instruments)
follow.

### Institutional split: government constrains, firms optimise

- **Government** sets non-market constraints — local content minimums, tariffs,
  quotas. Exogenous and swept, never chosen by the model. Part 4e is where they
  arrive.
- **Firms** are profit maximisers operating inside those constraints. One firm
  per region.

That split is what justifies per-tier demand minimums as *policy* rather than as
a modelling trick, and it avoids a trilevel structure where governments and firms
both optimise.

### Structural change from Part 3b: vertical integration

In Part 3b any stage could source from either region. That is fine for a single
planner, but in a game it would need an internal transfer price between rival
firms at every stage — a modelling problem in its own right. So from here on:

- each firm owns a **vertically integrated chain** inside its own region
  (MINE → PROC → MFG)
- firms **compete downstream**, delivering finished product into either region's
  demand market
- cross-region delivery pays a transport premium, 2.4 against 0.5

### An asymmetric instance, deliberately

Symmetric regions produce symmetric results and teach nothing about entry. R1
begins deep into its learning curve; R2 is cheaper to build but starts
inexperienced. The question is whether R2 can buy its way down the curve before
R1's cost advantage locks it out. Section 2 loads the numbers and section 2.1
prints them keyed the way the model indexes.

### How to read this notebook

Sections 5 and 6 build the chain and the planner **by hand** — that is Part 4a,
and it is the model every later Part 4 notebook reuses. Section 9 builds Part
4b's best response by hand: one new constraint, and it carries the entire
strategic content. Section 10 wraps what you built, and section 14 asserts the
notebook and the `lithium` package agree to $10^{-9}$.
""")

    out += common.setup_section(notebook=NOTEBOOK)

    out += common.instance_section(agree=14)
    out += common.structure_section(agree=14, chain=5)
    out += common.capex_curve_section(chain=5, revenue="7.5 of Part 4c")

    out += common.chain_section(tiers=6, tiered=9)
    out += common.tier_section()

    # ======================= 7. now the streamlined version ================
    M(r"""
## 7. Now the streamlined version

**This is where the notebook crosses from learning into convenience.**

Section 5 built the chain once, by hand, and section 6 calibrated the tiers off
it. The rest of this notebook needs that construction **about twenty times** —
five planner solves for the Pareto frontier, then a best-response loop that
rebuilds one firm's chain on every round, twice over for the two move orders,
twice again for the learning comparison.

So the next two cells wrap it, and the cell after that **proves the wrapper
reproduces the hand-built planner**. That check is what earns the wrap.

Every argument is explicit and none of them defaults to a module-level global.
`def f(..., n=SOME_GLOBAL)` freezes the value at the moment the cell runs, so a
later reassignment silently changes nothing — a bug this series shipped once.

First, two names for things section 5 and section 6 already produced, so the
wrappers can take them as arguments rather than reaching for globals.
""")

    C(r'''
TIERS = (TIER_Q, TIER_M)     # what section 6 calibrated, as one argument
MIPGAP_PLAN = 0.005          # the gap section 5.1 set on the hand-built model

print(f"tiers keyed by: {sorted(TIERS[0])}")
print(f"thresholds    : { {r: [round(q, 1) for q in TIERS[0][r]] for r in REGIONS} }")
print(f"multipliers   : { {r: [round(v, 3) for v in TIERS[1][r]] for r in REGIONS} }")
print(f"MIP gap       : {MIPGAP_PLAN}")
''')

    M(r"""
### 7.1 The chain, wrapped

Sections 5.1 to 5.6, unchanged, as one function. `rev_price` is the one addition:
the planner passes `None` and gets no revenue term, while section 9's firm passes
`PRICE_FIXED` and gets one. Same chain, two uses.
""")

    C(r'''
def chain(m, r, learning, tiers, rev_price):
    """Sections 5.1-5.6, for any region, in any model."""
    b_ = m.addVars(BUILD[r], vtype=GRB.BINARY, name=f'b_{r}')
    c_ = m.addVars(BUILD[r], lb=0.0, ub=CAP_MAX, name=f'c_{r}')
    x_ = m.addVars(ACTIVE[r], lb=0.0, name=f'x_{r}')
    fmp_ = m.addVars(P, lb=0.0, name=f'fmp_{r}')
    fpf_ = m.addVars(P, lb=0.0, name=f'fpf_{r}')
    sale_ = m.addVars(REGIONS, P, lb=0.0, name=f'sale_{r}')
    disp_ = m.addVars(P, lb=0.0, name=f'disp_{r}')

    m.addConstrs((c_[s, v] <= CAP_MAX * b_[s, v] for (s, v) in BUILD[r]), name=f'su_{r}')
    m.addConstrs((c_[s, v] >= CAP_MIN * b_[s, v] for (s, v) in BUILD[r]), name=f'sl_{r}')
    m.addConstrs((x_[s, v, p] <= (LEGACY_CAP[s, r] if v == -1 else c_[s, v])
                  for (s, v, p) in ACTIVE[r]), name=f'cap_{r}')
    m.addConstrs((gp.quicksum(ETA['MINE', v, p] * x_['MINE', v, p]
                              for v in VIN[r, 'MINE', p]) == fmp_[p] for p in P), name=f'mine_{r}')
    m.addConstrs((fmp_[p] == gp.quicksum(x_['PROC', v, p] for v in VIN[r, 'PROC', p])
                  for p in P), name=f'pin_{r}')
    m.addConstrs((gp.quicksum(ETA['PROC', v, p] * x_['PROC', v, p]
                              for v in VIN[r, 'PROC', p]) == fpf_[p] for p in P), name=f'pout_{r}')
    m.addConstrs((fpf_[p] == gp.quicksum(x_['MFG', v, p] for v in VIN[r, 'MFG', p])
                  for p in P), name=f'min_{r}')
    m.addConstrs((gp.quicksum(ETA['MFG', v, p] * x_['MFG', v, p] for v in VIN[r, 'MFG', p])
                  == sale_.sum('*', p) + disp_[p] for p in P), name=f'mout_{r}')

    cum_ = m.addVars(P, lb=0.0, ub=3 * CAP_MAX * HORIZON + EXPERIENCE0[r], name=f'cum_{r}')
    m.addConstrs((cum_[p] == EXPERIENCE0[r] +
                  gp.quicksum(LEN[q] * x_['MFG', v, q] for q in P if q <= p
                              for v in VIN[r, 'MFG', q]) for p in P), name=f'cp_{r}')

    capex_ = (gp.quicksum(MU[s, v] * FIXED[s, r] * b_[s, v] for (s, v) in BUILD[r])
              + gp.quicksum(MU[s, v] * UNIT[s, r] * c_[s, v]
                            for (s, v) in BUILD[r] if s not in LEARN_STAGES))
    Q_ = m.addVars(P, lb=Q_START, ub=Q_START + Q_ADD, name=f'Q_{r}')
    C_ = m.addVars(P, lb=0.0, name=f'C_{r}')
    lam_ = m.addVars(P, K, lb=0.0, ub=1.0, name=f'lam_{r}')
    m.addConstrs((lam_.sum(p, '*') == 1 for p in P), name=f'sc_{r}')
    m.addConstrs((Q_[p] == gp.quicksum(QBP[k] * lam_[p, k] for k in K) for p in P), name=f'sQ_{r}')
    m.addConstrs((C_[p] == gp.quicksum(CBP[k] * lam_[p, k] for k in K) for p in P), name=f'sC_{r}')
    m.addConstrs((Q_[p] == Q_START + gp.quicksum(c_[s, v] for (s, v) in BUILD[r]
                                                 if s in LEARN_STAGES and v <= p)
                  for p in P), name=f'cc_{r}')
    for p in P:
        m.addSOS(GRB.SOS_TYPE2, [lam_[p, k] for k in K])
    rate_ = sum(UNIT[s, r] for s in LEARN_STAGES) / len(LEARN_STAGES)
    capex_ += gp.quicksum(MU['PROC', p] * rate_ * (C_[p] - (C_[p - 1] if p > 0 else 0.0))
                          for p in P)

    if learning == 'both' and tiers is not None:
        tq, tm = tiers
        J_ = list(range(N_TIERS))
        z_ = m.addVars(P, J_, vtype=GRB.BINARY, name=f'z_{r}')
        m.addConstrs((z_.sum(p, '*') == 1 for p in P), name=f'ot_{r}')
        lagp = {p: YEAR_TO_P[max(1, START[p] - LAG_YEARS)] for p in P}
        bigq = 3 * CAP_MAX * HORIZON + EXPERIENCE0[r]
        m.addConstrs((cum_[lagp[p]] >= tq[r][j - 1] - bigq * (1 - z_[p, j])
                      for p in P for j in J_ if j > 0), name=f'tf_{r}')
        m.addConstrs((cum_[lagp[p]] <= tq[r][j] + bigq * (1 - z_[p, j])
                      for p in P for j in J_ if j < N_TIERS - 1), name=f'tc_{r}')
        ts_ = m.addVars(STAGES, P, J_, lb=0.0, name=f'ts_{r}')
        m.addConstrs((ts_.sum(s, p, '*') == gp.quicksum(x_[s, v, p] for v in VIN[r, s, p])
                      for s in STAGES for p in P), name=f'tss_{r}')
        m.addConstrs((ts_[s, p, j] <= 3 * CAP_MAX * z_[p, j]
                      for s in STAGES for p in P for j in J_), name=f'tl_{r}')
        opex_ = gp.quicksum(OMEGA[p] * OPEX[s, r] * tm[r][j] * ts_[s, p, j]
                            for s in STAGES for p in P for j in J_)
    else:
        z_ = None
        opex_ = gp.quicksum(OMEGA[p] * OPEX[s, r] * x_[s, v, p] for (s, v, p) in ACTIVE[r])

    trans_ = gp.quicksum(OMEGA[p] * TRANSPORT[r, rt] * sale_[rt, p]
                         for rt in REGIONS for p in P)
    dcost_ = gp.quicksum(OMEGA[p] * PEN_DISPOSE * disp_[p] for p in P)
    rev_ = (gp.quicksum(OMEGA[p] * rev_price * sale_[rt, p] for rt in REGIONS for p in P)
            if rev_price is not None else None)
    return dict(b=b_, c=c_, x=x_, sale=sale_, disp=disp_, cum=cum_, z=z_,
                capex=capex_, opex=opex_, trans=trans_, dcost=dcost_, revenue=rev_,
                cost=capex_ + opex_ + trans_ + dcost_)


print("chain() defined -", chain.__doc__.splitlines()[0])
''')

    M(r"""
### 7.2 The planner, wrapped

Section 5.7's model, for any weight. `w1` is the planner's relative valuation of
the two regions — **not** a bargaining outcome, and not a share of anything.
""")

    C(r'''
def planner(w1, learning, tiers, mipgap):
    """Section 5.7, for any weight."""
    m = gp.Model()
    m.Params.OutputFlag = 0
    m.Params.MIPGap = mipgap
    H = {r: chain(m, r, learning, tiers, rev_price=None) for r in REGIONS}
    short = m.addVars(REGIONS, P, lb=0.0, name='short')
    m.addConstrs((gp.quicksum(H[r]['sale'][rt, p] for r in REGIONS) + short[rt, p]
                  >= DEMAND[rt, p] for rt in REGIONS for p in P), name='demand')
    pen = gp.quicksum(OMEGA[p] * PEN_SHORT * short[rt, p] for rt in REGIONS for p in P)
    m.setObjective(w1 * H['R1']['cost'] + (1 - w1) * H['R2']['cost'] + pen, GRB.MINIMIZE)
    m.optimize()
    m._H, m._short, m._pen = H, short, pen
    return m


print("planner() defined")
''')

    M(r"""
### 7.3 Does the wrapper reproduce the hand-built planner?

Same weight, same learning setting, same tiers. If these two numbers differ, the
wrapper is not the model you read in section 5.
""")

    C(r'''
check = planner(W1, learning='capacity', tiers=None, mipgap=MIPGAP_PLAN)
rel = abs(check.ObjVal - m.ObjVal) / abs(m.ObjVal)
print(f"hand-built (section 5.7): {m.ObjVal:,.9f}")
print(f"wrapper    (section 7.2): {check.ObjVal:,.9f}")
assert rel < 1e-9, f"the wrapper is not the model you read; relative gap {rel:.2e}"
print(f"\nagree to {rel:.1e} - the wrap is earned")
''')

    # ========================= 8. the Pareto frontier ======================
    M(r"""
## 8. Model 4a — the Pareto frontier

$$\min \;\; w\,\text{Cost}_{R1} + (1-w)\,\text{Cost}_{R2} + \pi^{short}\!\sum u$$

Sweeping $w$ traces the frontier of achievable cost pairs. That is the right
cooperative benchmark to measure the cost of rivalry against — **and it is not a
game**. One objective function means one decision maker.

> **Predict before you run.** As $w$ rises, the planner values R1's cost more and
> should shift building to R2. Do you expect that shift to be **smooth** across
> the five weights, or something else? And what should happen to unserved demand
> at the extremes?
""")

    C(r'''
WEIGHTS = [0.1, 0.3, 0.5, 0.7, 0.9]

rows = []
for w in WEIGHTS:
    mw = planner(w, learning='both', tiers=TIERS, mipgap=MIPGAP_PLAN)
    assert mw.SolCount > 0, f"w={w} found no solution"
    H = mw._H
    rows.append(dict(weight_R1=w, weighted_obj=round(mw.ObjVal, 1),
                     cost_R1=round(H['R1']['cost'].getValue(), 1),
                     cost_R2=round(H['R2']['cost'].getValue(), 1),
                     builds_R1=sum(1 for k in H['R1']['b'] if H['R1']['b'][k].X > 0.5),
                     builds_R2=sum(1 for k in H['R2']['b'] if H['R2']['b'][k].X > 0.5),
                     shortfall=round(sum(mw._short[rt, p].X
                                         for rt in REGIONS for p in P), 2)))
frontier = pd.DataFrame(rows)

# the frontier is a set of DISCRETE points, so the build split should jump
splits = list(zip(frontier.builds_R1, frontier.builds_R2))
assert len(set(splits)) < len(splits), \
    "every weight gave a different build split; the frontier is smoother than claimed"
print(f"build splits across the sweep: {splits}")
print(f"distinct splits: {len(set(splits))} for {len(WEIGHTS)} weights")
frontier
''')

    M(r"""
Plot the frontier as cost pairs, and the build split beside it. The left panel is
the frontier itself; the right shows why it has the shape it does.
""")

    C(r'''
fig, ax = plt.subplots(1, 2, figsize=(12, 4.3))
ax[0].plot(frontier.cost_R1, frontier.cost_R2, 'o-', lw=2.4, color='#2471a3')
for _, row in frontier.iterrows():
    ax[0].annotate(f"w={row.weight_R1:.1f}", (row.cost_R1, row.cost_R2),
                   textcoords="offset points", xytext=(6, 6), fontsize=9)
ax[0].set(xlabel="R1 cost", ylabel="R2 cost",
          title="The frontier is a few discrete points, not a curve")
ax[1].bar([str(w) for w in frontier.weight_R1], frontier.builds_R1,
          label='R1 builds', color='#2471a3')
ax[1].bar([str(w) for w in frontier.weight_R1], frontier.builds_R2,
          bottom=frontier.builds_R1, label='R2 builds', color='#d68910')
ax[1].set(xlabel="weight on R1's cost", ylabel="plants built",
          title="Lumpy investment makes the split jump")
ax[1].legend()
for a in ax:
    a.grid(alpha=0.3)
plt.tight_layout(); plt.show()
''')

    M(r"""
The frontier is sharply **non-convex and nearly bang-bang**: the planner loads
essentially all capacity onto whichever region it weights *less*, because that
region's cost is discounted in the objective. Across the sweep the build split
goes 6/3 → 6/3 → 3/3 → 3/6 → 3/6 — three distinct allocations for five weights,
which is what the assertion above checks.

That shape is a direct consequence of lumpy investment: you cannot build 0.4 of a
facility, so the frontier is a set of discrete points rather than a smooth curve.
It is also why a **weighted-sum scalarisation is a weak tool** for this problem —
whole regions of the frontier are unreachable by any weight. An
$\varepsilon$-constraint formulation (minimise R1's cost subject to R2's cost
$\le$ budget) would trace it more faithfully and is worth trying.

Note the shortfall column rising at the extremes, 0.00 at $w \le 0.5$ but 0.21
at 0.7 and 1.46 at 0.9: when the planner nearly ignores one region it starts
letting demand go unserved rather than building there. Hold on to that — it is
the same mechanism that makes section 11's naive comparison impossible.
""")

    # ===================== 9. model 4b, by hand ============================
    M(r"""
## 9. Model 4b — two firms at a fixed price

Now each region is a **profit-maximising firm**:

$$\max_{\text{firm } r} \;\;
\underbrace{\sum_p \omega_p\,\bar{p}\sum_{rt}\text{sale}_{r,rt,p}}_{\text{revenue}}
\;-\;\underbrace{\text{Cost}_r}_{\text{capex + opex + transport + disposal}}$$

The chain is unchanged — that is why section 7 wrapped it. **One constraint is
new, and it carries the entire strategic content of Part 4b:**

$$\text{sale}_{r,rt,p} \;\le\; \max\{0,\; D_{rt,p} - \overline{\text{sale}}_{-r,rt,p}\}$$

At a **fixed** price nobody buys more than the market wants, so a firm's sales
are capped by **residual demand** — whatever the rival left unserved. That single
line makes the structure a **race for market share**: at any price above marginal
cost both firms want the whole market, and whoever commits capacity first
captures it.

Watch what it costs in model size. The rivalry is 26 constraints.
""")

    C(r'''
FIRM = 'R1'
rival_sales = {(rt, p): 0.0 for rt in REGIONS for p in P}

mb = gp.Model("best_response")
mb.Params.OutputFlag = 0
mb.Params.MIPGap = MIPGAP_PLAN
h = chain(mb, FIRM, 'both', TIERS, rev_price=PRICE_FIXED)
mb.update()
before = mb.NumConstrs

# THE constraint: nobody sells more than the demand the rival left behind
mb.addConstrs((h['sale'][rt, p] <= max(0.0, DEMAND[rt, p] - rival_sales.get((rt, p), 0.0))
               for rt in REGIONS for p in P), name='residual')
mb.update()

print(f"constraints before the residual cap: {before}")
print(f"                after              : {mb.NumConstrs}"
      f"   (+{mb.NumConstrs - before} = {len(REGIONS)} markets x {len(P)} periods)")
print(f"\nthe rival sells nothing, so the cap is just demand itself:")
print(f"{'p':>3s} {'year':>5s} " + " ".join(f"{r:>9s}" for r in REGIONS))
for p in [0, 6, len(P) - 1]:
    print(f"{p:3d} {START[p]:5d} " + " ".join(f"{DEMAND[r, p]:9.2f}" for r in REGIONS))
''')

    M(r"""
### 9.1 The objective, and the first solve

Revenue is `PRICE_FIXED` per unit, discounted by `OMEGA[p]` — that is the
`revenue` handle `chain()` already returns, which is why it took a `rev_price`
argument at all. Profit is revenue minus the same cost expression the planner
minimised.

> **Predict before you run.** R1 faces no rival, so the residual cap is the whole
> market. Demand over the horizon totals about 2,743 rate-units. Will R1 serve
> all of it? Its revenue is a flat 12.0 per unit and its cheapest chain costs
> rather less than that — but every plant is lumpy.
""")

    C(r'''
mb.setObjective(h['revenue'] - h['cost'], GRB.MAXIMIZE)
mb.update()
assert mb.NumVars > 0 and mb.NumConstrs > 0, "empty model"

mb.optimize()
assert mb.SolCount > 0, f"no solution; status {mb.Status}"

hand_built = mb.ObjVal
print(f"status {mb.Status}, profit {hand_built:,.4f}, gap {mb.MIPGap:.2e}")
print(f"  revenue  {h['revenue'].getValue():12,.2f}")
print(f"  cost     {h['cost'].getValue():12,.2f}")
print(f"  sales    {sum(h['sale'][rt, p].X for rt in REGIONS for p in P):12,.2f}"
      f"   of {sum(DEMAND.values()):,.1f} demanded")
print(f"  builds   {sum(1 for k in h['b'] if h['b'][k].X > 0.5):12d}")
''')

    M(r"""
**R1 declines to serve the whole market even with no competition.** It sells
about 1,652 of the 2,743 rate-units demanded. At a flat price of 12.0 the revenue
on a marginal unit cannot justify committing another lumpy facility, so the
last tranche of demand simply goes unmet.

That is not a bug and it is not a solver artefact — it is what a fixed price
does. Remember it: section 11 is where it turns a straightforward comparison into
an impossible one, and Part 4c is where an endogenous price removes it.
""")

    # ===================== 10. the streamlined game ========================
    M(r"""
## 10. The best response, wrapped — and the three ways this game can end

You have written the residual cap and the profit objective once. The loop below
needs them **about forty times**. Two cells: the best response, and the iteration
that calls it.

**The termination test is the interesting part, and it differs from Part 4c's.**
Here the strategy that matters is the set of plants built — a tuple of
`(stage, vintage)` pairs, which is **discrete**. So exact state matching is
correct, and a tolerance would be wrong. In Part 4c the strategy is a continuous
quantity schedule and exact matching invents cycles out of MIP-gap noise. Same
loop, opposite right answer, and the reason is the type of the strategy.

Three exits:

1. **CONVERGED** — the profile repeats immediately. A fixed point: a
   pure-strategy Nash equilibrium of the discretised game.
2. **CYCLE** — it repeats after $k \ge 2$ rounds. **No pure-strategy equilibrium
   was found**, and the cycle itself is the result: each firm builds only if the
   other does not. That is real economics, and suppressing it would be the actual
   error.
3. **MAX_ITER** — report non-convergence honestly.
""")

    C(r'''
def best_response(r, rival, learning, tiers, mipgap):
    """Section 9: the chain, the residual cap, and a profit objective."""
    m = gp.Model()
    m.Params.OutputFlag = 0
    m.Params.MIPGap = mipgap
    h_ = chain(m, r, learning, tiers, rev_price=PRICE_FIXED)
    m.addConstrs((h_['sale'][rt, p] <= max(0.0, DEMAND[rt, p] - rival.get((rt, p), 0.0))
                  for rt in REGIONS for p in P), name='residual')
    m.setObjective(h_['revenue'] - h_['cost'], GRB.MAXIMIZE)
    m.optimize()
    m._h = h_
    return m


def iterate(learning, tiers, first, max_iter, mipgap):
    """Iterated best response, terminating on the BUILD PLAN - see above."""
    sales = {r: {(rt, p): 0.0 for rt in REGIONS for p in P} for r in REGIONS}
    plans, hist, log = {}, [], []
    order = [first] + [r for r in REGIONS if r != first]
    for it in range(max_iter):
        for r in order:
            rival = {}
            for other in REGIONS:
                if other == r:
                    continue
                for k, v in sales[other].items():
                    rival[k] = rival.get(k, 0.0) + v
            b = best_response(r, rival, learning, tiers, mipgap)
            if b.SolCount == 0:
                return dict(status='INFEASIBLE', iters=it, log=log)
            sales[r] = {(rt, p): b._h['sale'][rt, p].X for rt in REGIONS for p in P}
            plans[r] = tuple(sorted((s, v) for (s, v) in b._h['b']
                                    if b._h['b'][s, v].X > 0.5))
            log.append(dict(iter=it, firm=r, profit=b.ObjVal, builds=len(plans[r]),
                            total_sales=sum(sales[r].values())))
        state = tuple(plans.get(r) for r in REGIONS)
        if state in hist:
            # repeating IMMEDIATELY is a fixed point; after k rounds it is a
            # genuine k-cycle with no pure-strategy equilibrium found
            clen = len(hist) - hist.index(state)
            return dict(status=('CONVERGED' if clen == 1 else 'CYCLE'),
                        cycle_len=clen, iters=it + 1, log=log, plans=plans,
                        sales=sales)
        hist.append(state)
    return dict(status='MAX_ITER', iters=max_iter, log=log, plans=plans, sales=sales)


print("best_response() and iterate() defined")
''')

    M(r"""
### 10.1 Does the wrapper reproduce the hand-built best response?
""")

    C(r'''
check = best_response(FIRM, rival_sales, 'both', TIERS, MIPGAP_PLAN)
rel = abs(check.ObjVal - hand_built) / abs(hand_built)
print(f"hand-built (section 9.1): {hand_built:,.9f}")
print(f"wrapper    (section 10) : {check.ObjVal:,.9f}")
assert rel < 1e-9, f"the wrapper is not the model you read; relative gap {rel:.2e}"
print(f"\nagree to {rel:.1e} - the wrap is earned")
''')

    # ===================== 11. does moving first pay =======================
    M(r"""
## 11. Does moving first pay?

> **Predict before you run.** The firm that moves first optimises against an
> empty market and can commit capacity to whatever it likes; the second optimises
> against the leftovers. Write down whether you expect that to be worth a few
> per cent, or a lot — and whether you expect the two orders to reach the *same*
> equilibrium.
""")

    C(r'''
MAX_ITER = 10

runs, rows = {}, []
for first in REGIONS:
    res = iterate('both', TIERS, first=first, max_iter=MAX_ITER, mipgap=MIPGAP_PLAN)
    runs[first] = res
    last = {g['firm']: g for g in res['log'][-len(REGIONS):]}
    rows.append(dict(first_mover=first, status=res['status'],
                     repeat_length=res.get('cycle_len'), iterations=res['iters'],
                     **{f'profit_{r}': round(last[r]['profit'], 1) for r in REGIONS},
                     **{f'sales_{r}': round(last[r]['total_sales'], 1) for r in REGIONS}))
orders = pd.DataFrame(rows)

assert (orders.status == 'CONVERGED').all(), "a move order failed to converge"
for r in REGIONS:
    own, other = orders[f'profit_{r}'][REGIONS.index(r)], orders[f'profit_{r}'][1 - REGIONS.index(r)]
    print(f"{r}: moving first is worth {100 * (own / other - 1):5.1f}% "
          f"({own:,.1f} against {other:,.1f})")
assert orders.profit_R1[0] != orders.profit_R1[1], \
    "both move orders gave the same equilibrium; there is no first-mover effect"
orders
''')

    M(r"""
Both orders reach a **fixed point** (repeat length 1), so a pure-strategy
equilibrium exists in this instance — but they reach **different** ones.

**Moving first is worth 29.1% of profit to R1 and 49.2% to R2.** That is
first-mover advantage emerging endogenously from capacity commitment: the leader
builds and locks in residual demand, and the follower optimises against what is
left. R2 gains more in percentage terms precisely because it is the weaker firm —
it has more to lose from being second.

Two consequences worth stating plainly.

**The equilibrium is not unique, so "the" answer to this game does not exist.**
Reporting one ordering would be reporting an artefact of the solution procedure.
Sweep the order — and if you extend this, sweep the starting profile too. The
assertion above fails if the two orders ever coincide, which would mean this
whole section had nothing to show.

**No cycling appeared here, but do not generalise from that.** A fixed price
makes each firm's problem well behaved. Once price responds to total quantity
(Part 4c), a firm's optimal capacity depends on the rival's output *through the
price*, and cycling becomes much more likely — Part 4c-exact finds exactly that
once the revenue approximation is removed.
""")

    C(r'''
trace = pd.DataFrame(runs['R1']['log'])
print("the mechanism, round by round, with R1 moving first:")
trace
''')

    M(r"""
The trace shows it directly: R1 moves first against an empty market and takes
1,652.0 units; R2 then optimises against the residual and takes 987.1. From
iteration 1 onward neither firm changes anything — a fixed point, and the reason
the loop stops after 2 rounds rather than the 10 it was allowed.
""")

    # ================== 12. the cost of rivalry ============================
    M(r"""
## 12. The cost of rivalry — and a bound that looks violated

Comparing 4a to 4b directly is invalid: 4a minimises **cost**, 4b maximises
**profit**. The clean approach is to take the competitive *decisions* and
re-price them through the cooperative cost accounting.

But there is a trap here, and it is worth walking into deliberately, because the
naive version produces a result that is **provably impossible**.

The planner has strictly more freedom than the firms: it can choose *any* pair of
plans, including exactly the competitive one. So the planner's cost must be a
**lower bound** on the competitive cost. If a comparison says otherwise, the
comparison is wrong — not the theory.
""")

    C(r'''
res = runs['R1']
comp_cost, comp_sales = 0.0, {}
for r in REGIONS:
    rival = {}
    for other in REGIONS:
        if other == r:
            continue
        for k, v in res['sales'][other].items():
            rival[k] = rival.get(k, 0.0) + v
    br = best_response(r, rival, 'both', TIERS, MIPGAP_PLAN)
    comp_cost += br._h['cost'].getValue()
    for rt in REGIONS:
        for p in P:
            comp_sales[r, rt, p] = br._h['sale'][rt, p].X
served = {(rt, p): sum(comp_sales[r, rt, p] for r in REGIONS)
          for rt in REGIONS for p in P}

coop = planner(0.5, learning='both', tiers=TIERS, mipgap=MIPGAP_PLAN)
coop_cost = sum(coop._H[r]['cost'].getValue() for r in REGIONS)

print("--- the NAIVE comparison ---")
print(f"  cooperative planner cost   {coop_cost:10.1f}")
print(f"  competitive cost           {comp_cost:10.1f}")
print(f"  apparent cost of rivalry   {comp_cost - coop_cost:10.1f}"
      f"  ({100 * (comp_cost - coop_cost) / coop_cost:+.1f}%)")
print(f"\n  demand over horizon        {sum(DEMAND.values()):10.1f}")
print(f"  served by the firms        {sum(served.values()):10.1f}")
print(f"  UNSERVED                   {sum(DEMAND.values()) - sum(served.values()):10.1f}")

assert comp_cost < coop_cost, \
    "the naive comparison did not produce the impossible result this section is about"
''')

    M(r"""
The apparent cost of rivalry is **negative** — competition looks *cheaper* than
the planner, by 8.8%. That cannot be an efficiency gain, and the assertion above
deliberately requires it, because the impossible answer is the lesson.

**The resolution is in the last line.** The planner is required to serve all
demand (or pay a shortfall penalty); the firms are not, and they simply decline
to serve about 104 rate-units — exactly the under-provision section 9.1 flagged.
So the competitive outcome **is not in the planner's feasible set**, and the two
numbers are not comparable. Serving that last tranche needs another lumpy
facility, and the planner pays for it while the firms walk away.

Two ways to repair the comparison. They answer different questions, and both
restore the bound.
""")

    C(r'''
# TEST 1 -- volume-matched: hold the planner to exactly what the firms served
mv = gp.Model()
mv.Params.OutputFlag = 0
mv.Params.MIPGap = 1e-6
Hv = {r: chain(mv, r, 'both', TIERS, rev_price=None) for r in REGIONS}
mv.addConstrs((gp.quicksum(Hv[r]['sale'][rt, p] for r in REGIONS) >= served[rt, p]
               for rt in REGIONS for p in P), name='match_volume')
mv.setObjective(gp.quicksum(Hv[r]['cost'] for r in REGIONS), GRB.MINIMIZE)
mv.optimize()
assert mv.SolCount > 0, "the volume-matched planner found no solution"

# TEST 2 -- welfare-inclusive: charge the firms the same social cost of unserved demand
pen_comp = sum(OMEGA[p] * PEN_SHORT * max(0.0, DEMAND[rt, p] - served[rt, p])
               for rt in REGIONS for p in P)
coop_total = coop_cost + coop._pen.getValue()

print("TEST 1 -- volume-matched (efficiency only)")
print(f"  planner at competitive volume {mv.ObjVal:10.1f}")
print(f"  competitive                   {comp_cost:10.1f}")
print(f"  cost of rivalry               {comp_cost - mv.ObjVal:10.1f}"
      f"  ({100 * (comp_cost - mv.ObjVal) / mv.ObjVal:+.2f}%)")
print("\nTEST 2 -- welfare-inclusive (efficiency + unserved demand)")
print(f"  planner cost + penalty        {coop_total:10.1f}")
print(f"  competitive cost + penalty    {comp_cost + pen_comp:10.1f}")
print(f"  cost of rivalry               {comp_cost + pen_comp - coop_total:10.1f}"
      f"  ({100 * (comp_cost + pen_comp - coop_total) / coop_total:+.1f}%)")

# both repairs must restore the bound; that is the point of the section
assert mv.ObjVal <= comp_cost + 1e-3, "volume-matched bound still violated"
assert coop_total <= comp_cost + pen_comp + 1e-3, "welfare-inclusive bound still violated"
print("\nboth bounds hold")
''')

    M(r"""
Both repairs restore the bound, and the two numbers answer different questions:

| Comparison | Cost of rivalry | What it measures |
|---|---|---|
| Naive (different volumes) | **−8.8%** | nothing — invalid |
| Volume-matched | **+0.96%** | pure productive inefficiency of splitting output between two firms |
| Welfare-inclusive | **+34.3%** | that inefficiency **plus** the social loss from 103.7 units never produced |

The volume-matched figure is small, which is itself informative: given *what*
gets produced, two firms produce it almost as cheaply as a planner would. Nearly
all of the welfare cost of rivalry in this model is the **under-provision** —
capacity that no firm finds privately worth building.

That under-provision is an artefact of the **fixed price**, though. At a constant
price the revenue on a marginal unit cannot rise to justify a lumpy facility.
With an endogenous price (Part 4c) unserved demand raises the price and draws
capacity in, so the quantity distortion largely disappears and the remaining gap
becomes interpretable as genuine strategic inefficiency.

**The general lesson**: when a comparison violates a bound you can prove, the
error is in the comparison. Check first whether the two models are solving the
same problem — most often they differ in a *constraint* (here, the obligation to
serve demand) rather than in anything economic.
""")

    # ===================== 13. learning under rivalry ======================
    M(r"""
## 13. Learning under rivalry

Part 3b found production learning did not change the plan under cost
minimisation, because cumulative production was pinned by demand. In a game
quantity is a **decision**, so the channel finally has a lever.

> **Predict before you run.** Turning the production channel off means every unit
> is operated at full price — no tier discount ever. Do you expect that to change
> profits by a few per cent, or to change what gets *built*?
""")

    C(r'''
rows = []
for lm in ['capacity', 'both']:
    r2 = iterate(lm, TIERS, first='R1', max_iter=MAX_ITER, mipgap=MIPGAP_PLAN)
    last = {g['firm']: g for g in r2['log'][-len(REGIONS):]}
    rows.append(dict(learning=lm, status=r2['status'],
                     **{f'profit_{r}': round(last[r]['profit'], 1) for r in REGIONS},
                     **{f'sales_{r}': round(last[r]['total_sales'], 1) for r in REGIONS},
                     **{f'builds_{r}': last[r]['builds'] for r in REGIONS}))
learning_table = pd.DataFrame(rows)

flat, tiered = learning_table.iloc[0], learning_table.iloc[1]
print(f"without the production channel: {flat.builds_R1 + flat.builds_R2} plants built "
      f"in total, sales {flat.sales_R1 + flat.sales_R2:,.1f}")
print(f"with it                       : {tiered.builds_R1 + tiered.builds_R2} plants built "
      f"in total, sales {tiered.sales_R1 + tiered.sales_R2:,.1f}")
for r in REGIONS:
    print(f"  {r}: sales {flat[f'sales_{r}']:7.1f} -> {tiered[f'sales_{r}']:7.1f}"
          f"  ({100 * (tiered[f'sales_{r}'] / flat[f'sales_{r}'] - 1):5.1f}% more)"
          f"   profit {flat[f'profit_{r}']:8.1f} -> {tiered[f'profit_{r}']:8.1f}")
assert flat.builds_R1 + flat.builds_R2 < tiered.builds_R1 + tiered.builds_R2, \
    "the production channel did not change what gets built"
learning_table
''')

    M(r"""
**The production channel does not merely reduce cost here — it decides whether
anything gets built at all.**

Without it, neither firm builds a single plant: R1 earns 2,486.9 and R2 815.0,
selling 933.3 and 470.2 out of legacy capacity alone. With it, both build three
plants, sales rise to 1,652.0 and 987.1 — up 77.0% and 109.9% — and profits
roughly triple, to 7,612.7 and 2,494.5.

The mechanism is the tier discount. Operating every unit at full price makes the
chain expensive enough that a lumpy facility never pays for itself at a fixed
price of 12.0. The tiers cut operating cost by 18% and then 33%, and that is what
tips the investment decision.

**So keep the channel in the formulation**, and note that the reason is stronger
than "it is a cost reduction". The asymmetry in `EXPERIENCE0` is also doing what
it was built to do: R1 starts several tiers up the curve and holds a durable
operating-cost advantage that R2's cheaper capital cannot fully offset. That
advantage is what Part 4c turns into a reason to *flood the market*.

One caveat on reading this table. `learning='capacity'` removes the tier block
entirely rather than setting the tiers to 1.0, so the comparison is "tiered opex
versus flat opex", not "learning versus no learning at the same cost level". The
two firms are genuinely more expensive to run in the first row, which is the
point, but it is not a pure information effect.
""")

    # ================= 14. the agreement assertion =========================
    M(r"""
## 14. The agreement assertion

Everything above was built by hand, and `src/lithium/` holds the same models as
functions. **The same model exists twice, deliberately** — and deliberate
duplication with nothing comparing the copies is how a bug gets fixed in three
places out of four.

This cell imports the package, hands it the same instance dictionaries and the
same knobs, runs the same case as section 9.1, and asserts the two objectives
agree to $10^{-9}$.
""")

    C(r'''
from lithium import Instance, best_response_fixed_price, build_structure

nb_instance = Instance(
    regions=tuple(REGIONS), stages=tuple(STAGES),
    fixed=FIXED, unit=UNIT, opex=OPEX,
    legacy_cap=LEGACY_CAP, legacy_ret=LEGACY_RET,
    eta_ceil=ETA_CEIL, eta_base=ETA_BASE, alpha=ALPHA, beta=BETA, delta_bar=DELTA_BAR,
    demand_base=DEMAND_BASE, demand_growth=DEMAND_GROWTH, experience0=EXPERIENCE0,
)
nb_struct = build_structure(nb_instance, blocks=BLOCKS, dr=DR, life=LIFE, lead=LEAD,
                            cap_min=CAP_MIN, cap_max=CAP_MAX,
                            legacy_byr=LEGACY_BYR, eta_floor=ETA_FLOOR)

packaged = best_response_fixed_price(
    FIRM, rival_sales, nb_struct,
    learning='both', mipgap=MIPGAP_PLAN,
    transport=TRANSPORT, pen_dispose=PEN_DISPOSE, price_fixed=PRICE_FIXED,
    capex_curve=(QBP, CBP), learn_stages=LEARN_STAGES,
    tiers=TIERS, n_tiers=N_TIERS, lag_years=LAG_YEARS,
)

rel = abs(packaged.ObjVal - hand_built) / abs(hand_built)
print(f"notebook (section 9.1, by hand): {hand_built:,.9f}")
print(f"package  (lithium.games)       : {packaged.ObjVal:,.9f}")
assert rel < 1e-9, f"notebook and package disagree by {rel:.2e}"
print(f"\nnotebook and package agree to {rel:.1e}")
''')

    M(r"""
## 15. Summary

| Question | Answer |
|---|---|
| Is Part 4a a game? | **No.** One objective function, one decision maker. It is a cooperative bound |
| What shape is the Pareto frontier? | Three discrete allocations for five weights — lumpy investment makes it jump |
| Does moving first pay at a fixed price? | **Yes** — 29.1% to R1, 49.2% to R2, and the two orders reach different equilibria |
| Is the equilibrium unique? | **No.** Reporting one move order would be reporting an artefact |
| What is the cost of rivalry? | **+0.96%** volume-matched, **+34.3%** welfare-inclusive. The naive answer, −8.8%, is impossible |
| Does production learning matter in a game? | **Decisively** — without it neither firm builds anything at all |

### Formulation lessons

- **One constraint can be the whole model.** Part 4b's residual demand cap is 26
  constraints and it carries all of the strategic content.
- **The termination test follows from the type of the strategy.** Discrete build
  plans take exact matching; Part 4c's continuous quantities need a tolerance.
  Using the wrong one either invents cycles or misses them.
- **A cycle is a result, not a bug.** If no pure-strategy equilibrium exists,
  reporting one would be the error.
- **When a comparison violates a bound you can prove, fix the comparison.** Check
  whether the two models are solving the same problem — usually they differ in a
  constraint, not in economics.
- **A weighted-sum scalarisation is a weak tool on a lumpy frontier.** Whole
  regions of it are unreachable by any weight.

### Things to try

- `PRICE_FIXED = 16.0` — a higher price should draw in the capacity that
  under-provision left out, and shrink the welfare-inclusive cost of rivalry
- `WEIGHTS = [0.4, 0.45, 0.5, 0.55, 0.6]` — zoom in on the frontier's flip and
  see whether anything lives between the discrete allocations
- `MAX_ITER = 2` — force a MAX_ITER exit and check the code reports it honestly
  rather than pretending to converge
- In section 2.2, `EXPERIENCE0['R1'] = 500.0` — remove incumbency, and watch
  section 13's asymmetry disappear

### Where this goes next

**Part 4c — Cournot.** Price responds to quantity, so the residual cap disappears
and the rivalry runs through the price itself. That single change removes the
under-provision this notebook measured, and largely dissolves the first-mover
advantage it just found — from 29.1% to 4.4%.
""")

    return out

"""Build notebooks/00_concepts.ipynb.

**Subject:** the concepts guide. Twenty-three short sections, each a markdown
explanation followed by one runnable demo that fits on a screen.

**This notebook is the template, and its cells are transcribed rather than
rewritten.** `CLAUDE.md` Part 11 names Part 0 as the shape every other notebook
was converted TOWARD, so retyping it would have risked damaging the reference
while gaining nothing. A script did the transcription and a round-trip check
proved the cells came across unchanged; only two things were edited by hand:

- the front matter gains a Colab badge and the shared setup section, so it opens
  the same way every other notebook in the series does;
- **section 23 is corrected.** It printed a hardcoded observation about what
  happens at iteration 2 of the Best Response Intersection loop. Measured across
  all 120 orderings of the five arcs: the final value, the fortification set and
  even the iteration count are identical every time, but the intermediate trace
  takes one of TWO forms, and the claim about iteration 2 holds in only one of
  them. The fix is the Code Standard, Part 6's second remedy -- assert the invariants,
  teach the degeneracy.

**This notebook has no agreement assertion, and that is the documented
exception.** It builds nothing the package holds: its demos are deliberately
tiny, hand-solved illustrations of a concept, not implementations of a model.
There is no second copy for it to disagree with.
"""
from . import common

NOTEBOOK = "00_concepts.ipynb"
TITLE = "Part 0 - Concepts guide"

# The documented exception to the Code Standard, Part 4's agreement assertion. Stated
# here so `build.py --check` reports it, and repeated in the notebook's own
# front matter so a reader meets it too.
NO_AGREEMENT_ASSERTION = (
    "Part 0 builds nothing the package holds. Its demos are deliberately tiny "
    "hand-solved illustrations of a concept - a four-item knapsack, a two-scenario "
    "hedge, a five-arc network - not implementations of any model in src/lithium. "
    "There is no second copy for it to disagree with, so an agreement assertion "
    "would have nothing to assert."
)


def cells():
    out = []

    def M(text):
        out.append(("md", text.strip("\n")))

    def C(text):
        out.append(("code", text.strip("\n")))

    _front = []

    def _M(text):
        _front.append(("md", text.strip("\n")))

    _M(r"""
# Part 0 — Concepts guide

### The operations research behind Parts 1 to 5, one idea at a time

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/sear-labs/advopt-lithiumsc/blob/main/notebooks/00_concepts.ipynb)

**This is a reference, not a model.** Each section states one concept, says where
it shows up in the series, and then demonstrates it on numbers small enough to
check by hand. Nothing here takes more than a few seconds to run and most of it
needs no solver at all.

**It is also the template.** Every other notebook in this series was converted
*toward* this shape: one idea per section, a markdown explanation above every
code cell, and a demo short enough to read without scrolling. If you are writing
teaching code of your own, this is the pattern.

**There is no agreement assertion at the end of this notebook, and that is
deliberate.** Every other notebook ends by importing `lithium` and checking that
its hand-built model matches the package's to 1e-9. This one has nothing to
compare against: its demos are tiny illustrations of a concept, not
implementations of a model, so there is no second copy to disagree with.
""")

    out += _front
    out += common.setup_section(notebook=NOTEBOOK)

    M(r"""
# Part 0 — Concepts Guide

### The operations research behind Parts 1–4f, one idea at a time

This notebook is a reference, not a model. Each section states a concept, says why it appears in
the supply chain notebooks, defines every symbol it uses, works a small numeric example you can
check on paper, and where useful demonstrates it in a few lines of code you can run and break.

**Who this is written for.** Someone about four weeks into a first optimization course. You know
what an *objective function*, a *decision variable*, a *constraint*, and a *parameter* are. You
have probably seen the simplex method described. Everything past that — relaxations, duality,
branch and bound, stochastic programming, games — is defined here when it first appears.

**How to use it.** Read §0 first; it is the key to the notation and the vocabulary. After that the
sections are independent — go to the one matching the notebook you are reading. Every section has
a **By hand** block with small numbers. Do not skip those: they are the fastest way to see what an
equation is actually doing.

| § | Concept | Where it shows up |
|---|---|---|
| **0** | **How to read this guide: notation, symbols, vocabulary** | **start here** |
| 1 | LP vs MILP, and why integrality is hard | facility siting everywhere |
| 2 | LP relaxation, MIP gap, bounds | every solve |
| 3 | Big-M and why tightness matters | build/size linking |
| 4 | Semi-continuous variables | Part 3 sizing |
| 5 | Piecewise linearization and **SOS2** | learning curves |
| 6 | Disjunctive constraints (indicator tiers) | Part 3b opex learning |
| 7 | Learning curves: capacity vs production | Parts 3 and 3b |
| 8 | Discounting, CRF, annualization | all parts |
| 9 | Vintage indexing | efficiency everywhere |
| 10 | Variable-length periods | Part 3 onward |
| 11 | Scenario trees and nonanticipativity | Part 2 |
| 12 | EVPI and VSS | Part 2 |
| 13 | Progressive hedging | Part 2 |
| 14 | Benders / L-shaped decomposition | Part 2b, Part 3 design |
| 15 | Piecewise linearization revisited: curvature **and** direction | Part 4c |
| 16 | Games: best response, Nash, first-mover advantage | Part 4b, 4c |
| 17 | Cournot and endogenous price | Part 4c |
| 18 | Bilevel programs, KKT, and MPECs | Part 4d |
| 19 | Linearizing products of variables | Part 4d |
| 20 | Comparing models that solve different problems | Part 4a/4b |
| 21 | Risk measures: VaR and CVaR | Part 2c |
| 22 | Max-flow / min-cut and network interdiction | Part 4f |
| 23 | Trilevel programs and Best Response Intersection | Part 4f |
""")
    C(r'''
# Setup. Run this once. Most demos below are plain Python; only a few need the solver.
try:
    import gurobipy as gp
    from gurobipy import GRB
    HAVE_GUROBI = True
    print("gurobipy", gp.gurobi.version())
except Exception as e:                      # noqa: BLE001
    HAVE_GUROBI = False
    print("gurobipy unavailable (%s) - solver demos will be skipped" % type(e).__name__)

import math
from itertools import combinations
print("ready")
''')
    M(r"""
---

# 0. How to read this guide

## 0.1 What you are assumed to know, and what gets defined here

**Assumed** (a first course, week 4):

- An **optimization model** has an objective function, decision variables, and constraints.
- A **parameter** is a number known before you solve. A **decision variable** is a number the
  solver chooses. *This distinction is the single most important thing on the page* — most
  confusion when reading a formulation is a symbol you have mis-sorted into the wrong bin.
- "Linear" means every term is a constant times a variable, added up. No $x^2$, no $x \cdot y$,
  no $\log x$.

**Defined here as they arise** — you are not expected to know these yet:

feasible region · convex · vertex · relaxation · bound · incumbent · MIP gap · duality ·
shadow price · complementary slackness · NP-hard · certificate · epigraph · scenario ·
nonanticipativity · Nash equilibrium · bilevel · KKT conditions.
""")
    M(r"""
## 0.2 The notation rules used throughout

Formulations look impenetrable mostly because the reader cannot tell which symbols are *known*
and which are *unknown*. This guide follows one rule, and states the exceptions.

| Kind | Looks like | Examples | What it means |
|---|---|---|---|
| **Set** | script capital | $\mathcal{A}, \mathcal{P}, \mathcal{S}, \mathcal{K}$ | a collection you sum or loop over |
| **Index** | lowercase, in a subscript | $a, p, s, k, t, v, j$ | picks one member out of a set |
| **Parameter** | UPPERCASE Latin, or Greek | $M,\; Q_k,\; \kappa_a,\; \pi_s,\; \delta_t,\; \rho$ | a number you supply before solving |
| **Variable** | lowercase Latin | $x,\; y,\; c,\; q,\; f$ | a number the solver chooses |

**Decorations.** $\bar{x}$ is an upper bound on $x$; $\underline{x}$ is a lower bound;
$\hat{x}$ is a value *fixed* from some earlier solve (so it is a parameter now, even though it is
a variable elsewhere); $x^{*}$ is an optimal value.

**The Greek exceptions.** A handful of *variables* are traditionally Greek, and renaming them
would make this guide disagree with every paper you go on to read. These eight are variables:

$$\lambda_k \;(\S5) \quad \theta \;(\S14,\S23) \quad \eta \;(\S21) \quad \mu \;(\S18)
\quad \gamma_a,\; u_n \;(\S22) \quad \zeta_a,\; \phi_a \;(\S23)$$

**Operators.**

| Symbol | Read it as |
|---|---|
| $\sum_{k \in \mathcal{K}}$ | "add up, over every $k$ in the set $\mathcal{K}$" |
| $\forall a \in \mathcal{A}$ | "this line is repeated once for every $a$ in $\mathcal{A}$" |
| $y \in \{0,1\}$ | "$y$ may only take the values 0 or 1" |
| $\min_x f(x)$ | the smallest *value* $f$ attains |
| $\arg\min_x f(x)$ | the *$x$* that attains it — a decision, not a cost |
| $(w)^{+}$ | $\max(w, 0)$ — "the positive part", used for shortfalls |
| $\mathbb{E}[\,\cdot\,]$ | probability-weighted average: $\sum_s \pi_s (\cdot)_s$ |
| $\lVert v \rVert^2$ | $\sum_i v_i^2$ — squared distance |
| $\nabla_x f$ | vector of partial derivatives of $f$ with respect to each $x_i$ |
| $v^{\top} x$ | $\sum_i v_i x_i$ |

---

### Reading one equation out loud

$$x_{a,p} \;\le\; M\, y_{a,p} \qquad \forall\, a \in \mathcal{A},\; p \in \mathcal{P}$$

- $x_{a,p}$ — lowercase, so a **variable**: flow on arc $a$ during period $p$. Two subscripts
  means there is one such variable for *every combination* of arc and period.
- $\le$ — this is a **constraint**, a restriction the solver must respect. It is not an
  assignment and not a definition.
- $M$ — uppercase, so a **parameter**: a fixed number you pick before solving (§3).
- $y_{a,p}$ — a **variable**, binary, "is arc $a$ open in period $p$".
- $\forall a \in \mathcal{A},\, p \in \mathcal{P}$ — with 27 arcs and 6 periods, **this one
  printed line is 162 separate constraints**. Formulations are compact because of this
  quantifier, and model files are large for the same reason.

### And a second one

$$Q \;=\; \sum_{k \in \mathcal{K}} Q_k\, \lambda_k$$

$k$ indexes breakpoints, $\mathcal{K} = \{0,1,2,3,4\}$; $Q_k$ is a **parameter** (where the
$k$-th breakpoint sits); $\lambda_k$ is a **variable** (how much weight the solver puts there).
Written out, with the numbers used in §5:

$$Q \;=\; 0\lambda_0 + 100\lambda_1 + 200\lambda_2 + 300\lambda_3 + 400\lambda_4$$

One equation, five variables, and $Q$ ends up being a weighted average of five fixed locations.
""")
    M(r"""
## 0.3 Master symbol table

Every symbol used in this guide, in one place. Each section also repeats the ones it needs.

### Indices and sets

| Symbol | Meaning | § |
|---|---|---|
| $t$ | a single **year** | 8, 10 |
| $p$ | a **period** — a block of one or more years | 8, 10 |
| $v$ | a **vintage** — the period an asset was built in | 9 |
| $s \in \mathcal{S}$ | a **scenario** (one possible future) | 11–14, 21 |
| $k \in \mathcal{K}$ | a **breakpoint** of a piecewise-linear curve | 5, 15 |
| $j$ | a **tier** (§6) or a **retained attack** (§23) | 6, 23 |
| $a \in \mathcal{A}$ | an **arc** of the network | 22, 23 |
| $n \in \mathcal{N}$ | a **node** of the network | 22 |
| $f$ | a **firm** (Part 4) | 16, 17 |

### Parameters

| Symbol | Meaning | § |
|---|---|---|
| $M$ | "big-M" — a deliberately large constant used to switch a constraint on or off | 3, 6, 18 |
| $\underline{c},\ \bar{c}$ | minimum and maximum buildable facility size | 4 |
| $Q_k,\ F_k$ | location and height of breakpoint $k$ | 5 |
| $T_j,\ m_j$ | upper threshold and unit cost of learning tier $j$ | 6 |
| $LR,\ B_{\text{lc}},\ U_0,\ Q_0$ | learning rate, learning exponent, anchor cost and anchor volume | 7 |
| $\rho$ | **discount rate** (e.g. 0.05) | 8, 10 |
| $\delta_t$ | discount factor for year $t$, $=(1+\rho)^{-t}$ | 8, 10 |
| $\omega_p$ | money weight of period $p$, $=\sum_{t \in p}\delta_t$ | 10 |
| $L_p$ | length of period $p$ in years | 10 |
| $\Lambda$ | asset life in years | 8 |
| $\text{CRF}$ | capital recovery factor | 8 |
| $\bar\eta,\ G_{\text{new}},\ G_{\text{life}}$ | efficiency ceiling, frontier improvement rate, in-life improvement rate | 9 |
| $\pi_s$ | probability of scenario $s$ | 11–14, 21 |
| $\alpha$ | CVaR tail fraction (e.g. 0.25 = "the worst quarter") | 21 |
| $A,\ B$ | intercept and slope of the inverse demand curve $\text{price}=A-B\,q$ | 17, 18 |
| $\kappa_a$ | capacity of arc $a$ | 22, 23 |
| $\rho_{\text{PH}}$ | progressive-hedging penalty weight | 13 |
| $\Lambda_{\text{mix}}$ | weight on expectation in a hybrid risk objective | 21 |

### Variables

| Symbol | Meaning | § |
|---|---|---|
| $x$ | flow / throughput — a "how much" quantity | 3, 6, 19 |
| $y$ | **binary**, 0 or 1 — a "whether" decision | 1, 3, 4, 6, 19 |
| $c$ | facility capacity (semi-continuous) | 4 |
| $q$ | quantity sold by a firm | 17, 18 |
| $\lambda_k$ | interpolation weight on breakpoint $k$ | 5, 15 |
| $\theta$ | stand-in for a cost/flow that is bounded by cuts (an *epigraph* variable) | 14, 23 |
| $\eta$ | the value-at-risk level, found by the model itself | 21 |
| $z_s$ | cost overshoot above $\eta$ in scenario $s$ | 21 |
| $w_s$ | progressive-hedging multiplier for scenario $s$ | 13 |
| $\mu$ | KKT multiplier on an inequality (a shadow price) | 18 |
| $\gamma_a$ | 1 if arc $a$ is in the chosen cut | 22 |
| $u_n$ | node potential (dual of the flow balance at node $n$) | 22 |
| $\zeta_a$ | 1 if arc $a$ is attacked | 22, 23 |
| $\phi_a$ | 1 if arc $a$ is fortified | 23 |
| $\sigma_a$ | auxiliary variable replacing the product $\gamma_a(1-\zeta_a)$ | 22 |

### Letters that get reused — and how to tell them apart

The literature recycles letters. Where this guide could not avoid it, here is the map.

| Letter | One meaning | The other | This guide writes |
|---|---|---|---|
| $\rho$ | discount rate (§8) | progressive-hedging penalty (§13) | $\rho$ and $\rho_{\text{PH}}$ |
| $\lambda$ | SOS2 interpolation weight (§5) | risk mixing weight (§21) | $\lambda_k$ and $\Lambda_{\text{mix}}$ |
| $\alpha,\beta$ | CVaR tail fraction (§21) | learning rates in Part 3's code | $\alpha$ and $G_{\text{new}}, G_{\text{life}}$ |
| $b$ | learning exponent (§7) | a binary variable in many texts | $B_{\text{lc}}$ and $y$ |
| $\theta$ | Benders recourse cost (§14) | defender's guaranteed flow (§23) | $\theta$ in both — same *role*: a variable squeezed by cuts |
| $\pi$ | scenario probability (§11) | node potential in network duality | $\pi_s$ and $u_n$ |
""")
    M(r"""
## 0.4 Thirteen words you will meet

Short definitions with a number attached, so they mean something concrete.

**Feasible region.** The set of all variable values satisfying every constraint. For
$x_1 + x_2 \le 10,\ x \ge 0$ it is a triangle with corners $(0,0), (10,0), (0,10)$.

**Convex set.** Take any two points in the set; the straight line between them stays inside.
The triangle above is convex. The set $\{0\} \cup [5, 10]$ — "zero, or between 5 and 10" — is
**not**: 0 and 6 are both in it, and their midpoint 3 is not. Non-convexity is what makes a
problem hard, and §1 and §4 are both about deliberately choosing it because the economics
demand it.

**Convex function.** The chord between any two points on the graph lies *on or above* the graph
($x^2$). **Concave** is the reverse — the chord lies on or below ($\sqrt{x}$, and every learning
curve in this project). §5 and §15 turn entirely on this.

**Vertex (corner point).** A corner of the feasible region. An LP optimum can always be found at
one, which is why the simplex method only ever visits corners.

**Relaxation.** The same model with some requirement deleted — usually "integer" (§2) or a
complicating constraint. Deleting a requirement can only help, so a relaxation's optimum is
always at least as good as the true one. That is what makes it a **bound**.

**Bound.** A number you can *prove* the answer is on one side of. For a minimization, a
**lower bound** says "the true cost cannot be below this"; an **upper bound** is any feasible
solution's cost. Optimization is the business of squeezing the two together.

**Incumbent.** The best actual solution found so far — an upper bound for a minimization.

**Certificate.** A bound that comes with a proof, rather than a hope. "Within 1% of optimal" from
branch and bound is a certificate; "the heuristic stopped improving" is not.

**NP-hard.** No algorithm is known that solves every instance in time polynomial in its size, and
finding one would settle a famous open problem. Practically: expect the solve time to blow up on
*some* instances, not necessarily yours.

**Dual variable / shadow price.** Every constraint has an associated number telling you how much
the objective would improve per unit of relaxation of that constraint. If capacity is binding and
its dual is 12, one more unit of capacity is worth 12. Duals are what Benders (§14), MPECs (§18),
and min-cut (§22) are all built on.

**Complementary slackness.** For each constraint, *either* it is tight *or* its dual is zero —
never both nonzero. "If you have spare capacity, extra capacity is worthless." Written
$\mu \cdot (\text{slack}) = 0$ (§18).

**Epigraph variable.** A single variable $\theta$ standing in for a complicated cost, pushed down
by constraints of the form $\theta \ge (\text{some linear function})$. Since you are minimizing
$\theta$, it settles at the largest of those lower bounds. This is the trick behind Benders (§14)
and CVaR (§21).

**Heuristic vs exact.** An exact method returns the optimum *and* a certificate. A heuristic
returns a solution. Progressive hedging on integer problems (§13) is a heuristic; Benders (§14) is
exact. Both are useful; only one lets you write "provably within 0.4%".
""")
    M(r"""
---

# 1. LP vs MILP — where the difficulty comes from

**The idea.** Forcing some variables to be whole numbers turns an easy problem into a hard one,
because it shatters the feasible region into disconnected points.

| Symbol | Meaning | Kind |
|---|---|---|
| $x$ | how much (flow, throughput, size) | variable, continuous |
| $y$ | whether (build or not) | variable, binary |

A **linear program (LP)** minimizes a linear objective over linear constraints with continuous
variables. It solves fast in practice, and the optimum sits at a vertex of the feasible region.

A **mixed-integer linear program (MILP)** forces some variables to be integers. That single change
makes the problem NP-hard, because the feasible set stops being convex — it becomes a lattice of
disconnected points, and you can no longer trust local information to tell you where the optimum
is. In an LP, "no improving direction here" means you are done. In a MILP it means nothing: the
better solution may be a jump away, with worse points in between.

In our supply chain the split is deliberate:

- **Continuous**: flows on arcs, throughput, facility size. These are *how much*.
- **Integer**: whether to build a facility. These are *whether*.

A facility cannot be 0.4 built — it has a fixed cost incurred in full or not at all. That
indivisibility is the entire source of computational difficulty, and it is also the economically
meaningful part.

---

### By hand

Four projects; pick a subset within a budget of 10.

| item $i$ | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| value $V_i$ | 12 | 10 | 8 | 11 |
| cost $W_i$ | 5 | 4 | 3 | 6 |

$$\max \sum_i V_i y_i \quad \text{s.t.} \quad \sum_i W_i y_i \le 10, \quad y_i \in \{0,1\}$$

Only seven subsets fit the budget, so you can enumerate them:

| subset | cost | value |
|---|---|---|
| {1} | 5 | 12 |
| {2} | 4 | 10 |
| {3} | 3 | 8 |
| {4} | 6 | 11 |
| {1,2} | 9 | **22** |
| {1,3} | 8 | 20 |
| {2,3} | 7 | 18 |
| {2,4} | 10 | 21 |
| {3,4} | 9 | 19 |

The optimum is $\{1,2\}$ with value **22** — and note it leaves one unit of budget unused. That is
the lattice at work: there is no way to spend the leftover.

**The relaxation.** Allow $0 \le y_i \le 1$ — fractional projects. Now sort by value per unit of
cost: item 3 gives 2.67, item 2 gives 2.50, item 1 gives 2.40, item 4 gives 1.83. Fill greedily:
take all of 3 (cost 3, 7 left), all of 2 (cost 4, 3 left), then $3/5$ of item 1.

$$8 + 10 + 0.6 \times 12 = \mathbf{25.2}$$

The relaxation says 25.2; the truth is 22. The 3.2 difference is the **integrality gap** — the
price of indivisibility. It is not solver error, and it does not go away with a faster computer.
""")
    C(r'''
# Predict before you run: the LP relaxation of a knapsack. Will its objective
# be higher or lower than the integer optimum, and can you say why before you
# see the numbers?
# The same knapsack, solved twice: with and without integrality.
if HAVE_GUROBI:
    value  = [12, 10, 8, 11]
    weight = [5,   4,  3,  6]
    cap    = 10

    k = gp.Model(); k.Params.OutputFlag = 0
    take = k.addVars(4, vtype=GRB.BINARY)
    k.addConstr(gp.quicksum(weight[i]*take[i] for i in range(4)) <= cap)
    k.setObjective(gp.quicksum(value[i]*take[i] for i in range(4)), GRB.MAXIMIZE)
    k.optimize()
    mip = k.ObjVal

    rel = k.relax(); rel.Params.OutputFlag = 0; rel.optimize()   # note: relax() after optimize()
    print(f"LP relaxation (upper bound for a max problem): {rel.ObjVal:.3f}")
    print(f"MILP optimum                                : {mip:.3f}")
    print(f"integrality gap                             : {rel.ObjVal - mip:.3f}")
    print("\nMILP solution      :", [round(v.X, 3) for v in k.getVars()])
    print("fractional LP soln :", [round(v.X, 3) for v in rel.getVars()])
else:
    print("skipped - needs gurobipy")

# Warning worth internalising: Model.relax() called before Model.update() returns an EMPTY
# model. It solves to 0, reports OPTIMAL, and passes any test written against it.
''')
    M(r"""
---

# 2. LP relaxation, bounds, and what a "1% MIP gap" actually guarantees

**The idea.** A solver does not find the optimum and stop; it squeezes a lower bound up against
an upper bound until the two are close enough. The MIP gap is the width of that squeeze.

| Symbol | Meaning |
|---|---|
| incumbent | objective value of the best *feasible* solution found so far |
| best bound | best objective value still achievable in any unexplored branch |

Drop the integrality requirement and you get the **LP relaxation**. Because it is less
constrained, for a minimization its optimum is **always $\le$** the true MILP optimum — a *lower
bound*. (For a maximization it is always $\ge$: an upper bound. Same idea, flipped.)

**Branch and bound** works between two numbers. It picks a fractional variable — say $y_3 = 0.6$ —
and splits the problem into $y_3 = 0$ and $y_3 = 1$, solving the relaxation of each. Any branch
whose relaxation is already worse than the incumbent can be discarded whole, unexplored. That
*pruning* is the whole algorithm.

- **Incumbent** (upper bound for a min): the best integer-feasible solution found so far.
- **Best bound** (lower bound for a min): the best relaxation value over unexplored branches.

$$\text{MIP gap} = \frac{\lvert \text{incumbent} - \text{best bound}\rvert}{\lvert\text{incumbent}\rvert}$$

Terminating at a 1% gap is a **guarantee**: the true optimum is no more than 1% better than what
you have. That is genuinely useful — and it is also why chasing 0.01% is usually false precision
when your learning rate is a guess.

---

### By hand

Continuing §1's knapsack. Suppose branch and bound has found $\{1,2\}$ (value 22) and the best
remaining relaxation is 25.2:

$$\text{gap} = \frac{25.2 - 22}{22} = 14.5\%$$

Not good enough to stop. It branches further, the bound drops to 23:

$$\text{gap} = \frac{23 - 22}{22} = 4.5\%$$

and when every branch has been pruned the bound reaches 22 and the gap is 0. Notice the
*incumbent never moved*: the solver had the optimal answer at the very first step and spent all
its remaining effort **proving** it. That is typical, and it is why "time to optimality" and
"time to the answer" are different numbers.

### The rolling-horizon trap

One consequence that matters in Part 1: a *sequence* of 1%-gap solves in a rolling horizon gives
you **no** overall bound. Five rolls, each within 1%, compound to

$$1.01^5 - 1 = 5.1\%$$

in the worst case — and that is only the bound arithmetic, ignoring that a suboptimal early
decision changes what the later problems even are. A single perfect-foresight solve at 1% does
give you a bound on the whole answer.
""")
    M(r"""
---

# 3. Big-M, and why a loose M is the most expensive mistake in facility location

**The idea.** To make a constraint apply only when a switch is on, multiply the switch by a big
number. How big you make it decides how long your model takes to solve.

| Symbol | Meaning | Kind |
|---|---|---|
| $x$ | flow through the facility | variable, continuous |
| $y$ | 1 if the facility is built | variable, binary |
| $M$ | a constant at least as large as $x$ can ever be | **parameter — you choose it** |

To say "flow is only allowed if the facility is built" you write

$$x \le M y, \qquad y \in \{0,1\}$$

With $y=0$ this forces $x \le 0$; with $y=1$ it permits $x$ up to $M$. **$M$ must be large enough
never to wrongly restrict a feasible solution, and no larger.**

Why tightness matters: branch and bound only ever sees the *relaxation*, where $y$ may be
fractional. At $y = 0.5$ the constraint permits $x \le M/2$. A huge $M$ therefore permits a huge
$x$ at a tiny fractional $y$ — the model buys a facility for a fraction of a cent, the lower bound
collapses, and the search tree explodes.

In Part 3 the bound is `CAP_MAX` — the actual maximum facility size — not a generic $10^9$. If a
node genuinely cannot exceed some capacity, use that number.

---

### By hand

Ship at least 200 units. Building costs 1500; shipping costs 2 per unit; the site can hold at
most 260.

$$\min\; 1500 y + 2x \quad\text{s.t.}\quad x \ge 200,\;\; x \le 260,\;\; x \le My,\;\; y \in \{0,1\}$$

**True answer:** you must ship, so $y=1$, $x=200$, cost $1500 + 400 = 1900$.

**Now the relaxation**, with $0 \le y \le 1$. The constraint $x \le My$ rearranges to
$y \ge x/M$, so the solver buys the smallest fraction of a facility it can get away with:

| $M$ | forced $y$ | fixed cost paid | relaxation value | as % of 1900 |
|---|---|---|---|---|
| 260 (tight) | $200/260 = 0.769$ | 1153.8 | **1553.8** | 82% |
| 1,000,000 (lazy) | $200/10^6 = 0.0002$ | 0.3 | **400.3** | 21% |

Identical integer solutions. Identical optimum. But the lazy $M$ hands branch and bound a lower
bound of 400 when the answer is 1900 — it has to close a factor of nearly five by branching,
where the tight $M$ starts 82% of the way there.

**Rule of thumb:** every big-M in your model should trace back to a physical quantity you can
name. If you cannot say what $M$ *is*, it is too big.
""")
    C(r'''
# Same feasible integer set, two values of M. Compare the LP relaxation bounds.
if HAVE_GUROBI:
    for M in [260, 1_000_000]:
        t = gp.Model(); t.Params.OutputFlag = 0
        y = t.addVar(vtype=GRB.BINARY); x = t.addVar(ub=260)
        t.addConstr(x <= M * y)
        t.addConstr(x >= 200)                      # must ship at least 200
        t.setObjective(1500*y + 2*x, GRB.MINIMIZE) # fixed cost + variable
        t.optimize()
        r = t.relax(); r.Params.OutputFlag = 0; r.optimize()
        print(f"M = {M:>9,}   MILP = {t.ObjVal:8.1f}   LP bound = {r.ObjVal:8.1f}"
              f"   bound quality = {100*r.ObjVal/t.ObjVal:5.1f}%")
else:
    print("skipped - needs gurobipy")
''')
    M(r"""
The tight $M$ gives an LP bound close to the true optimum. The loose $M$ lets the relaxation
buy a facility at a fraction of a cent, so the bound collapses. Identical integer solutions,
wildly different search effort.
""")
    M(r"""
---

# 4. Semi-continuous variables

**The idea.** Some quantities are "zero, or big enough to be worth it" — never in between. That
is not a continuous variable and not an integer one.

| Symbol | Meaning | Kind |
|---|---|---|
| $c$ | facility capacity | variable, semi-continuous |
| $y$ | 1 if the facility is built | variable, binary |
| $\underline{c}$ | smallest facility worth building | parameter |
| $\bar{c}$ | largest facility the site allows | parameter |

$$c = 0 \quad\text{or}\quad \underline{c} \le c \le \bar{c}$$

Encoded with one binary:

$$c \le \bar{c}\,y, \qquad c \ge \underline{c}\,y, \qquad y \in \{0,1\}$$

Check both branches: $y=0$ gives $0 \le c \le 0$, so $c=0$. $y=1$ gives
$\underline{c} \le c \le \bar{c}$. Nothing else is reachable — and *that gap is exactly the
non-convexity* from §0.4.

This is how Part 3 sizes facilities, and it is strictly better than the "integer count of
fixed-size units" approach in Parts 1–2:

| | Integer count × fixed size | Semi-continuous |
|---|---|---|
| Binaries per site-period | one per candidate unit | **one** |
| Attainable capacities | multiples of the unit | **continuous** in range |

Fewer integer variables *and* a finer decision space. The lower bound $\underline{c}$ matters:
without it the model dodges the fixed cost by building something infinitesimally small — capacity
0.0001 at a cost of nothing, which is arithmetically valid and physically absurd.

Gurobi also has `vtype=GRB.SEMICONT` natively, but the explicit binary is clearer for teaching and
is needed anyway to charge a fixed cost.

---

### By hand

Site limits: $\underline{c} = 50$, $\bar{c} = 260$. Demand needing service: 130.

| formulation | reachable capacities | what you build for demand 130 | wasted |
|---|---|---|---|
| integer count of 50-unit modules | 0, 50, 100, 150, 200, 250 | 150 (three modules) | **20** |
| semi-continuous | 0, or anything in [50, 260] | **130** | 0 |
| plain continuous $c \ge 0$ | anything $\ge 0$ | 130 | 0, but... |

The third row is the trap. With plain continuous capacity and a fixed cost charged as
$\text{FIX} \cdot y$, nothing links $c$ to $y$, so the model sets $y=0$, pays no fixed cost, and
builds 130 anyway. The two constraints above are what stop it.
""")
    M(r"""
---

# 5. Piecewise linearization and SOS2 — the one to understand properly

**The idea.** You can put a curve into a linear model by pinning it to a few points and letting
the solver interpolate between them — but unless you force it to use *neighbouring* points, it
will cheat.

| Symbol | Meaning | Kind |
|---|---|---|
| $\mathcal{K}$ | the set of breakpoints, here $\{0,1,2,3,4\}$ | set |
| $Q_k$ | where breakpoint $k$ sits on the horizontal axis | parameter |
| $F_k$ | the true value $f(Q_k)$, computed before solving | parameter |
| $\lambda_k$ | weight the solver puts on breakpoint $k$ | **variable** |
| $Q, F$ | the interpolated point and its value | variables |

To put a nonlinear function $f(Q)$ into a linear model, pick breakpoints $Q_0 \ldots Q_K$,
precompute $F_k = f(Q_k)$, and interpolate:

$$Q = \sum_k Q_k \lambda_k, \qquad F \approx \sum_k F_k\lambda_k,
\qquad \sum_k \lambda_k = 1, \quad \lambda_k \ge 0$$

Because the $\lambda$'s are non-negative and sum to one, $(Q, F)$ is a weighted average of the
breakpoints — it lands somewhere inside the polygon they trace out.

**And that is the bug.** With $\lambda$ free, the model can put weight on non-adjacent
breakpoints — mixing $\lambda_0$ and $\lambda_4$, say — which evaluates the function on the
straight *chord* between them rather than on the curve.

Whether that is a problem depends on curvature and direction:

| | Minimizing | Maximizing |
|---|---|---|
| **Convex** $f$ | chord lies above — no incentive, safe | chord exploited |
| **Concave** $f$ | **chord lies below — exploited** | safe |

Our cumulative learning-curve cost is **concave increasing** and we **minimize**, so we are in the
dangerous cell: the LP would ride the chord and claim a cost reduction it never earned.

**SOS2** (special ordered set of type 2) is the fix: at most two variables in the set may be
nonzero, **and they must be adjacent**. That forces interpolation along an actual segment of the
curve. Gurobi handles it natively via `addSOS`, branching on the set rather than needing extra
binaries.

---

### By hand

A concave increasing curve — rising, then flattening:

| $k$ | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| $Q_k$ | 0 | 100 | 200 | 300 | 400 |
| $F_k$ | 0 | 60 | 100 | 130 | 150 |

Require $Q \ge 200$ and minimize $F$. The true answer is $f(200) = 100$.

**What the solver does without SOS2.** It wants the smallest $F$ consistent with $Q = 200$, so it
mixes the two *end* points:

$$\lambda_0 = 0.5,\ \lambda_4 = 0.5 \;\Longrightarrow\;
Q = 0.5(0) + 0.5(400) = 200 \;\checkmark, \qquad
F = 0.5(0) + 0.5(150) = \mathbf{75}$$

It reports 75 for something that costs 100 — a **25% phantom discount**, from a model that is
feasible, optimal, and completely wrong.

**With SOS2** only adjacent pairs are allowed. To hit $Q = 200$ exactly it must use $\lambda_2 = 1$,
giving $F = 100 \;\checkmark$. At $Q = 250$ it would use $\lambda_2 = \lambda_3 = 0.5$, giving
$F = (100 + 130)/2 = 115$ — on the chord of a *neighbouring* pair, which is the approximation you
signed up for.

> **Predict before you run.** The cell below minimises that concave cost with a
> free convex combination and then again with SOS2. Which of the two reports the
> lower number, and which of the two is telling the truth?
""")
    C(r'''
# Predict before you run: this minimises a CONCAVE cost with a free convex
# combination of breakpoints. Does it report a cost above, below, or equal to
# the true one? Write your answer down, then look.
# Concave increasing f. Minimize f subject to a lower bound on Q, with and without SOS2.
if HAVE_GUROBI:
    QB = [0, 100, 200, 300, 400]
    FB = [0,  60, 100, 130, 150]        # concave: rising, flattening

    for use_sos in [False, True]:
        d = gp.Model(); d.Params.OutputFlag = 0
        lam = d.addVars(len(QB), lb=0, ub=1)
        Q   = d.addVar(); F = d.addVar()
        d.addConstr(lam.sum() == 1)
        d.addConstr(Q == gp.quicksum(QB[k]*lam[k] for k in range(len(QB))))
        d.addConstr(F == gp.quicksum(FB[k]*lam[k] for k in range(len(QB))))
        d.addConstr(Q >= 200)           # we must reach Q = 200
        if use_sos:
            d.addSOS(GRB.SOS_TYPE2, [lam[k] for k in range(len(QB))])
        d.setObjective(F, GRB.MINIMIZE)
        d.optimize()
        nz = {k: round(lam[k].X, 3) for k in range(len(QB)) if lam[k].X > 1e-6}
        print(f"SOS2={str(use_sos):5s}  F = {F.X:6.2f}   (true f(200) = 100)   lambda = {nz}")
else:
    print("skipped - needs gurobipy")
''')
    M(r"""
Without SOS2 the model mixes breakpoints 0 and 4, reports a cost **below** the true value, and the
$\lambda$ pattern shows exactly how it cheated. With SOS2 it is pinned to the adjacent pair and
returns the correct 100.

**Diagnostic to run on any real model:** print the nonzero $\lambda$ per period.

| what you see | what it means |
|---|---|
| two adjacent nonzeros | the curve is doing real work |
| one nonzero | you have built a step function — the mesh is too coarse |
| non-adjacent nonzeros | SOS2 is not being enforced. Stop and fix it |

**And check breakpoint placement.** If the mesh spans far beyond where the solution actually
lands, the chords are coarsest exactly where it matters. Part 3's mesh ran to 1,400 while the
solution reached 1,174 — three of nine breakpoints never used. Solve once, read the realized
range, then re-mesh; the objective *rose* slightly, confirming the coarse mesh had been
understating a concave cost.
""")
    M(r"""
---

# 6. Disjunctive constraints — when SOS2 is not available

**The idea.** When the thing driving a curve is not the thing being multiplied by it, SOS2 stops
working and you fall back to "pick a tier with a binary, and charge a constant within the tier."

| Symbol | Meaning | Kind |
|---|---|---|
| $j \in \mathcal{J}$ | learning tier | index |
| $T_{j-1}, T_j$ | lower and upper cumulative-production threshold of tier $j$ | parameter |
| $m_j$ | unit cost that applies inside tier $j$ | parameter |
| $y_{p,j}$ | 1 if period $p$ sits in tier $j$ | variable, binary |
| $x_p$ | throughput in period $p$ | variable |
| $x_{p,j}$ | the slice of $x_p$ charged at tier $j$'s rate | variable |
| $q^{lag}_p$ | cumulative production *before* period $p$ | variable |
| $\bar{x}$ | largest possible throughput | parameter |

SOS2 works in Part 3 because the curve's argument (cumulative **capacity**) is the same quantity
being paid for, so the interpolated cumulative cost enters the objective directly.

Part 3b breaks that. Operating cost learning depends on cumulative **production**, while the cost
applies to *current* throughput. Naively you would write

$$\text{cost} = \underbrace{U(q^{lag}_p)}_{\text{a variable}} \times
\underbrace{x_p}_{\text{another variable}}$$

which is **bilinear** — a variable times a variable. Not linear, not convex, and outside SOS2's
reach (§19 explains why this class is genuinely hard).

The fix is a **disjunctive** formulation — "disjunctive" meaning the feasible set is an *or* of
several pieces. Discretize learning into tiers, use one binary per tier to select which applies,
and split throughput across tiers so each piece meets a *constant* multiplier:

$$\sum_j y_{p,j} = 1, \qquad y_{p,j} \in \{0,1\}$$
$$q^{lag}_p \ge T_{j-1} - M(1 - y_{p,j}), \qquad q^{lag}_p \le T_j + M(1 - y_{p,j})$$
$$\sum_j x_{p,j} = x_p, \qquad x_{p,j} \le \bar{x}\, y_{p,j}, \qquad
\text{cost} = \sum_j m_j\, x_{p,j}$$

Read the middle line as: *if* $y_{p,j} = 1$ the two bounds bite and cumulative production must lie
in tier $j$; if $y_{p,j} = 0$ the $M$ term makes them vacuous. Now every product is (constant ×
variable). Linear.

The cost is real: more binaries than SOS2, a weaker relaxation from the big-Ms, and the
approximation is a step function rather than a piecewise-linear curve — so expect some
**bunching** at thresholds. This is a case where you accept a cruder, more expensive formulation
because the exact one is unavailable.

---

### By hand

Two tiers. Below 100 cumulative units, operating cost is 10/unit; at or above 100, it is 8/unit.
Take $M = 1000$ and $\bar{x} = 200$.

| | $T_{j-1}$ | $T_j$ | $m_j$ |
|---|---|---|---|
| tier 1 | 0 | 100 | 10 |
| tier 2 | 100 | 1000 | 8 |

Say the model has $q^{lag}_p = 120$ and wants throughput $x_p = 60$.

**Check tier 1** ($y_{p,1}=1$): needs $120 \le T_1 = 100$. False — so $y_{p,1}$ cannot be 1.

**Check tier 2** ($y_{p,2}=1$): needs $120 \ge 100$ ✓ and $120 \le 1000$ ✓. Selected.

Then $x_{p,1} \le \bar{x} \cdot 0 = 0$ forces the whole 60 into the second slice,
$x_{p,2} = 60$, and

$$\text{cost} = 10(0) + 8(60) = \mathbf{480}$$

against 600 at the untaught rate. Notice what the tiers cost you in fidelity: at $q^{lag} = 99$
the model charges 600 and at $q^{lag} = 100$ it charges 480, a cliff where the true curve has a
smooth slope. That is the **bunching** — solutions pile up just past a threshold.
""")
    M(r"""
---

# 7. Learning curves: what accumulates matters

**The idea.** Things get cheaper as you make more of them. *Which* "more" you write down —
calendar years, capacity built, or units actually produced — changes what the model decides.

| Symbol | Meaning | Kind |
|---|---|---|
| $LR$ | learning rate: fractional cost drop per doubling (0.20 = 20%) | parameter |
| $B_{\text{lc}}$ | learning exponent, $= -\log_2(1-LR)$ | parameter |
| $U_0$ | unit cost at the anchor volume | parameter |
| $Q_0$ | anchor cumulative volume | parameter |
| $U(Q)$ | unit cost at cumulative volume $Q$ | derived function |
| $C(Q)$ | *cumulative* cost of producing up to $Q$ | derived function |

**Wright's law.** Unit cost falls by a fixed fraction for every doubling of cumulative output:

$$U(Q) = U_0 \left(Q/Q_0\right)^{-B_{\text{lc}}}, \qquad B_{\text{lc}} = -\log_2(1 - LR)$$

Always floor it — real curves flatten, and an unfloored power law eventually gives away the
technology.

**Three modelling choices that are often conflated:**

| Driver | Represents | Consequence |
|---|---|---|
| **Calendar time** (exogenous) | cost falls whether or not you build | *Free lunch.* Biases toward waiting |
| **Cumulative capacity** | learning by building | Must be earned, but idle plants still learn |
| **Cumulative production** | learning by doing | Must build **and** run |

Production-based is the most faithful to the original empirical work, and it is the only one under
which "flood the market to drive down your own future costs" is a rational strategy — which is why
Part 4's predatory dynamics need it.

**Linearize the *cumulative* cost, not the unit cost.** You need
$C(Q) = \int_{Q_0}^{Q} U(q)\,dq$, then charge increments $C_p - C_{p-1}$. Interpolating unit cost
and multiplying by capacity reintroduces the bilinear term of §6.

**Endogenous learning needs foresight.** A myopic or rolling-horizon model has little reason to
overbuild early to buy down a curve, because it cannot see the payoff. Endogenous learning belongs
in a perfect-foresight formulation.

---

### By hand

$LR = 0.20$, so $B_{\text{lc}} = -\log_2(0.80) = 0.3219$. Anchor: $U_0 = 10$ at $Q_0 = 400$.

| cumulative $Q$ | doublings from $Q_0$ | $U(Q)$ | check |
|---|---|---|---|
| 400 | 0 | 10.00 | anchor |
| 800 | 1 | 8.00 | $10 \times 0.8$ |
| 1600 | 2 | 6.40 | $10 \times 0.8^2$ |
| 3200 | 3 | 5.12 | $10 \times 0.8^3$ |

**Why "cumulative cost, not unit cost" matters.** Going from 400 to 800 units, what do those 400
units cost?

| accounting | arithmetic | total |
|---|---|---|
| charge the *starting* unit cost | $10 \times 400$ | 4000 — too high |
| charge the *ending* unit cost | $8 \times 400$ | 3200 — too low |
| the integral $\int_{400}^{800} U(q)\,dq$ | — | **3539** |

The first two are wrong by $+13\%$ and $-10\%$ on a *single* doubling, and the error grows with
the learning rate. The middle column is what your model charges if you interpolate $U$ and
multiply by volume — the bilinear shortcut of §6. The integral is
what you should linearize with §5's machinery — it is the concave increasing curve of that
section, which is exactly why SOS2 was needed there.
""")
    C(r'''
LR, Q0, U0 = 0.20, 400.0, 10.0
b = -math.log2(1 - LR)
print(f"LR = {LR:.0%}  ->  b = {b:.4f}\n")
for q in [400, 800, 1600, 3200]:
    print(f"  Q = {q:5d}  ({q//400} x Q0)   unit cost = {U0*(q/Q0)**(-b):6.3f}"
          f"   ratio to start = {(q/Q0)**(-b):.3f}")

# Cumulative cost from 400 to 800, three ways.
exact = U0*Q0**b*(800**(1-b) - 400**(1-b))/(1-b)
print(f"\ncharge start unit cost : {U0*400:8.1f}   (+{100*(U0*400/exact-1):.1f}%)")
print(f"integral (correct)     : {exact:8.1f}")
print(f"charge end unit cost   : {8.0*400:8.1f}   ({100*(8.0*400/exact-1):.1f}%)")
''')
    M(r"""
---

# 8. Discounting, CRF, and annualization

**The idea.** A dollar later is worth less than a dollar now, and how you spread a lump-sum
construction cost across the years decides whether your model is willing to build near the end of
its horizon.

| Symbol | Meaning | Kind |
|---|---|---|
| $\rho$ | discount rate per year (e.g. 0.05) | parameter |
| $t$ | year index | index |
| $\delta_t$ | discount factor for year $t$ | derived parameter |
| $\Lambda$ | asset life in years | parameter |
| $\text{CRF}$ | capital recovery factor | derived parameter |

$$\delta_t = (1+\rho)^{-t}$$

**The discount rate sets the effective length of your model**, regardless of the horizon you type
in. At 5%, 90% of a perpetual stream's value arrives by year 48; at 10%, by year 25; at 3%, not
until year 78.

**Capital recovery factor** converts a lump sum into an equivalent annual payment over $\Lambda$
years:

$$\text{CRF} = \frac{\rho(1+\rho)^\Lambda}{(1+\rho)^\Lambda - 1}$$

**Why annualize capex instead of charging it at the build year?** Consider a 25-year asset built
in year 16 of a 20-year model. Lump-sum accounting charges 100% of its cost while the model only
sees 5 years of its output — so it refuses to build late, and that refusal is an accounting
artifact, not economics. Because an annuity discounts back to exactly its principal over a full
life, charging CRF per operating year makes the fraction of *cost* inside the horizon equal the
fraction of *value* inside the horizon. The bias cancels.

A **cool-down buffer** — solve to year 39, report to year 28 — fixes the same bias from the other
direction, by keeping decisions away from the boundary. Part 3 uses both, which is why its
lump-sum penalty is small.

---

### By hand

At $\rho = 5\%$: $\delta_1 = 0.952$, $\delta_5 = 0.784$, $\delta_{15} = 0.481$,
$\delta_{20} = 0.377$.

$$\text{CRF}(25\text{ yr}, 5\%) = \frac{0.05 (1.05)^{25}}{(1.05)^{25}-1} = 0.07095$$

Sanity check the definition: an annuity of 0.07095 paid for 25 years, discounted at 5%, is worth
exactly 1.0 today. That identity is the whole point.

**Now the late-build problem.** A plant costing 1000 with a 25-year life, built at the end of year
15 so it operates in years 16–40. The model stops reporting at year 20.

| accounting | what it charges | present value |
|---|---|---|
| lump sum at build | $1000 \times \delta_{15}$ | **481.0** |
| CRF over operating years *inside* the horizon (16–20) | $1000 \times 0.07095 \times \sum_{t=16}^{20}\delta_t$ | **147.8** |

And the share of the asset's output that falls inside the horizon, discounted the same way:

$$\frac{\sum_{t=16}^{20}\delta_t}{\sum_{t=16}^{40}\delta_t} = 0.307
\qquad\text{and}\qquad \frac{147.8}{481.0} = 0.307$$

**The two fractions are identical, exactly.** That is the cancellation: annualization charges the
model for precisely the share of the asset it is allowed to use. Lump-sum charges it for 100% of
an asset it can only use 31% of — which is why an unfixed model builds nothing in its final
years, and why Part 1 saw 342 units of unmet demand against 24.
""")
    C(r'''
rho, L = 0.05, 25
crf = rho*(1+rho)**L/((1+rho)**L - 1)
d   = lambda t: (1+rho)**-t

print(f"CRF({L} yr, {rho:.0%}) = {crf:.5f}")
print(f"check: annuity of {crf:.5f} for {L} yrs, discounted =",
      round(crf*sum(d(t) for t in range(1, L+1)), 6), " (should be 1.0)")

# The late-build bias, made arithmetic.
capex, build_end, horizon = 1000, 15, 20
inside = sum(d(t) for t in range(build_end+1, horizon+1))
full   = sum(d(t) for t in range(build_end+1, build_end+1+L))
print(f"\nplant of {capex} built end of year {build_end}, life {L}, horizon {horizon}")
print(f"  lump-sum charge      : {capex*d(build_end):8.1f}")
print(f"  annualised charge    : {capex*crf*inside:8.1f}")
print(f"  cost share charged   : {capex*crf*inside/(capex*d(build_end)):8.3f}")
print(f"  output share usable  : {inside/full:8.3f}   <- identical, by construction")

print("\n horizon   90% of perpetuity value reached by year")
for r in [0.03, 0.05, 0.10]:
    cum, cap, hit = 0.0, 1/r, None
    for t in range(1, 401):
        cum += 1/(1+r)**t
        if hit is None and cum >= 0.9*cap:
            hit = t
    print(f"   {r:.0%}      year {hit}")
''')
    M(r"""
---

# 9. Vintage indexing

**The idea.** How well an asset runs depends on *when it was built*, not only on what year it is
now. Getting that wrong quietly deletes the case for ever replacing anything.

| Symbol | Meaning | Kind |
|---|---|---|
| $v$ | vintage — the period the asset was built in | index |
| $p$ | the period it is currently operating in ($p \ge v$) | index |
| $\eta(v,p)$ | efficiency of a vintage-$v$ asset operating in period $p$ | **parameter** (a lookup) |
| $\eta^{new}(v)$ | efficiency of a brand-new asset built in $v$ — the *frontier* | parameter |
| $\bar\eta$ | technological ceiling nobody exceeds | parameter |
| $G_{\text{new}}$ | rate at which the frontier improves per period | parameter |
| $G_{\text{life}}$ | rate at which an existing asset improves per period | parameter |
| $\bar\Delta$ | cap on how much an asset can improve over its life | parameter |

Efficiency, cost and retirement all depend on **when an asset was built**. So index by vintage $v$
*and* operating period $p$:

$$\eta(v,p) = \min\Big\{\eta^{new}(v) + \bar\Delta,\;
\bar\eta - \big(\bar\eta - \eta^{new}(v)\big)(1-G_{\text{life}})^{\,p-v}\Big\}$$

Two channels: $G_{\text{new}}$ improves the **frontier** (newer builds start better),
$G_{\text{life}}$ improves assets **over their life** (operators learn). With
$G_{\text{life}} < G_{\text{new}}$ and both closing the remaining gap to the same ceiling, an old
asset improves but never overtakes a newer vintage.

**Why this matters:** an efficiency indexed on operating year alone, $\eta(p)$, silently upgrades
every existing asset every year — which destroys the economic case for replacement and
retirement, and does so **without any error message**.

$\eta(v,p)$ is a **parameter**, a dictionary lookup. It costs zero additional variables.
Replicating nodes into "new / mid / old" groups and unlocking them with big-M constraints costs
extra binaries, extra constraints, a weaker relaxation, *and* only approximates what the lookup
gives exactly.

---

### By hand

Ceiling $\bar\eta = 0.95$; a period-0 build starts at 0.70; frontier improves at
$G_{\text{new}} = 5\%$ of the remaining gap per period; assets improve in life at
$G_{\text{life}} = 2\%$ of their own remaining gap.

Frontier: $\eta^{new}(v) = 0.95 - 0.25(0.95)^{v}$ →

| $v$ | 0 | 5 | 10 |
|---|---|---|---|
| $\eta^{new}(v)$ | 0.700 | 0.757 | 0.800 |

Now the full table (blank = not built yet):

| built in $v$ ↓ / operating in $p$ → | $p=0$ | $p=10$ | $p=20$ |
|---|---|---|---|
| $v=0$ | 0.700 | 0.746 | 0.760* |
| $v=5$ | — | 0.775 | 0.807 |
| $v=10$ | — | 0.800 | 0.828 |

\* capped by $\bar\Delta = 0.06$.

Read the middle column: in period 10, the old plant runs at 0.746 and a new one at 0.800. The old
one **has** improved (0.700 → 0.746) but is still behind. That ordering is what makes replacement
economics work. Index on $p$ alone and every cell in a column becomes 0.800 — the 20-year-old
plant is suddenly as good as new, for free, and your model will never retire anything.
""")
    C(r'''
eta_bar, eta_start = 0.95, 0.70
G_new, G_life, cap_gain = 0.05, 0.02, 0.06

eta_new = lambda v: eta_bar - (eta_bar - eta_start)*(1 - G_new)**v
# THE FUNCTION IS THE LESSON: vintage efficiency is two compounding effects
# and one cap, and seeing them in three lines is the entire section.
def eta(v, p):
    return min(eta_new(v) + cap_gain,
               eta_bar - (eta_bar - eta_new(v))*(1 - G_life)**(p - v))

print("vintage |  p=0     p=10    p=20")
for v in (0, 5, 10):
    row = "  ".join(f"{eta(v,p):.3f}" if p >= v else "  -  " for p in (0, 10, 20))
    print(f"  v={v:<4d}|  {row}")
print("\nan old asset improves, but never overtakes a newer vintage:")
print(f"  v=0 at p=10 : {eta(0,10):.3f}")
print(f"  v=10 at p=10: {eta(10,10):.3f}  <- newer build is still better")
''')
    M(r"""
---

# 10. Variable-length periods

**The idea.** Model the near years one at a time and the far years in blocks — but then every
quantity needs the *right* weight, and money and matter need different ones.

| Symbol | Meaning | Kind |
|---|---|---|
| $p$ | a period, i.e. a block of consecutive years | index |
| $t \in p$ | the years belonging to period $p$ | index |
| $\omega_p$ | **money** weight of period $p$ | parameter |
| $L_p$ | **physical** weight of period $p$ — its length in years | parameter |

Investment granularity should be fine where decisions bind and coarse where they do not — at 5%,
years 1–15 carry over half the objective while years 30+ carry a few percent.

**The trap.** With unequal periods you need two different weights, and mixing them is the most
common bug in this class of model:

| Quantity | Weight | Why |
|---|---|---|
| Money (opex, transport, penalties) | $\omega_p = \sum_{t \in p} \delta_t$ | discounted sum over the period's years |
| Physical accumulation (cumulative production) | $L_p$ = period length | **undiscounted** — atoms do not discount |

Both failure modes are silent and both produce plausible-looking output.

---

### By hand

$\rho = 5\%$. Period 1 covers years 1–2; period 2 covers years 3–7.

$$\omega_1 = \delta_1 + \delta_2 = 0.952 + 0.907 = 1.859, \qquad L_1 = 2$$
$$\omega_2 = \delta_3 + \delta_4 + \delta_5 + \delta_6 + \delta_7 = 3.927, \qquad L_2 = 5$$

A plant in period 2 spends 100/yr on opex and makes 50 units/yr.

| quantity | correct | common bug | error |
|---|---|---|---|
| opex charged | $100 \times \omega_2 = 393$ | $100 \times \delta_3 = 86$ (weight as one year) | **4.5× too cheap** |
| cumulative production added | $50 \times L_2 = 250$ | $50 \times \omega_2 = 196$ (money weight) | 21% too little |

The first bug makes long periods nearly free to operate, so the model builds too much and runs it
too hard. The second understates cumulative volume, so learning arrives late. Neither raises an
error; both change the answer.

**Lags too.** Define any lag **in years**, then map to whichever period contains that year.
"Lagged by one period" means one year early in the horizon and five years late — which makes
learning artificially decelerate exactly as the periods coarsen.
""")
    C(r'''
rho = 0.05
d = lambda t: (1+rho)**-t
periods = {1: range(1, 3), 2: range(3, 8)}

for p, yrs in periods.items():
    w, L = sum(d(t) for t in yrs), len(list(yrs))
    print(f"period {p}: years {min(yrs)}-{max(yrs)}   omega={w:.4f}   L={L}")

w2, L2 = sum(d(t) for t in periods[2]), 5
print(f"\nopex 100/yr in period 2")
print(f"  correct  100 * omega = {100*w2:7.1f}")
print(f"  bug      100 * d(3)  = {100*d(3):7.1f}   ({100*w2/(100*d(3)):.1f}x understated)")
print(f"production 50/yr in period 2")
print(f"  correct  50 * L      = {50*L2:7.1f}")
print(f"  bug      50 * omega  = {50*w2:7.1f}   ({100*(1-50*w2/(50*L2)):.0f}% understated)")
''')
    M(r"""
---

# 11. Scenario trees and nonanticipativity

**The idea.** You must decide now, before you know which future happens — so the model must be
forbidden from making today's decision depend on tomorrow's news.

| Symbol | Meaning | Kind |
|---|---|---|
| $s \in \mathcal{S}$ | a scenario: one complete future | index |
| $\pi_s$ | probability of scenario $s$, $\sum_s \pi_s = 1$ | parameter |
| $x_s$ | the full decision vector under scenario $s$ | variable |
| $x_{s,t}$ | the stage-$t$ part of that vector | variable |
| $h_s(\cdot)$ | cost incurred in scenario $s$ | function |

A scenario tree has stages $t$ and leaf scenarios $s$ with probabilities $\pi_s$. A plan is
**implementable** only if scenarios you cannot yet tell apart take the same decision:

$$\mathcal{N} = \{x : x_{s,t} = x_{s',t} \text{ whenever } s,s' \text{ share a node at stage } t\}$$

$$\min_{x} \; \sum_s \pi_s\, h_s(x_s) \qquad \text{s.t.} \qquad x \in \mathcal{N}$$

$\mathcal{N}$ is the **nonanticipativity** set. It is the rigorous version of "you don't know the
future." Solving this directly — the **extensive form** — replicates the entire model once per
scenario, which is why it becomes intractable and why decomposition (§13, §14) exists.

**Rolling horizon is a poor man's stochastic program.** It captures not knowing the future but
never optimizes against a *distribution* of futures: it commits to one path and re-optimizes when
surprised.

---

### By hand

Three scenarios — demand Low (0.3), Mid (0.5), High (0.2) — revealed after stage 1. Build capacity
$x_1$ at stage 1, adjust with $x_{2,s}$ at stage 2.

| plan | $x_{1}$ under L / M / H | legal? |
|---|---|---|
| A | 10 / 10 / 10 | ✔ implementable — one number, decided before the reveal |
| B | 8 / 14 / 22 | ✘ **clairvoyant** — needs to know $s$ at stage 1 |

Plan B is what you get if you solve each scenario separately and average the answers, and it will
always look cheaper than anything you can actually do. Its cost is the WS bound of §12 — useful
as a benchmark, unusable as a plan.

**Size.** If the deterministic model has 500 variables and 3 stage-1 variables, the extensive form
over 3 scenarios has $3 \times 497 + 3 = 1494$ variables. Over 200 scenarios: 99,403. The model
grows linearly in the number of scenarios and the solve time does not.
""")
    M(r"""
---

# 12. EVPI and VSS — two different questions

**The idea.** Two separate things get called "the value of stochastic modelling". One measures
what perfect foresight would be worth (you cannot buy it). The other measures what *modelling*
the uncertainty is worth (you can).

| Quantity | Definition | Meaning |
|---|---|---|
| **WS** | *wait-and-see*: solve each scenario with perfect knowledge, then probability-weight | lower bound on cost, not achievable |
| **RP** | *recourse problem*: the stochastic optimum, respecting nonanticipativity | what you would actually do |
| **EEV** | fix the *mean-forecast* first-stage decision, then re-optimize later stages per scenario | what a point forecast costs you |
| **EVPI** | $\text{RP} - \text{WS}$ | value of foresight — **cannot be bought** |
| **VSS** | $\text{EEV} - \text{RP}$ | value of *modelling* uncertainty — **under your control** |

Guaranteed, for a minimization: $\;\text{WS} \le \text{RP} \le \text{EEV}$.

**All three must come from the same evaluation machinery.** Reading RP off a gap-terminated
extensive-form solve while EEV comes from an evaluation path mixes two different measurements and
can produce a negative VSS — which is impossible. If your ordering ever breaks, the plumbing is
wrong, not the economics. (Part 2 section 7 is built on exactly this trap: reading RP off the
extensive form's objective while EEV comes from the evaluation path compares two different
measurements, and a MILP terminated at a gap reports an objective *above* its true optimum.
Its fix is to route all three through one evaluation and assert `RP == ef.ObjVal`.)

**A large EVPI does not imply you need a stochastic model.** VSS is nonzero exactly when the
mean-forecast and stochastic solutions *choose differently*. Part 2 is a case in point:
EVPI is 1.547% of RP while VSS is 0.013% — foresight is worth a hundred times what the
stochastic model is, because the point forecast already picks very nearly the right
first move. One extra solve tells you whether you need the machinery.

Also: with coarse trees these metrics are **biased upward**, not merely noisy — extreme scenarios
carry too much probability mass.

**And VSS depends on how much you have COMMITTED, not only on how uncertain you are.**
Part 2's headline finding: with only year 1 fixed before the uncertainty resolves, VSS is
0.013%; lock in years 1, 4 and 7 and the same scenarios give 1.121%. Generous recourse makes
stochastic programming look worthless, and it is telling the truth about that model. Whether
that model is the right one is a separate and more important question.

---

### By hand

Build capacity $q$ now at 6 per unit. Demand $d$ is 5 or 15, equally likely. Every unit of demand
you cannot serve costs 10 in lost margin. Total cost $= 6q + 10(d-q)^{+}$.

Three candidate capacities, two scenarios:

| $q$ | cost if $d=5$ | cost if $d=15$ | expected cost |
|---|---|---|---|
| 5 | $30 + 0 = 30$ | $30 + 100 = 130$ | **80** ← best on average |
| 10 | $60 + 0 = 60$ | $60 + 50 = 110$ | 85 |
| 15 | $90 + 0 = 90$ | $90 + 0 = 90$ | 90 |

**RP = 80** — the stochastic optimum builds *small*, accepting shortfalls in the bad case.

**WS**: with foresight you would build 5 when $d=5$ (cost 30) and 15 when $d=15$ (cost 90).
$\text{WS} = 0.5(30) + 0.5(90) = 60$.

**EEV**: mean demand is 10. Optimize against $d=10$ alone — costs are 80, **60**, 90 for
$q = 5, 10, 15$ — so the point forecast says build 10. Now *evaluate that plan* across the real
scenarios: $0.5(60)+0.5(110) = 85$.

$$\text{EVPI} = 80 - 60 = \mathbf{20}, \qquad \text{VSS} = 85 - 80 = \mathbf{5}$$

Ordering holds: $60 \le 80 \le 85$ ✓.

Read it: foresight would be worth 20, and you cannot have it. Thinking probabilistically instead
of pointwise is worth 5 (6% of RP), and you can have that for the price of writing the model.
Note *why* it is worth anything — the mean forecast picks $q=10$ and the stochastic model picks
$q=5$. **Different decisions is the whole mechanism.** Had both picked 10, VSS would be exactly 0
no matter how large the uncertainty.
""")
    C(r'''
# EVPI and VSS from one table, computed the way you should compute them:
# one evaluation routine used for all three quantities.
scen = {5: 0.5, 15: 0.5}          # demand -> probability
CAPEX, LOST = 6, 10
cands = [5, 10, 15]

cost = lambda q, dmd: CAPEX*q + LOST*max(0, dmd - q)
ev   = lambda q: sum(pr*cost(q, dmd) for dmd, pr in scen.items())

print("  q  |  d=5   d=15  |  E[cost]")
for q in cands:
    print(f" {q:3d} | {cost(q,5):5d} {cost(q,15):6d}  | {ev(q):8.1f}")

WS  = sum(pr*min(cost(q, dmd) for q in cands) for dmd, pr in scen.items())
RP  = min(ev(q) for q in cands)
mean_d = sum(pr*dmd for dmd, pr in scen.items())
q_ev   = min(cands, key=lambda q: cost(q, mean_d))     # the mean-forecast decision
EEV = ev(q_ev)                                          # ... evaluated honestly

print(f"\nmean demand {mean_d:.0f} -> mean-forecast plan q = {q_ev}")
print(f"WS   = {WS:6.1f}   (perfect foresight, unattainable)")
print(f"RP   = {RP:6.1f}   (stochastic optimum, q = {min(cands, key=ev)})")
print(f"EEV  = {EEV:6.1f}   (mean-forecast plan, evaluated across scenarios)")
print(f"EVPI = RP - WS  = {RP-WS:5.1f}")
print(f"VSS  = EEV - RP = {EEV-RP:5.1f}")
assert WS <= RP <= EEV, "ordering violated -> the plumbing is wrong, not the economics"
print("\nassertion WS <= RP <= EEV holds")
''')
    M(r"""
---

# 13. Progressive hedging

**The idea.** Let each scenario pretend it knows the future, then charge it a growing penalty for
disagreeing with the others until they all agree.

| Symbol | Meaning | Kind |
|---|---|---|
| $x_s$ | scenario $s$'s own version of the first-stage decision | variable |
| $z$ | the consensus decision: probability-weighted average of the $x_s$ | variable |
| $w_s$ | multiplier for scenario $s$ — the accumulated "you keep disagreeing" charge | variable |
| $\rho_{\text{PH}}$ | penalty weight | **parameter you must tune** |
| $k$ | iteration counter | index |

**PH** relaxes nonanticipativity, solves each scenario as if clairvoyant, and iterates to
agreement:

$$x_s^{k+1} = \arg\min_{x_s}\Big\{h_s(x_s) + (w_s^k)^\top x_s
+ \tfrac{\rho_{\text{PH}}}{2}\lVert x_s - z^k\rVert^2\Big\}$$
$$z^{k+1} = \sum_s \pi_s x_s^{k+1}, \qquad w_s^{k+1} = w_s^k + \rho_{\text{PH}}(x_s^{k+1} - z^{k+1})$$

Line by line: solve each scenario with two extra terms — a *linear* charge $w_s^\top x_s$ that
remembers which way this scenario has been pulling, and a *quadratic* charge pulling it toward the
current consensus. Average to get the new consensus. Update each multiplier by how far its
scenario still deviates. Repeat until the deviations vanish.

It is ADMM in a scenario-product space. It decomposes the **scenario** dimension — on a
deterministic model it buys nothing; what it buys is making *going stochastic* affordable.

**A useful trick.** The quadratic penalty would normally make each subproblem a MIQP. But for
binary $x$, $x^2 = x$, so

$$\tfrac{\rho_{\text{PH}}}{2}\lVert x-z\rVert^2 = \tfrac{\rho_{\text{PH}}}{2}\big[x(1-2z) + z^2\big]$$

— **linear**. Subproblems stay MILPs. (Check at $z=0.6$: $x=1$ gives $(1-0.6)^2 = 0.16$ and
$1(1-1.2)+0.36 = 0.16$ ✓; $x=0$ gives $0.36$ both ways ✓.)

**Honest caveats.** Convergence is proven for convex problems with compact feasible sets; on MILPs
PH is a **heuristic** — it may return a good plan, but it does not hand you a bound. Convergence
is **not monotone in $\rho_{\text{PH}}$**: small values never agree, large values snap to a poor
point, intermediate values can cycle. Always sweep it.

**APH** (Eckstein, Watson & Woodruff 2025) relaxes PH's synchronicity: only a subset of
subproblems need solving per iteration, with deterministic convergence under a *fairness*
condition — every scenario must be revisited within a bounded number of iterations. A round-robin
guarantees it; random sampling does not.

---

### By hand

Two equally likely scenarios. Scenario 1 alone would want $x = 2$; scenario 2 alone would want
$x = 8$. Write the costs as $h_1(x) = (x-2)^2$ and $h_2(x) = (x-8)^2$. The right answer is
obviously $z = 5$; watch PH find it. Take $\rho_{\text{PH}} = 1$.

**Iteration 1** — no penalties yet, so each scenario gets its wish:

$$x_1 = 2,\quad x_2 = 8 \;\Rightarrow\; z = 5, \quad w_1 = 1(2-5) = -3, \quad w_2 = +3$$

**Iteration 2** — each subproblem now minimizes $(x-a)^2 + w x + \tfrac12 (x-5)^2$. Setting the
derivative to zero: $2(x-a) + w + (x - 5) = 0$, so $x = (2a - w + 5)/3$.

$$x_1 = \frac{4+3+5}{3} = 4, \qquad x_2 = \frac{16-3+5}{3} = 6$$

They have moved from 6 apart to 2 apart. Continue:

| iteration | $x_1$ | $x_2$ | $z$ | $w_1$ | disagreement |
|---|---|---|---|---|---|
| 1 | 2.000 | 8.000 | 5.0 | −3.00 | 6.00 |
| 2 | 4.000 | 6.000 | 5.0 | −4.00 | 2.00 |
| 3 | 4.333 | 5.667 | 5.0 | −4.67 | 1.33 |
| 4 | 4.556 | 5.444 | 5.0 | −5.11 | 0.89 |
| 5 | 4.704 | 5.296 | 5.0 | −5.41 | 0.59 |

The consensus $z$ was right from the first iteration; what takes the iterations is getting the
scenarios to *accept* it — the multipliers grow until disagreement is not worth its price. That is
the whole algorithm, and it is why the stopping test is on the spread of the $x_s$, not on $z$.
""")
    C(r'''
# Progressive hedging by hand, on a two-scenario quadratic. No solver needed:
# each subproblem's first-order condition is solvable in closed form.
rho_ph, targets, pi = 1.0, [2.0, 8.0], [0.5, 0.5]

x = list(targets)                                   # iteration 1: each scenario gets its wish
z = sum(p*xi for p, xi in zip(pi, x))
w = [rho_ph*(xi - z) for xi in x]
print(f"it 1:  x1={x[0]:6.3f}  x2={x[1]:6.3f}  z={z:5.3f}  w1={w[0]:6.3f}  spread={abs(x[0]-x[1]):5.3f}")

for it in range(2, 9):
    # min (x-a)^2 + w*x + rho/2 (x-z)^2   ->   2(x-a) + w + rho(x-z) = 0
    x = [(2*a - wi + rho_ph*z)/(2 + rho_ph) for a, wi in zip(targets, w)]
    z = sum(p*xi for p, xi in zip(pi, x))
    w = [wi + rho_ph*(xi - z) for wi, xi in zip(w, x)]
    print(f"it {it}:  x1={x[0]:6.3f}  x2={x[1]:6.3f}  z={z:5.3f}  w1={w[0]:6.3f}  spread={abs(x[0]-x[1]):5.3f}")

print(f"\ntrue optimum of 0.5[(x-2)^2 + (x-8)^2] is x = 5")
print("\nthe binary trick, checked numerically:")
for zz in (0.6,):
    for xb in (0, 1):
        print(f"  z={zz}  x={xb}:  (x-z)^2 = {(xb-zz)**2:.4f}   "
              f"x(1-2z)+z^2 = {xb*(1-2*zz)+zz**2:.4f}")
''')
    M(r"""
---

# 14. Benders / L-shaped decomposition

**The idea.** Solve the hard integer part on its own, guessing what the easy continuous part will
cost; let the easy part send back a linear "your guess is too low, and here is the slope" message;
repeat. The messages are the *cuts*.

| Symbol | Meaning | Kind |
|---|---|---|
| $y$ | first-stage decision (capacity, build) — the master's variables | variable |
| $\hat{y}$ | a *specific* proposal from the master, fixed when solving the subproblem | parameter, downstream |
| $\theta$ | the master's estimate of downstream cost — an epigraph variable | variable |
| $Q(y)$ | the true optimal downstream cost given $y$ | function |
| dual | shadow price returned by the subproblem; becomes the cut's slope | — |

If your model has the structure **integer decisions set capacity, then a continuous problem
evaluates it**, you can split it:

- **Master** (integers): propose a capacity vector, using $\theta$ as a placeholder for downstream
  cost.
- **Subproblem** (LP): given that capacity, find optimal flows; return its dual solution.
- **Cut**: the duals give a valid linear underestimate of $Q(y)$. Add $\theta \ge (\text{that
  linear function})$ to the master and repeat.

Because the master only ever has *some* of the cuts, it always underestimates: **its objective is
a valid lower bound at every iteration**. Any $\hat y$ plus its true $Q(\hat y)$ is an upper bound.
They meet.

For a two-stage stochastic program with integer first stage and LP recourse this is the
**L-shaped method**, and it is usually *preferable to PH* — the subproblems are convex with exact
duals, where PH on mixed-integer subproblems is a heuristic.

This is why Part 3 keeps flows continuous. It also enables **bilevel** models: because a
follower's operational problem is an LP, you can write its KKT conditions and collapse a
Stackelberg game to a single level (an MPEC, §18).

| Decomposition | Splits | Use when |
|---|---|---|
| Benders / L-shaped | integer vs continuous | LP recourse, integer investment |
| Progressive hedging | scenarios | subproblems contain integers |

They are orthogonal and can be combined.

---

### By hand

Build capacity $y \in [0,10]$ at 5 per unit. Then serve demand of 8: each unit served from
capacity costs 3, each unit unserved costs 20.

$$Q(y) = 3\min(y,8) + 20\,(8-\min(y,8))
= \begin{cases} 160 - 17y & y \le 8\\ 24 & y \ge 8\end{cases}$$

$Q$ is piecewise linear, decreasing, **convex** — which is exactly why linear cuts underneath it
are valid.

**Iteration 1.** The master has no cuts yet, so it believes downstream cost could be zero:
$\min 5y + \theta$ with $\theta \ge 0$ gives $y = 0$, $\theta = 0$, **LB = 0**. Now solve the
subproblem at $\hat y = 0$: $Q(0) = 160$, and its dual says each extra unit of capacity is worth
17. So the true cost of this proposal is $0 + 160 = 160$ → **UB = 160**, and the cut is

$$\theta \;\ge\; 160 - 17y$$

**Iteration 2.** Master: $\min 5y + \theta$ s.t. $\theta \ge 160 - 17y,\; \theta \ge 0$. Below
$y = 160/17 = 9.41$ the cut binds and the total is $160 - 12y$, falling; above it $\theta$ hits
zero and the total is $5y$, rising. So $y = 9.41$, **LB = 47.06**. Subproblem: $Q(9.41) = 24$
(capacity is now slack, so the dual is 0) → **UB = 71.06**, and the new cut is flat:
$\;\theta \ge 24$.

**Iteration 3.** Master: $\min 5y + \theta$ s.t. $\theta \ge 160-17y$, $\theta \ge 24$. The two
cuts cross at $y = 8$; below that the total is $160-12y$ (falling), above it $5y + 24$ (rising).
So $y = 8$, $\theta = 24$, **LB = 64**. Subproblem: $Q(8) = 24$ → **UB = 64**. LB = UB → **done,
provably optimal.**

| iteration | $\hat y$ | LB | UB | cut added |
|---|---|---|---|---|
| 1 | 0.00 | 0.00 | 160.00 | $\theta \ge 160 - 17y$ |
| 2 | 9.41 | 47.06 | 71.06 | $\theta \ge 24$ |
| 3 | 8.00 | **64.00** | **64.00** | converged |

The bounds close from both ends, and **the master never saw the function $Q$** — only two of its
tangent lines. That is the whole economy of the method: on a real model, $Q$ is a large LP over
thousands of flow variables, and the master learns enough about it from a handful of hyperplanes.

### Multicut vs single-cut

With $S$ scenarios you can keep **one** $\theta$ standing in for the average recourse cost, or
**$S$ of them**, one per scenario:

| | Single-cut | Multicut |
|---|---|---|
| Master variables | one $\theta$ | $\theta_s$ for each scenario |
| Learned per iteration | one hyperplane about the *average* | $S$ hyperplanes about the parts |
| Master size | small, constant | grows $S\times$ faster |
| Iterations | many | few |

Aggregating throws away the information that scenarios disagree, which is precisely the
information that made the problem stochastic. Part 2b measures it: **15 iterations multicut
against 22 single-cut**, both terminating at the extensive-form optimum exactly. Multicut is the
default unless the master becomes the bottleneck.

### The bound is the point

The master is a relaxation, so its objective is a **valid lower bound at every iteration** — not
an estimate. Progressive hedging with an integer first stage cannot give you this. For work that
will inform an investment recommendation, "provably within 0.4%" is worth more than a slightly
better incumbent with no certificate.
""")
    C(r'''
# Benders, three iterations, no solver: the master is small enough to reason about directly.
CAPEX, SERVE, PENALTY, DEMAND, YMAX = 5, 3, 20, 8, 10

# THE FUNCTION IS THE LESSON: Benders needs a subproblem VALUE and its
# SLOPE, and the whole method is what you do with those two numbers.
def Q(y):                                    # subproblem value
    served = min(y, DEMAND)
    return SERVE*served + PENALTY*(DEMAND - served)

def dual_slope(y):                           # d Q / d y  (the cut's slope)
    return (SERVE - PENALTY) if y < DEMAND else 0.0

cuts, UB = [], float("inf")
print(" it |   y   |   LB    |   UB    | cut added")
for it in range(1, 5):
    # master: min 5y + theta  s.t. theta >= intercept + slope*y, theta >= 0, 0 <= y <= YMAX
    best = None
    for yg in [i/1000 for i in range(0, YMAX*1000 + 1)]:
        th = max([0.0] + [ic + sl*yg for ic, sl in cuts])
        v  = CAPEX*yg + th
        if best is None or v < best[0]:
            best = (v, yg, th)
    LB, y_hat, th = best
    UB = min(UB, CAPEX*y_hat + Q(y_hat))
    sl = dual_slope(y_hat); ic = Q(y_hat) - sl*y_hat
    done = abs(UB - LB) < 1e-6
    print(f" {it:2d} | {y_hat:5.2f} | {LB:7.2f} | {UB:7.2f} | "
          + ("converged" if done else f"theta >= {ic:.0f} + {sl:.0f}y"))
    if done:
        break
    cuts.append((ic, sl))
''')
    M(r"""
---

# 15. Piecewise linearization revisited — curvature *and* direction

**The idea.** §5's rule was half the story. Whether a free convex combination cheats depends on
the curve's shape **and** on whether you are minimizing or maximizing. Same curve, opposite
requirement.

| | Minimising | Maximising |
|---|---|---|
| **Convex** $f$ | chord above — safe | chord exploited → restrict |
| **Concave** $f$ | chord below — **exploited → SOS2** | chord below — **safe** |

- **Part 3**: cumulative learning cost is concave, and we minimise. Dangerous. SOS2 required.
- **Part 4c**: Cournot revenue is concave, and we maximise. **Safe** — a free convex combination
  has no incentive to mix non-adjacent breakpoints, because doing so would report *less* revenue.
  No SOS2, no binaries, no branching.

---

### By hand

Reuse §5's concave curve exactly: $Q_k = (0,100,200,300,400)$, $F_k = (0,60,100,130,150)$, and the
same cheat, $\lambda_0 = \lambda_4 = 0.5$, giving $Q = 200$ and $F = 75$ against a true 100.

| you are | the chord gives | the solver's incentive | verdict |
|---|---|---|---|
| **minimising** $F$ | 75 < 100 | take it — 75 is better | **broken**, needs SOS2 |
| **maximising** $F$ | 75 < 100 | refuse it — 100 is better, use $\lambda_2 = 1$ | **safe**, no SOS2 |

Identical constraints, identical numbers. Only the direction of the objective changed, and with it
the entire answer to "do I need SOS2?" Always check both before reaching for it — **and before
omitting it.**

---

**Approximation error behaves differently inside a game.** Part 4c-exact measures this: piecewise
revenue understates a single best response by ~0.25% at 7 breakpoints, exactly as theory predicts.
But at the *equilibrium* the error changes sign and grows to ~12% for one firm, because each firm's
slightly-wrong response perturbs its rival's problem and the perturbations compound around the
best-response loop.

**Validate a discretisation at the level you report, not the level you solve.**
""")
    M(r"""
---

# 16. Games: best response, Nash equilibrium, and what convergence means

**The idea.** One objective function means one decision maker. Two firms with conflicting
objectives is a *game*, and no single optimisation represents it.

| Term | Meaning |
|---|---|
| **strategy** | the thing a player chooses (a build plan, a quantity schedule) |
| **profile** | one strategy for each player — a candidate outcome |
| **best response** | the strategy maximising your payoff, *taking the rival's as fixed* |
| **Nash equilibrium** | a profile where every player is already best-responding — nobody gains by deviating alone |
| **iterated best response** | fix the rival's strategy, optimise, swap, repeat |

Adding a second objective with a weight gives you a *cooperative planner splitting the
difference*, which is precisely not rivalry. The distinction is not cosmetic — §20 shows the two
give different numbers by construction.

A fixed point of iterated best response is a pure-strategy **Nash equilibrium**. Three outcomes
must be distinguished, and the third is not a failure:

1. **Converged** — the profile repeats. A Nash equilibrium of the discretised game.
2. **Cycle** — the profile repeats after $k \ge 2$ rounds. No pure-strategy equilibrium was found
   by this procedure. With **lumpy investment this is expected**: each firm builds only if the
   other does not. Report it; suppressing it would be the error.
3. **Iteration cap** — report non-convergence honestly.

---

### By hand

Two firms decide whether to Build a plant. The market supports one plant, not two.

| | firm 2: Build | firm 2: Not |
|---|---|---|
| **firm 1: Build** | (−20, −20) | (**50**, 0) |
| **firm 1: Not** | (0, **50**) | (0, 0) |

Check each cell by asking "does either player want to move?"

| profile | firm 1's best reply | firm 2's best reply | equilibrium? |
|---|---|---|---|
| (Build, Build) | Not (−20 → 0) | Not | no |
| (Build, Not) | Build ✓ | Not ✓ | **yes** |
| (Not, Build) | Not ✓ | Build ✓ | **yes** |
| (Not, Not) | Build (0 → 50) | Build | no |

**Two equilibria**, and they differ by *who* got there. That is first-mover advantage in its
purest form — worth 50 versus 0 — and it means "the equilibrium" is not a well-defined object
here. In Part 4b the two move orders give different equilibria with the advantage worth ~29% of
profit. Reporting one ordering reports an artefact of the solution procedure: sweep the order,
and the starting profile too.

**And watch how you iterate.** From (Not, Not), if both firms best-respond *simultaneously* they
both build, landing on (Build, Build); from there both withdraw, landing back on (Not, Not) — a
**2-cycle that never terminates**, even though two equilibria exist. Alternating updates find one
immediately. The cycle is a property of the *update rule*, not of the game.

---

### Two traps, both hit while building Part 4

**Test the actual strategy.** Part 4b tested convergence on build plans alone. In Cournot the
strategy *is* the quantity schedule, and testing plans declared convergence while quantities were
still moving by thousands of cost units.

**Use a tolerance, never exact matching.** Hashing the exact quantity vector produced a spurious
**5-cycle** — profits oscillating in the fourth significant figure with identical build plans.
That was MIP-gap noise: each best response is a MILP solved to a finite tolerance, so quantities
wobble even at a genuine fixed point. **A loose MIP gap inside a best-response loop can masquerade
as strategic cycling.**
""")
    C(r'''
# The entry game: enumerate, then check every profile for unilateral deviations.
pay = {("B","B"): (-20,-20), ("B","N"): (50, 0), ("N","B"): (0, 50), ("N","N"): (0, 0)}
S = ("B", "N")

print("profile   payoffs      BR1  BR2   Nash?")
for a in S:
    for b in S:
        br1 = max(S, key=lambda s: pay[(s, b)][0])
        br2 = max(S, key=lambda s: pay[(a, s)][1])
        print(f"  ({a},{b})   {str(pay[(a,b)]):>12}    {br1}    {br2}    "
              f"{'YES' if (br1, br2) == (a, b) else 'no'}")

print("\nsimultaneous best response from (N,N)  -  both players move at once:")
prof, seen = ("N", "N"), [("N", "N")]
print(f"  start : {prof}")
for step in range(1, 6):
    prof = (max(S, key=lambda s: pay[(s, prof[1])][0]),      # both read the OLD profile
            max(S, key=lambda s: pay[(prof[0], s)][1]))
    if prof in seen:
        print(f"  step {step}: {prof}   <- already seen: this is a {step - seen.index(prof)}-cycle,")
        print("            yet two equilibria exist. The cycle is the update rule, not the game.")
        break
    seen.append(prof)
    print(f"  step {step}: {prof}")
''')
    M(r"""
---

# 17. Cournot competition and endogenous price

**The idea.** Let the price fall as total output rises, and rivalry changes character completely:
firms stop racing for a fixed prize and start weighing volume against the margin they destroy by
chasing it.

| Symbol | Meaning | Kind |
|---|---|---|
| $A$ | choke price — the price at which demand hits zero | parameter |
| $B$ | slope of inverse demand | parameter |
| $C$ | marginal cost per unit | parameter |
| $q_f$ | quantity sold by firm $f$ | variable |
| $\bar q$ | the *rival's* quantity, taken as fixed while firm $f$ optimises | parameter, downstream |

With a **fixed** price, rivalry is a race for a capped market: the only channel between firms is
residual demand, and whoever commits capacity first takes it. That structure manufactures a large
first-mover advantage.

With **endogenous** price, quantity determines price:

$$\text{price} = A - B\sum_f q_f$$

Firm $f$'s revenue, taking the rival's quantity $\bar q$ as given:

$$\big(A - B(q + \bar q)\big)q = \underbrace{(A - B\bar q)}_{\text{shifted intercept}}q - Bq^2$$

Concave in own quantity, so each best response is a **QP** (or MIQP with investment binaries).
Differentiating and setting to zero gives the best-response function

$$q^{*} = \frac{A - C - B\bar q}{2B}$$

---

### By hand

$A = 100$, $B = 1$, $C = 10$ for both firms. Best response: $q^{*} = (90 - \bar q)/2$.

**Iterated best response**, starting from a rival quantity of 0:

| round | $q_1$ | $q_2$ |
|---|---|---|
| 1 | 45.00 | 22.50 |
| 2 | 33.75 | 28.13 |
| 3 | 30.94 | 29.53 |
| 4 | 30.23 | 29.88 |
| 5 | 30.06 | 29.97 |

Converging on $q_1 = q_2 = 30$ — which you can also get directly by symmetry: $q = (90-q)/2$
gives $q = 30$. Total 60, price $100 - 60 = 40$, profit each $(40-10)\times 30 = 900$.

**Three benchmarks on the same numbers:**

| outcome | total quantity | price | joint profit |
|---|---|---|---|
| Collusion (one decision maker) | 45 | 55 | **2025** |
| Cournot (two rivals) | 60 | 40 | 1800 |
| Stackelberg (leader commits 45) | 67.5 | 32.5 | 1518.75 |

Collusion restricts output by 25% and lifts joint profit by 12.5% — the standard benchmark against
which Cournot sits. Add players and quantity keeps rising toward the competitive level; that is
the entire content of the Cournot model.

---

### Three consequences worth internalising

- **Price adjustment substitutes for rationing.** Part 4b's 29% first-mover advantage falls to ~4%
  under Cournot: there is no capped market to seize, and flooding depresses your own margin too.
  *A result that depends on a rationing rule deserves suspicion.*
- **Collusion restricts output.** Joint profit maximisation cuts quantity ~30% in Part 4c, raises
  price, and lifts joint profit ~20%.
- **Learning finally changes quantities.** With demand fixed and costs minimised (Part 3b),
  production-based learning was a windfall that changed no decision — cumulative production was
  pinned by demand. Once quantity is a decision, firms rationally sell *past* the static optimum
  because a unit sold advances them toward a cheaper cost tier. In Part 4c this raises output ~13%.
  **Learning-by-doing also amplifies incumbency** — the firm already further along the curve gains
  more from each marginal unit.
""")
    C(r'''
A, B, C = 100.0, 1.0, 10.0
br = lambda q_rival: (A - C - B*q_rival)/(2*B)      # best-response function

q1 = q2 = 0.0
print("round     q1      q2     price   profit1")
for k in range(1, 7):
    q1 = br(q2); q2 = br(q1)                        # alternating best response
    price = A - B*(q1 + q2)
    print(f"  {k}    {q1:6.3f}  {q2:6.3f}  {price:6.2f}  {(price-C)*q1:8.2f}")

qc = (A - C)/(3*B)                                  # symmetric Cournot, closed form
qm = (A - C)/(2*B)                                  # monopoly / collusive total
qL = qm; qF = br(qL)                                # Stackelberg
print(f"\n{'outcome':<14}{'total q':>9}{'price':>8}{'joint profit':>14}")
for name, tot in [("collusion", qm), ("Cournot", 2*qc), ("Stackelberg", qL+qF)]:
    p = A - B*tot
    print(f"{name:<14}{tot:9.2f}{p:8.2f}{(p-C)*tot:14.2f}")
print(f"\nStackelberg leader profit {(A-B*(qL+qF)-C)*qL:.2f} vs Cournot {(A-B*2*qc-C)*qc:.2f}"
      f"  -> first-mover advantage {100*((A-B*(qL+qF)-C)*qL/((A-B*2*qc-C)*qc)-1):.1f}%")
''')
    M(r"""
---

# 18. Bilevel programs, KKT conditions, and MPECs

**The idea.** When one player moves first and the other reacts, you have an optimisation *inside*
an optimisation. No solver accepts that. But if the inner problem is nice enough, you can replace
it with the algebraic conditions that characterise its solution, and the whole thing flattens into
one model.

| Symbol | Meaning | Kind |
|---|---|---|
| $x_L$ | the leader's decision (moves first, commits) | variable |
| $x_F$ | the follower's decision (observes, then reacts) | variable |
| $\Pi_L, \Pi_F$ | leader's and follower's payoffs | functions |
| $\mathcal{L}$ | the follower's Lagrangian | function |
| $\mu_i$ | multiplier on the follower's $i$-th inequality — its shadow price | variable |
| $g_i(x) \le 0$ | the follower's $i$-th constraint | — |
| $M$ | big-M used to linearise complementarity | parameter |

A **Stackelberg** game has a leader who commits and a follower who observes and responds:

$$\max_{x_L}\; \Pi_L(x_L, x_F^*) \quad\text{s.t.}\quad x_F^* \in \arg\max_{x_F} \Pi_F(x_F; x_L)$$

Replace the inner problem with its **KKT optimality conditions** — the calculus conditions that a
constrained optimum must satisfy — yielding a single-level **MPEC** (Mathematical Program with
Equilibrium Constraints):

*Stationarity* — $\nabla_{x_F}\mathcal{L} = 0$: at the optimum, the gradient of the payoff is
exactly balanced by the pull of the binding constraints.

*Primal and dual feasibility* — $g_i \le 0$ and $\mu_i \ge 0$.

*Complementarity* — $\mu_i \, g_i(x) = 0$: each constraint is either tight or worthless. This is
the one nonlinear piece, and it is linearised with a binary and a big-M:

$$\mu_i \le M y_i, \qquad -g_i \le M(1-y_i), \qquad y_i \in \{0,1\}$$

Read it: $y_i = 1$ allows a positive multiplier but forces zero slack; $y_i = 0$ allows slack but
forces the multiplier to zero. Exactly one of the two, which is what complementarity says.

**This works only if the follower's problem is continuous and concave.** KKT is necessary and
sufficient for a concave program and says nothing useful about a MILP. That is the payoff for the
design choice in Part 3: keep the operational layer an LP and put integers only on investment.

---

### By hand

Continue §17's numbers. The leader commits $q_L = 45$. The follower solves

$$\max_{q_F \ge 0} \;\big(100 - (45 + q_F)\big)q_F - 10 q_F \quad\text{s.t.}\quad q_F \le \text{CAP}$$

Lagrangian $\mathcal{L} = (55 - q_F)q_F - 10q_F - \mu(q_F - \text{CAP})$, so stationarity reads

$$45 - 2q_F - \mu = 0$$

**Case CAP = 30 (loose).** Guess $\mu = 0$ → $q_F = 22.5$. Check feasibility: $22.5 \le 30$ ✓.
Check complementarity: $\mu(q_F - \text{CAP}) = 0 \times (-7.5) = 0$ ✓. Valid.

**Case CAP = 15 (binding).** Guess $\mu = 0$ → $q_F = 22.5 > 15$ ✘ infeasible. So the constraint
must be tight: $q_F = 15$, and stationarity gives $\mu = 45 - 30 = 15$. Check $\mu \ge 0$ ✓,
complementarity $15 \times 0 = 0$ ✓. Valid — and $\mu = 15$ is meaningful: one more unit of
capacity would earn the follower 15.

**The big-M sizing question, concretely.** In the second case $\mu = 15$. Set $M = 10$ and the
constraint $\mu \le My$ caps $\mu$ at 10 — the model stays feasible, still solves, and returns a
follower response that is simply wrong. **Nothing warns you.** Size $M$ above the largest
shadow price the follower could ever have; here $\mu \le 45$, so $M = 50$ is defensible and
$M = 10^9$ wrecks the relaxation (§3).

---

**Always validate an MPEC.** Take the leader's solution, solve the follower's problem *directly*,
and confirm the embedded KKT block reproduces it. Part 4d does this and matches to machine
precision.

**Caveats worth knowing.** MPECs violate standard constraint qualifications at every feasible
point — the complementarity system has no strict interior — which is why the big-M reformulation
into a MILP is the standard route rather than an elegant one. And the big-Ms are *chosen*, not
derived: too small silently forces duals to zero, too large destroys the relaxation.
""")
    C(r'''
# The follower's KKT conditions, checked by hand-enumeration of the two cases.
A, B, C, qL = 100.0, 1.0, 10.0, 45.0

# THE FUNCTION IS THE LESSON: the KKT conditions ARE this section, and
# enumerating the two cases by hand is how you see why an MPEC needs
# complementarity rather than a solver call.
def follower_kkt(CAP):
    # stationarity: (A - C - B*qL) - 2*B*qF - mu = 0
    slope = A - C - B*qL
    qF_unc = slope/(2*B)
    if qF_unc <= CAP:
        qF, mu, branch = qF_unc, 0.0, "cap slack  -> mu = 0"
    else:
        qF, mu, branch = CAP, slope - 2*B*CAP, "cap tight  -> mu > 0"
    return qF, mu, branch

for CAP in (30.0, 15.0):
    qF, mu, branch = follower_kkt(CAP)
    direct = min(CAP, (A - C - B*qL)/(2*B))          # solve the follower directly
    print(f"CAP={CAP:5.1f}  qF={qF:6.2f}  mu={mu:5.2f}   {branch}")
    print(f"          stationarity residual : {A-C-B*qL-2*B*qF-mu:.1e}")
    print(f"          complementarity mu*(qF-CAP) : {mu*(qF-CAP):.1e}")
    print(f"          direct solve agrees   : {abs(direct-qF) < 1e-9}\n")

print("big-M sizing: the largest multiplier the follower can have here is",
      f"{A - C - B*qL:.0f}, so M = 50 is safe and M = 10 would silently truncate mu.")
''')
    M(r"""
---

# 19. Linearizing products of variables

**The idea.** A variable times a constant is fine. A variable times a *variable* is not, and how
badly it hurts depends on which kinds of variables.

| Symbol | Meaning | Kind |
|---|---|---|
| $y$ | a binary variable | variable |
| $x$ | a continuous variable, $0 \le x \le M$ | variable |
| $w$ | the auxiliary variable standing in for the product | variable |
| $S_k$ | the $k$-th value on a discretisation grid | parameter |

**Constant × variable** — already linear. Nothing to do. This is why Part 3b disaggregates
throughput across learning tiers: each piece then meets a *constant* multiplier (§6).

**Binary × continuous** — linearises **exactly**. For $w = y \cdot x$ with $y \in \{0,1\}$ and
$0 \le x \le M$:

$$w \le My, \qquad w \le x, \qquad w \ge x - M(1-y), \qquad w \ge 0$$

**Continuous × continuous** — genuinely nonconvex. Options: McCormick envelopes (a relaxation, so
you get a bound not an answer), a global solver, or **discretise one factor onto a
binary-selected grid** to convert it into the exact binary×continuous case.

Part 4d uses the third route. The leader's revenue contains $-B\,q^F q^L$, a product of two
decision variables. Writing $q^L = \sum_k S_k y_k$ with binary $y_k$ turns it into
$\sum_k S_k (q^F y_k)$ — exactly linearisable, one auxiliary per grid point. The only
approximation is the grid's fineness, which is a parameter you can sweep, and coarsening it can
only *understate* the leader's profit because it restricts the leader's strategy space.

---

### By hand

**Binary × continuous.** Take $x = 7$, $M = 10$.

| | $w \le My$ | $w \le x$ | $w \ge x - M(1-y)$ | $w \ge 0$ | forced |
|---|---|---|---|---|---|
| $y = 0$ | $w \le 0$ | $w \le 7$ | $w \ge -3$ | $w \ge 0$ | $w = 0$ ✓ |
| $y = 1$ | $w \le 10$ | $w \le 7$ | $w \ge 7$ | $w \ge 0$ | $w = 7$ ✓ |

In both cases the four inequalities pin $w$ to a single value, and that value is $yx$. **Exact** —
no approximation anywhere.

**Continuous × continuous.** Now $w = xy$ with $x \in [0,10]$, $y \in [0,4]$, evaluated at
$x=5, y=2$ where the true product is 10. The McCormick envelope gives

$$w \ge 0,\quad w \ge 10y + 4x - 40, \quad w \le 10y, \quad w \le 4x$$

At $(5,2)$: lower bounds $\max(0,\; 20 + 20 - 40) = 0$; upper bounds
$\min(20,\; 20) = 20$. So the envelope permits **any $w$ between 0 and 20** for a product that is
actually 10. The relaxation is valid — it never excludes the truth — but on its own it is far too
loose to *be* the answer. That gap is why continuous×continuous is a different league from
binary×continuous, and why §6 went to such lengths to avoid it.

**The grid route, concretely.** Restrict the leader to $q^L \in \{0, 15, 30, 45\}$ with binaries
$y_0 \ldots y_3$ summing to 1. Then

$$q^F q^L = \sum_k S_k\,(q^F y_k), \qquad S = (0, 15, 30, 45)$$

and each $q^F y_k$ is binary×continuous — exact. Four extra binaries and four auxiliaries buy you
an exact reformulation of a nonconvex term, at the cost of restricting the leader to four
quantities.
""")
    C(r'''
# Binary x continuous is exact; continuous x continuous is not. Both, numerically.
x, Mb = 7.0, 10.0
print("binary x continuous, x = 7, M = 10")
for y in (0, 1):
    lo = max(0.0, x - Mb*(1 - y))
    hi = min(Mb*y, x)
    print(f"  y={y}:  w in [{lo:.1f}, {hi:.1f}]   -> forced to {lo:.1f}   (y*x = {y*x:.1f})")

xL, xU, yL, yU = 0.0, 10.0, 0.0, 4.0
xv, yv = 5.0, 2.0
lo = max(xL*yv + xv*yL - xL*yL, xU*yv + xv*yU - xU*yU)
hi = min(xU*yv + xv*yL - xU*yL, xv*yU + xL*yv - xL*yU)
print(f"\ncontinuous x continuous at x={xv}, y={yv}  (true product {xv*yv:.0f})")
print(f"  McCormick envelope allows w in [{lo:.1f}, {hi:.1f}]  <- a bound, not an answer")
''')
    M(r"""
---

# 20. Comparing models that solve different problems

**The idea.** Before explaining a surprising comparison economically, check that the two models
were answering the same question. Usually they were not.

A planner has strictly more freedom than competing firms — it can choose any plan, including the
competitive one. So the planner's cost is a **lower bound** on competitive cost. If your
comparison says otherwise, **the comparison is wrong, not the theory.**

Part 4 hit exactly this: a naive comparison showed competition costing 9.5% *less* than the
planner. The cause was not economic. The planner was obligated to serve all demand while the firms
simply declined to serve ~4% of it, so the competitive outcome was **not in the planner's feasible
set**.

---

### By hand

Toy numbers with the same structure. The planner must serve all 100 units; the firms serve 96 and
walk away from 4.

| | volume served | total cost |
|---|---|---|
| planner (obligated) | 100 | 1000 |
| firms (competitive) | 96 | 905 |

**Naive:** $905/1000 - 1 = -9.5\%$. Competition looks 9.5% cheaper, which is impossible — and the
arithmetic is fine. The error is that the two numbers count different amounts of output.

**Repair 1 — match the volumes.** Re-solve the planner with an obligation of 96 units; suppose it
costs 903. Now $905/903 - 1 = +0.22\%$: the *productive* inefficiency of splitting output between
two firms, which is a real and small effect.

**Repair 2 — price what was not produced.** Those 4 units had value to someone. At a willingness
to pay of 84 each, the competitive outcome really costs $905 + 4(84) = 1241$, i.e. $+24\%$ against
the planner. That is inefficiency *plus* the unproduced units.

| Comparison | Result | Measures |
|---|---|---|
| Naive (different volumes) | −9.5% | nothing — invalid |
| Volume-matched | +0.22% | productive inefficiency of splitting output |
| Welfare-inclusive | +24% | inefficiency **plus** the unproduced units |

Both repairs are valid; they answer different questions, and you must say which one you ran. In
Part 4ab's real numbers are −8.8% naive, +0.96% volume-matched and +34.3%
welfare-inclusive — the same three-way pattern, on its own instance.

---

The same discipline applies to **objectives in different units**. A cost-minimising model and a
profit-maximising model cannot be compared by objective value. Fix the decisions from one and
re-price them through the other's accounting.

**The general rule:** when a result violates a bound you can prove, look first for a constraint
that differs between the two models — not for an economic explanation.
""")
    M(r"""
---

# 21. Risk measures: VaR, CVaR, and why the expectation is often the wrong objective

**The idea.** Minimising the average cost is right when you run the system many times. A supply
chain gets built once, so the interesting question is usually *how bad is bad* — and one particular
way of asking that turns out to be linear.

| Symbol | Meaning | Kind |
|---|---|---|
| $s \in \mathcal{S}$ | scenario | index |
| $\pi_s$ | probability of scenario $s$ | parameter |
| $\text{cost}_s$ | realised cost in scenario $s$ | variable (a model output) |
| $\alpha$ | tail fraction: 0.25 means "the worst quarter of outcomes" | parameter |
| $\eta$ | the VaR level — a free scalar the model chooses | **variable** |
| $z_s$ | how far scenario $s$ overshoots $\eta$ | variable |
| $\Lambda_{\text{mix}}$ | weight on the expectation in a hybrid objective | parameter |

| Measure | Definition | Problem |
|---|---|---|
| Variance | spread about the mean | penalises **upside** too; being unexpectedly cheap is not a risk |
| VaR$_\alpha$ | the $\alpha$-quantile of cost | says nothing about what lies beyond it; **non-convex** in the decisions |
| **CVaR$_\alpha$** | mean of the worst $\alpha$ fraction | convex, and exactly linearisable |

### The Rockafellar–Uryasev linearisation

$$\text{CVaR}_\alpha \;=\; \min_{\eta}\;\; \eta + \frac{1}{\alpha}\,
\mathbb{E}\big[(\text{cost}-\eta)^+\big]$$

Introduce $z_s \ge \text{cost}_s - \eta$ and $z_s \ge 0$:

$$\text{CVaR}_\alpha \;=\; \min_{\eta,z}\;\; \eta + \frac{1}{\alpha}\sum_s \pi_s z_s$$

One free scalar $\eta$, one $z_s$ per scenario, one constraint per scenario. **$\eta$ lands on the
VaR at the optimum without being told to.** It composes with everything — the network, the
vintages, the capacity logic are untouched, and in a decomposed solve the epigraph simply sits in
the master.

---

### By hand

Four scenarios, deliberately unequal probabilities:

| scenario | cost | $\pi_s$ |
|---|---|---|
| calm | 100 | 0.4 |
| mild | 150 | 0.3 |
| bad | 300 | 0.2 |
| severe | 500 | 0.1 |

Expected cost $= 0.4(100)+0.3(150)+0.2(300)+0.1(500) = 195$.

**Take $\alpha = 0.25$** — "the worst quarter". Walk down from the top: the severe scenario
supplies 0.10 of probability, the bad scenario supplies the remaining 0.15. So
VaR$_{0.25} = 300$ (the cost at which cumulative tail probability reaches 25%) and

$$\text{CVaR}_{0.25} = \frac{0.10(500) + 0.15(300)}{0.25} = \frac{50 + 45}{0.25} = \mathbf{380}$$

**Now check the formula finds it.** Evaluate $\eta + \frac{1}{0.25}\sum_s \pi_s(\text{cost}_s-\eta)^+$
at several $\eta$:

| $\eta$ | overshoot term | objective |
|---|---|---|
| 150 | $4[0.2(150)+0.1(350)] = 260$ | 410 |
| 250 | $4[0.2(50)+0.1(250)] = 140$ | 390 |
| **300** | $4[0.1(200)] = 80$ | **380** ← minimum |
| 310 | $4[0.1(190)] = 76$ | 386 |
| 400 | $4[0.1(100)] = 40$ | 440 |

The minimum is at $\eta = 300$, which is exactly the VaR — nobody told it to go there. Below the
VaR, raising $\eta$ costs 1 but saves more than 1 in scaled overshoot; above it, the reverse. The
kink is the quantile.

And note CVaR (380) is nearly double the expectation (195). *That* is what the risk-neutral
objective was averaging away.

---

### Three things that catch people out

**A uniform shock cannot change the plan.** If a disturbance scales every option equally it
rescales the objective and nothing else; risk aversion then moves the reported metric while
selecting the same design. Risk aversion needs something to hedge *between* — the shock must fall
unevenly. Part 2c's first instance had this bug and looked like it was working.

**Degeneracy: a tie-break is not a trade-off.** When many plans achieve the same CVaR — common,
because tail scenarios are often dominated by the same binding constraint — the solver returns an
arbitrary one, and "the CVaR plan" is not well defined. Adding a small weight $\Lambda_{\text{mix}}$
on the expectation then improves the mean at *zero* cost in CVaR. That looks impossible for a
genuine trade-off and is routine for a tie-break. Diagnose it by sweeping $\Lambda_{\text{mix}}$: a
discontinuous jump at $\Lambda_{\text{mix}} \to 0^+$ with CVaR unchanged is the signature.

**Choose $\alpha$ before looking at results.** $\alpha$ states which futures you are willing to be
unprepared for. Picking it after seeing the frontier fits the risk preference to the answer.

| Objective | Character |
|---|---|
| Risk-neutral | ignores the tail |
| CVaR$_\alpha$ | tail-aware, still uses probabilities |
| Robust | one scenario dictates everything; no probabilities needed |
| Hybrid $\Lambda_{\text{mix}}\mathbb{E}+(1-\Lambda_{\text{mix}})\text{CVaR}$ | usually dominates both — but check whether it is breaking a tie |

**When probabilities are contestable — a geopolitical act, say — robust or distributionally robust
is the honest choice.** Assigning a probability to an export control is a modelling claim a
reviewer can attack; a worst-case bound is not.
""")
    C(r'''
# CVaR two ways: directly from the tail, and from the Rockafellar-Uryasev program.
scen  = [(100, 0.4), (150, 0.3), (300, 0.2), (500, 0.1)]     # (cost, probability)
alpha = 0.25

mean = sum(c*p for c, p in scen)
ru   = lambda eta: eta + (1/alpha)*sum(p*max(0.0, c - eta) for c, p in scen)

print(f"E[cost] = {mean:.1f}\n")
print("  eta   |  RU objective")
for eta in (100, 150, 250, 300, 310, 400, 500):
    print(f" {eta:5d}  |  {ru(eta):8.1f}" + ("   <- minimum" if eta == 300 else ""))

grid  = [e/10 for e in range(0, 6001)]
eta_star = min(grid, key=ru)
print(f"\nminimising over a fine grid: eta* = {eta_star:.1f}, CVaR = {ru(eta_star):.1f}")
print(f"direct tail average       : {(0.10*500 + 0.15*300)/0.25:.1f}")
print(f"eta* equals VaR_{alpha}      : {eta_star == 300.0}")
''')
    M(r"""
---

# 22. Max-flow / min-cut, and network interdiction

**The idea.** Sometimes a hard bilevel problem collapses into an easy single-level one because of
a duality theorem. This is the cleanest example in the series.

| Symbol | Meaning | Kind |
|---|---|---|
| $a \in \mathcal{A}$ | an arc | index |
| $\kappa_a$ | capacity of arc $a$ | parameter |
| $f_a$ | flow on arc $a$ | variable |
| $\gamma_a$ | 1 if arc $a$ is in the cut | variable (dual) |
| $u_n$ | node potential — the dual of node $n$'s flow balance | variable (dual) |
| $\zeta_a$ | 1 if arc $a$ is attacked | variable |
| $\sigma_a$ | auxiliary replacing the product $\gamma_a(1-\zeta_a)$ | variable |
| $\delta^{+}(s)$ | the arcs leaving node $s$ | set |

**Max-flow / min-cut duality:** the maximum $s$–$t$ flow equals the minimum total capacity of any
set of arcs whose removal disconnects $s$ from $t$. As an LP pair:

$$\max \sum_{a \in \delta^+(s)} f_a
\qquad\Longleftrightarrow\qquad
\min \sum_a \kappa_a \gamma_a \;\;\text{s.t.}\;\; \gamma_{ij} - u_i + u_j \ge 0,\;\; u_s - u_t \ge 1$$

The right-hand program is just the LP dual of the left. Read it as: give every node a "height"
$u_n$, require the source to be one unit above the sink, and pay for every arc that has to run
downhill. Cheapest way to do that = the min cut.

### Why this matters for interdiction

An attacker choosing arcs to remove, against an operator who reroutes optimally, is a max-min:

$$\min_{\zeta} \; \max_{f} \; \text{flow}$$

Bilevel, and normally painful (§18). But substituting min-cut for the inner max gives

$$\min_{\zeta} \; \min_{\text{cut}} \;(\cdot) \;=\; \min_{\zeta,\,\text{cut}} \;(\cdot)$$

**Two nested minimisations are one minimisation.** The bilevel problem becomes a single MILP — no
KKT block, no complementarity, no big-M.

### The one linearisation you need

Interdicting arc $a$ zeroes its capacity, giving a bilinear $\kappa_a(1-\zeta_a)\gamma_a$. Replace
it:

$$\sigma_a \;\ge\; \gamma_a - \zeta_a, \qquad \sigma_a \ge 0,
\qquad \text{minimise } \sum_a \kappa_a \sigma_a$$

Because the objective is minimised and $\kappa_a \ge 0$, $\sigma_a$ takes its lower bound:
$\gamma_a$ when the arc survives, $0$ when it is cut. **No big-M appears**, which is why this
formulation is numerically well behaved where a naive one is not.

---

### By hand

Five arcs, capacities in brackets:

```
         ┌──[3]──> a ──[2]──┐
         │         │        v
         s        [1]       t
         │         │        ^
         └──[2]──> b ──[3]──┘
```

$\;s\!\to\!a\,[3],\quad s\!\to\!b\,[2],\quad a\!\to\!b\,[1],\quad a\!\to\!t\,[2],
\quad b\!\to\!t\,[3]$ — all arcs point left-to-right, and the middle $[1]$ runs downward from
$a$ to $b$.

**Max flow.** Push 2 along $s\!\to\!a\!\to\!t$, 2 along $s\!\to\!b\!\to\!t$, and 1 more along
$s\!\to\!a\!\to\!b\!\to\!t$. Check every arc: $s\!\to\!a$ carries 3 ✓, $s\!\to\!b$ carries 2 ✓,
$b\!\to\!t$ carries $2+1 = 3$ ✓. **Max flow = 5.**

**Min cut.** Enumerate which nodes sit on the source side:

| source side $S$ | arcs crossing out | capacity |
|---|---|---|
| $\{s\}$ | $s\!\to\!a,\; s\!\to\!b$ | $3+2 = $ **5** |
| $\{s,a\}$ | $a\!\to\!t,\; a\!\to\!b,\; s\!\to\!b$ | $2+1+2 = $ **5** |
| $\{s,b\}$ | $s\!\to\!a,\; b\!\to\!t$ | $3+3 = 6$ |
| $\{s,a,b\}$ | $a\!\to\!t,\; b\!\to\!t$ | $2+3 = $ **5** |

Minimum = 5 = max flow ✓. Note **three cuts tie at 5** — degeneracy is the normal case in
networks, and §23 explains why that is precisely what governs how long the defender's algorithm
runs.

**Interdiction with a budget of one arc.** Try each:

| arc removed | remaining max flow |
|---|---|
| $s\!\to\!a$ | **2** |
| $b\!\to\!t$ | **2** |
| $s\!\to\!b$ | 3 |
| $a\!\to\!t$ | 3 |
| $a\!\to\!b$ | 4 |

The attacker cuts $s\!\to\!a$ (or $b\!\to\!t$) and takes throughput from 5 to 2.

**And the $\sigma$ trick, on these numbers.** For the cut $S=\{s\}$ take $\gamma_{s\to a} =
\gamma_{s\to b} = 1$ and all other $\gamma = 0$; heights $u_s = 1$, everything else 0 satisfies
$\gamma_{ij} \ge u_i - u_j$. Undisturbed objective $3(1) + 2(1) = 5$ ✓. Now attack $s\!\to\!a$, so
$\zeta_{s\to a} = 1$: the constraint $\sigma_a \ge \gamma_a - \zeta_a$ gives
$\sigma_{s\to a} \ge 0$ and $\sigma_{s\to b} \ge 1$, and minimisation drives each to its bound:

$$\sum_a \kappa_a\sigma_a = 3(0) + 2(1) = \mathbf{2}$$

— which is exactly the interdicted max flow computed above. The reformulation closes on the same
number, without a single big-M.

---

### Modelling cautions

**Decide what is attackable, and defend the choice.** Super-source and super-sink arcs are
modelling artifacts — a reserve base, a demand aggregate — not links anyone can sever. Leave them
interdictable and a small budget trivially severs the network, making every downstream analysis
vacuous. This happened: with the super-source arcs attackable, a budget of 3 severed everything
and every defence analysis returned zero.

**Verify the collapse.** Take the attack the MILP selects, solve the operator's max-flow directly
on the surviving network, and confirm the values agree. A sign error still produces a plausible
attack.
""")
    C(r'''
# A five-arc network: max flow, every cut, and the best single-arc attack.
from collections import defaultdict, deque

ARCS = {("s","a"): 3, ("s","b"): 2, ("a","b"): 1, ("a","t"): 2, ("b","t"): 3}
NODES = sorted({n for arc in ARCS for n in arc})

# THE FUNCTION IS THE LESSON: max-flow is the primitive sections 22 and
# 23 are built on, and it is called from four places below.
def max_flow(cap, src="s", snk="t"):
    res = defaultdict(int)
    for (u, v), k in cap.items():
        res[(u, v)] += k
    flow = 0
    while True:
        par, q = {src: None}, deque([src])
        while q:
            u = q.popleft()
            for v in NODES:
                if v not in par and res[(u, v)] > 0:
                    par[v] = u; q.append(v)
        if snk not in par:
            return flow
        path, v = [], snk
        while par[v] is not None:
            path.append((par[v], v)); v = par[v]
        b = min(res[e] for e in path)
        for u, v in path:
            res[(u, v)] -= b; res[(v, u)] += b
        flow += b

print(f"max flow = {max_flow(ARCS)}\n")
print("cuts (source side S -> capacity crossing out):")
for r in range(3):
    for S in combinations(["a", "b"], r):
        Sset = {"s"} | set(S)
        val = sum(k for (u, v), k in ARCS.items() if u in Sset and v not in Sset)
        print(f"  S = {str(sorted(Sset)):<16} capacity {val}"
              + ("   <- minimum" if val == 5 else ""))

print("\nsingle-arc interdiction:")
for a in ARCS:
    cut = {k: (0 if k == a else v) for k, v in ARCS.items()}
    print(f"  remove {a[0]}->{a[1]}:  flow = {max_flow(cut)}")
''')
    M(r"""
---

# 23. Trilevel programs and Best Response Intersection

**The idea.** Add a defender in front of the attacker and you have three nested optimisations.
You cannot write that down and press solve — but you can collapse the inner two by duality and
attack the outer one by generating attacks only as you need them.

| Symbol | Meaning | Kind |
|---|---|---|
| $\phi_a$ | 1 if arc $a$ is fortified (immune to attack) | variable |
| $\zeta_a$ | 1 if arc $a$ is attacked | variable |
| $z^j_a$ | attack pattern $j$, **already known and fixed** | parameter |
| $\theta$ | the flow the defender is guaranteeing | variable (epigraph) |
| $\mathcal{J}$ | the set of attacks retained so far | set |
| $\bar\kappa_a^{\,j}(\phi)$ | capacity of arc $a$ surviving attack $j$ given fortification $\phi$ | expression |

Section 18 collapsed a **bilevel** program with the follower's KKT conditions. Interdiction adds a
third level:

$$\max_{\text{defend}} \;\; \min_{\text{attack}} \;\; \max_{\text{operate}} \;\; (\cdot)$$

Read outward: the operator routes around damage; the attacker picks damage that survives good
routing; the defender fortifies anticipating the attacker. This is the
**defender–attacker–defender** (DAD) structure. Each level anticipates everything inside it.

The standard treatment: **collapse the inner two by duality** (§22), then **decompose the outer**.

### Best Response Intersection

$$
\textbf{NDP:}\;\; \max_{\phi,\theta} \theta \;\;\text{s.t.}\;\; \theta \le \text{flow}_j(\phi)\;
\forall j \in \mathcal{J}
\qquad\qquad
\textbf{ABR:}\;\; \min_{\text{attack}} \max_{\text{operate}} \text{flow}
$$

Solve the defender's master (NDP) over a *retained set* of attacks, take its fortification, find
that fortification's worst attack (ABR), add it to the set, repeat. $\theta$ falls — it is an
**upper bound**, because you are only defending against a subset of attacks — while the ABR value
rises as a **lower bound**. They meet.

**The step that keeps the master linear.** For a *fixed* attack pattern $z^j$, surviving capacity
is

$$\bar\kappa_a^{\,j}(\phi) \;=\; \kappa_a\big(1 - z^j_a(1-\phi_a)\big)$$

$z^j$ is a constant, so this is linear in $\phi$: an unattacked arc keeps $\kappa_a$; an attacked
arc keeps $\kappa_a \phi_a$. Each retained attack contributes an ordinary max-flow LP block, and
the whole master is a plain MILP.

---

### By hand

Same five-arc network as §22. Attacker budget 1; defender budget 2.

**Baseline:** undefended, the attacker cuts $b\!\to\!t$ and takes flow from 5 down to **2**. Seed
the retained set with that one attack.

| it | $\mathcal{J}$ (retained attacks) | defender picks $\phi$ | $\theta$ (UB) | ABR of that $\phi$ | best guarantee so far | new attack added |
|---|---|---|---|---|---|---|
| 1 | $\{b\!\to\!t\}$ | $\{s\!\to\!a,\, b\!\to\!t\}$ | 5 | 3 | **3** | $a\!\to\!t$ |
| 2 | $+\,\{a\!\to\!t\}$ | $\{a\!\to\!t,\, b\!\to\!t\}$ | 5 | 2 | 3 | $s\!\to\!a$ |
| 3 | $+\,\{s\!\to\!a\}$ | $\{s\!\to\!a,\, b\!\to\!t\}$ | **3** | 3 | **3** | — converged |

Walk iteration 1: the defender only knows about the attack on $b\!\to\!t$, so it protects that arc
(plus one more), and against *that single attack* the network still carries its full 5. It is
defending against a strawman — which is why $\theta = 5$ is an **upper bound**, not an answer.
Reality says an attacker facing this fortification switches to $a\!\to\!t$ and holds flow to 3, so
3 is what this fortification actually guarantees.

Iteration 2 is worth noticing: the master, now aware of two attacks, picks a *different*
fortification whose true guarantee is only 2 — **worse than iteration 1**. That is not a bug. The
ABR value is a lower bound *for the fortification just proposed*, not a running best; the
defender's incumbent is the best guarantee seen so far, and it never falls. Only $\theta$ is
required to be monotone.

By iteration 3 the retained set is rich enough that the master's optimism is squeezed out:
$\theta$ drops from 5 to 3 and meets the incumbent. **Answer: fortify $s\!\to\!a$ and
$b\!\to\!t$, guaranteeing 3 units against any single-arc attack**, up from 2 undefended.

Three iterations, against $\binom{5}{2} = 10$ fortifications $\times$ 5 attacks by enumeration.
Part 4f's real instance: **3–6 iterations**, matching full enumeration exactly, where at a defence
budget of 4 over 27 arcs enumeration needs $\binom{27}{4} = 17{,}550$ attacker solves — roughly
2,900× fewer, and the gap is a certificate rather than an estimate.

### Why it terminates quickly

Most attacks are never a best response to **anything**. The search is not over attacks but over
the much smaller set that sits on the boundary between defensive postures — the *intersection* of
the best responses. Worst case is exponential; practice is governed by the number of near-tied
cuts, which is why §22's observation that three cuts tied at 5 was not an idle remark.

### The trap this method exposed

Pruning the defender's candidate arcs to those the attacker chooses in the **undefended** problem
looks like an obvious economy — why fortify an arc nobody attacks? It is a silent heuristic, and
it reported a worse optimum while looking entirely reasonable, because fortifying an arc *changes
which attacks are rational*. The best two-arc defence in Part 4f protects one arc that nobody
attacks today, precisely because protecting the obvious arc pushes the attacker onto a different
cut. The restriction cost 5 units of throughput, and it also manufactured a tidy false finding —
that the second unit of defence bought nothing, a clean diminishing-returns story that was
entirely an artifact.

**Defence is a response to the attacker's response.** Any pruning that uses the undefended attack
pattern assumes away the mechanism the model exists to capture.
""")
    C(r'''
# Best Response Intersection on the five-arc network. Defender budget 2, attacker budget 1.
# The master is solved by enumeration here so the loop itself stays visible.
DEF_BUDGET, ATT_BUDGET = 2, 1

# THE FUNCTION IS THE LESSON: the three-level structure is exactly these
# two functions nested - operator inside attacker inside the loop below.
def flow_under(fort, attack):
    cap = {k: (0 if (k in attack and k not in fort) else v) for k, v in ARCS.items()}
    return max_flow(cap)

def attacker_best_response(fort):
    return min((flow_under(fort, set(att)), att)
               for att in combinations(ARCS, ATT_BUDGET))

nm = lambda arcs: "{" + ", ".join(f"{u}->{v}" for u, v in arcs) + "}"
lb0, att0 = attacker_best_response(frozenset())
print(f"undefended: attacker takes flow to {lb0} via {nm(att0)}\n")

J = [att0]
incumbent, best_known, trace = -1, None, []
print(" it | |J| | defender fortifies      | theta(UB) | ABR | incumbent | adds")
for it in range(1, 8):
    best_phi, best_theta = None, -1
    for phi in combinations(ARCS, DEF_BUDGET):                       # the NDP master
        th = min(flow_under(set(phi), set(j)) for j in J)
        if th > best_theta:
            best_theta, best_phi = th, phi
    lb, worst = attacker_best_response(set(best_phi))                # the ABR subproblem
    if lb > incumbent:                                               # incumbent never falls
        incumbent, best_known = lb, best_phi
    done = best_theta <= incumbent
    print(f" {it:2d} | {len(J):2d}  | {nm(best_phi):<23} |  {best_theta:5d}    | {lb:3d} |"
          f"   {incumbent:5d}   | " + ("converged" if done else nm(worst)))
    trace.append((best_theta, lb, incumbent))
    if done:
        break
    J.append(worst)

print(f"\nbest fortification {nm(best_known)}")
print(f"guaranteed flow rises from {lb0} (undefended) to {incumbent} with {DEF_BUDGET} fortifications")

# The trace above is NOT reproducible and the invariants ARE. Measured across
# all 120 orderings of the five arcs: the final value, the fortification and the
# iteration count are identical every time, but the intermediate column takes
# one of two forms depending on which of several equally-good fortifications the
# master happens to return first. So assert what holds, and read the rest as one
# possible history rather than the history.
assert all(trace[i][0] >= trace[i + 1][0] for i in range(len(trace) - 1)), \
    "theta rose: the master gained information and got MORE optimistic"
assert all(trace[i][2] <= trace[i + 1][2] for i in range(len(trace) - 1)), \
    "the incumbent fell: it is a max over evaluated fortifications and cannot"
assert all(inc <= th for th, _lb, inc in trace), \
    "the incumbent exceeded theta: a feasible plan beat the upper bound"
print(f"\ninvariants hold: theta {[t[0] for t in trace]} never rises, "
      f"incumbent {[t[2] for t in trace]} never falls, and incumbent <= theta throughout")
print("the ABR column is NOT monotone and NOT reproducible - see the note below")
''')
    M(r"""
### Why the middle column is not a result

The table above has three numeric columns and **they do not have the same
status**, which is the point of this section and a habit worth carrying into
every iterative method in the series.

`theta` is the master's optimistic bound. It can only fall, because each new
attack in `J` removes optimism and never adds it. The `incumbent` can only rise,
because it is a running maximum over fortifications that have actually been
evaluated. Those two are **invariants**, and the cell above asserts all three of
them — including that the incumbent never exceeds theta, which is what makes the
stopping rule sound.

The `ABR` column is neither. It is whatever the master happened to propose this
iteration, and the master is choosing among fortifications that are frequently
**tied**. Re-order the five arcs and it may pick a different one of the tied
options, producing a different intermediate history.

Measured across all 120 orderings of these five arcs:

| | distinct values |
|---|---|
| final guaranteed flow | **1** |
| best fortification set | **1** |
| iteration count | **1** |
| **the intermediate trace** | **2** |

So the answer is completely stable and the path is not. An earlier version of
this notebook printed a sentence about what happens *at iteration 2* — and that
sentence was true for half the orderings and false for the other half, with no
way for a reader to tell which they had got.

**This is the general fix for a degenerate trace**, and the series uses it more
than once: where several answers tie, do not narrate the path. Assert the
quantities that must hold whatever the tie-break does, and say plainly that the
rest is one possible history. Part 4f does the same thing when it compares Best
Response Intersection against enumeration on the *value* and not on the
fortification.
""")

    M(r"""
---

# Where to go next

| If you are reading... | ...you mainly need |
|---|---|
| Part 1 (deterministic) | §1–3, §7–10 |
| Part 2 (stochastic) | §11–13, and §2 for what a gap means |
| Part 2b (Benders) | §14, after §2 |
| Part 2c (risk) | §21, after §11 |
| Part 3 / 3b (network core, learning) | §4–7, §9, §10 |
| Part 4a–4c (planner, game, Cournot) | §15–17, §20 |
| Part 4d (Stackelberg MPEC) | §18–19, after §17 |
| Part 4e (policy instruments) | §17, §20 |
| Part 4f (interdiction) | §22–23, after §14 |
| Part 5 (integrated core) | §4–7, §9, §10, and §1 for semi-continuous sizing |

---

## Further reading

- Rockafellar & Wets (1991), *Scenarios and policy aggregation in optimization under
  uncertainty* — the PH paper
- Eckstein, Watson & Woodruff (2025), *Projective hedging algorithms*, Operations Research 73(1)
- Birge & Louveaux, *Introduction to Stochastic Programming* — EVPI/VSS, L-shaped method
- Gade et al. (2016); Boland et al. (2018) — Lagrangian bounds from PH on mixed-integer problems
- Conejo et al., *Decomposition Techniques in Mathematical Programming*
- Gurobi documentation on `addSOS`, semi-continuous variables, and indicator constraints
- Tirole, *The Theory of Industrial Organization* — Cournot, Stackelberg, entry deterrence
- Luo, Pang & Ralph, *Mathematical Programs with Equilibrium Constraints*
- Gabriel et al., *Complementarity Modeling in Energy Markets*
- Dempe, *Foundations of Bilevel Programming*
- Rockafellar & Uryasev (2000), *Optimization of conditional value-at-risk* — the CVaR linearisation
- Shapiro, Dentcheva & Ruszczyński, *Lectures on Stochastic Programming* — risk measures, SAA
- Wood (1993), *Deterministic network interdiction* — the max-flow interdiction MILP
- Brown, Carlyle, Salmerón & Wood (2006), *Defending critical infrastructure*, Interfaces 36(6) — DAD
- Smith & Song (2020), *A survey of network interdiction models and algorithms*, EJOR
""")

    return out

# Multi-Period Supply Chain MILP — Project Journal

*A record of what was built, what broke, and what the failures taught. Part summary, part
lab notebook.*

---

## What exists

| Notebook | Subject | Status |
|---|---|---|
| **Part 0** | Concepts guide — notation section + 23 sections, worked numeric examples, runnable demos | verified, 0 errors |
| **Part 1** | Deterministic: capex accounting, granularity, learning, rolling horizon | verified, 11 figures |
| **Part 2** | Stochastic: EV / PI / SP, EVPI & VSS, progressive hedging, APH | verified, 10 figures |
| **Part 3** | Network-core MILP: semi-continuous sizing, explicit arcs | verified, 10 figures |
| **Part 3b** | Production-based learning, utilization, local content lever | verified, 0 errors |
| **Part 4a/4b** | Cooperative planner → two-firm game at fixed price | verified, 0 errors |
| **Part 4c** | Cournot with endogenous price | verified, 1 figure |
| **Part 4c-exact** | Same as MIQP; measures the approximation error | verified (small config) |
| **Part 4d** | Stackelberg as a single-level MPEC | verified, 0 errors |
| **Part 4e** | Policy instruments: tariffs, quotas, local content | verified, 1 figure |

Ten notebooks plus this journal — the **instructional series**, complete.

### Production track (added August 2026)

A second series, aimed at the large lithium model rather than at teaching. These are meant to be
scaled; the ten above are not.

| Notebook | Subject | Status |
|---|---|---|
| **Part 5** | Integrated deterministic core: six stages, recycling loop, dual feedstock, regression harness | verified, 0 errors |
| **Part 2b** | Benders / L-shaped — exploits the LP core, exact with integer first stage | verified, 0 errors |
| **Part 2c** | CVaR, robust, hybrid objectives | verified, 0 errors |
| **Part 4f** | Interdiction: defender–attacker–operator, min-cut duality + Best Response Intersection | verified, 0 errors |

---

## What the production track found

**The collapse invariant only holds in the LP.** Part 5 tests that a multi-region model with free
trade equals a one-region model carrying summed demand. It does — to 1.6e-15 — but **only under
relaxation**. In the MILP the same test shows a 0.6% discrepancy, because semi-continuous sizing
gives the two configurations genuinely different feasible sets: two facilities at `cap_min` is a
reachable point that one facility at `2 × cap_min` is not. A regression test run on the MILP would
have been measuring lumpiness, not correctness.

**`m.relax()` without `m.update()` silently returns an empty model.** It solves to 0, is trivially
feasible, and passes any test written against it. Both collapse figures were exactly `0.000000`
before the fix. This belongs on the bug list below — it produced perfectly plausible output.

**Dual feedstock is worth 2.2% on the demo instance.** Letting one facility accept both virgin and
recycled input, rather than having recycling bypass processing entirely, is the minimal change that
makes the policy-brief recommendation expressible — and therefore testable.

**Multicut Benders converged in 15 iterations against 22 for single-cut**, both to the extensive
form value exactly. The gap is a certificate at every iteration, which progressive hedging cannot
provide once the first stage has integers.

**CVaR was degenerate, and that is why the hybrid wins.** Many plans achieved identical CVaR, so
"the CVaR plan" was whatever branch-and-bound happened to return. A tiny weight on the expectation
is not buying a trade-off — it is **breaking a tie**, which is why it can improve the mean by 19%
at *zero* cost in CVaR. Diagnosed from a non-monotone λ sweep.

**A uniform cost shock cannot change the plan.** The first CVaR instance scaled every region
equally, so risk aversion moved the reported metric and nothing else. Only once the shock fell
unevenly — R1 cheap but occasionally disrupted, R2 dearer and steady — did the risk-averse plan
diverge from the risk-neutral one. Risk aversion needs something to hedge *between*.

**Restricting the defender's candidate arcs is not an economy — it is a silent heuristic.** I limited
fortification candidates to arcs the attacker chooses in the *undefended* problem, on the reasoning
that protecting an unattacked arc is wasted budget. That reasoning is wrong, and BRI caught it: the
two-arc optimum protects one upstream arc **and** one downstream arc that nobody attacks today,
because fortifying the obvious one pushes the attacker onto a different cut. The restriction cost 5
units of throughput and reported the wrong optimum while looking entirely reasonable.

It also manufactured a false finding. Under the restriction, the second unit of defence appeared to
buy **nothing** — a clean diminishing-returns story that I had already written up as an echo of Part
4e's "steps, not slopes". With the full candidate set the second unit recovers 14 of 54 rather than
9. The tidy result was an artifact of the shortcut. **Defence is a response to the attacker's
response**, so anything that prunes the defender's options using the *undefended* attack pattern
assumes away the mechanism.

**Max-flow/min-cut duality removes every big-M from the interdiction model.** The attacker's
bilevel problem collapses to a single MILP with no complementarity block and no tuned constant —
the cleanest instance in the series of structure buying exactness.

**Restricting what is attackable is a modelling decision, not a detail.** With the super-source arcs
interdictable, an attacker with budget 3 severed the network completely and every defence analysis
returned zero. Those arcs are a modelling artifact — a reserve base, not a physical link. Excluding
them turned a degenerate problem into one where the mine→refining transition emerges as the
bottleneck on its own.

**Best Response Intersection converged in 3–6 iterations and matched full enumeration exactly.**
The master stays linear because for a *fixed* attack pattern $z^j$ the surviving capacity
$\kappa_a(1 - z^j_a(1-\phi_a))$ is linear in the fortification $\phi$ — so each retained attack adds
an ordinary max-flow LP block and the defender's problem is a plain MILP. At a defence budget of 4
over 27 arcs, enumeration needs 17,550 attacker solves; BRI needed 6 iterations and 0.10 s. Roughly
2,900×, and the gap is a certificate rather than an estimate.

**Why BRI terminates so fast.** The retained attack set stays tiny because most attacks are never a
best response to *anything*. The search is not over attacks; it is over the much smaller set of
attacks that sit on the boundary between defensive postures. Worst case is still exponential — what
governs practice is the number of near-tied cuts, not $\binom{|A|}{B}$.

---

## How the model evolved

**Parts 1–2** — aggregate stage balances, integer counts of fixed-size units, annual periods.
Sufficient to isolate capex accounting, period granularity, learning formulation, and the
foresight/uncertainty distinction.

**Part 3** — rebuilt as an explicit network on your specification: nodes, arcs, arc costs, integers
confined to a capacity layer over an LP core. Semi-continuous sizing replaced integer unit counts
— *fewer* binaries and a *finer* decision space simultaneously.

**Part 3b** — learning driver switched from installed capacity to cumulative production, which broke
SOS2 and forced disjunctive tiers.

**Part 4** — one objective became two, then two players. Vertical integration within regions avoided
needing transfer prices between rivals; competition moved downstream.

The single most consequential decision was made in Part 3: **keep flows continuous, put integers only
on investment.** It is what made Benders available in principle and what made the Part 4d MPEC
possible at all. A follower whose operational problem contained binaries would have had no usable
KKT conditions.

---

## The corrections that mattered

### You caught the VSS methodology error

I computed RP from `ef.ObjVal` — a gap-terminated solve value — while EEV came from the evaluation
path. Two different measurements, differenced, producing **VSS = −0.06%**, which is impossible.

Root cause: the extensive form stopped 22.78 above its true optimum inside a 0.5% tolerance, while
the evaluation path re-solved stage 2 exactly. I had dismissed it as rounding. It was not.

Fix: one function routing all three cases through identical machinery, with
`RP_evaluated == ef.ObjVal` as a built-in plumbing assertion.

### You caught the planner-bound violation

"Cost of rivalry" came out **negative** — competition apparently cheaper than a planner, which cannot
be. I had narrated it as a quantity distortion, which was incomplete and nearly wrong.

Root cause: the planner was obligated to serve all demand; the firms simply declined to serve ~4%.
The competitive outcome was **not in the planner's feasible set**.

| Comparison | Result |
|---|---|
| Naive | −9.5% (invalid) |
| Volume-matched | +0.21% |
| Welfare-inclusive | +33.6% |

### You were right about the learning driver

Wright's law is about cumulative *production*; a built-and-idled plant learns nothing. This was not a
detail — it is the precondition for flooding to be rational, and therefore for the whole of Part 4c.

### You were right about the three-tier LBD idea I argued against

I dismissed threshold tiers in favour of SOS2. That critique assumed SOS2 was available. Once the
curve's argument became production, the cost term went bilinear and SOS2 was off the table —
**disjunctive tiers became the principled answer.** I owed you that correction and it is recorded in
Part 0 §6.

### You called the capacity-learning effect being muted by model size

Correct, and it sharpened into a structural finding: capacity learning moves the plan at LR ≥ 0.08;
production learning never does, at *any* rate up to 0.75. Not a magnitude question —
**learning drives decisions when its driver is itself a decision variable.** Capacity is chosen;
production was determined by demand until Part 4 unpinned it.

---

## Bugs found by verification, not by reading

Every one of these produced plausible output.

**Chained assignment** — a patch created `dfW = rowsW = rows`, binding a DataFrame name to a list.
Caught by execution, not by review.

**Notebook cell ordering** — plot cells inserted before the cells defining their variables. A static
scope checker (AST-based, ignoring Jupyter magics) now runs on every notebook.

**Stale embedded source** — Part 2 carried an older snapshot of `build()` without the `mipgap`
argument. Notebooks that embed source must be regenerated when the source changes.

**Gurobi flattens tuple keys** — `addVars(list_of_tuples, P)` yields 3-tuple keys, not
`((s,r), p)`. Silent `KeyError` at construction.

**Default-argument capture** — `_rev_breakpoints(..., n=NBP_REV)` froze the module value at
definition time, so sweeping `NBP_REV` had no effect on the mesh.

**License limits differ by problem class** — the restricted license allows ~2000 vars for LP/MILP but
only ~150 for QP/MIQP. Discovered by probe, not documentation.

**`Model.relax()` before `Model.update()`** — returns an *empty* model. It solves to zero, reports
`OPTIMAL`, and passes any assertion written against it. Guard with `assert relaxed.NumConstrs > 0`.

---

## Diagnostics worth keeping

**Print the SOS2 λ values.** Two adjacent nonzeros means the curve is working. One means you built a
step function. Non-adjacent means SOS2 is not being enforced.

**Check breakpoint placement, not just density.** Part 3's mesh spanned to 2,200 while the solution
reached 1,174 — three of nine breakpoints never used, chords coarsest exactly where the answer lived.
Re-meshing *raised* the objective, confirming the coarse mesh had been understating a concave cost.
Solve once, read the realised range, re-mesh.

**Verify an MPEC against a direct solve.** Take the leader's solution, solve the follower's problem
independently, confirm the embedded KKT block reproduces it. Part 4d matches to machine precision. A
sign error or an undersized big-M yields a model that still solves and still looks reasonable.

**Assert the theory in code.** `WS <= RP <= EEV`. `RP_evaluated == ef.ObjVal`. Planner cost ≤
competitive cost at matched volume. When these fail, the plumbing is wrong, not the economics.

**Check whether scenarios disagree before going stochastic.** VSS is nonzero *exactly when* the
mean-forecast and stochastic solutions choose differently. One extra solve can save a formulation you
do not need.

---

## Findings

**Discounting sets the effective model length.** At 5%, 90% of a perpetual stream arrives by year 48;
at 10%, by year 25. Horizon truncation, late-build accounting, and rolling-horizon window length are
the same question in different clothes.

**Lump-sum capex refuses to build late** — nothing in the final period, 342 units unmet vs 24. With a
cool-down buffer *and* annualisation the effect nearly vanishes; they are two fixes for one bias.

**Rolling horizon at W = T reproduces perfect foresight exactly** (Bellman), so it buys nothing. All
tractability comes from W < T. Banning tail investment costs +22% and doubles early builds.

**Exogenous learning is the cheapest of three modes** — that is the free lunch, visible as a number.

**A large EVPI does not imply you need a stochastic model.** At one penalty level EVPI is 4.9% while
VSS is exactly zero: foresight is worth a great deal, and the point forecast still picks the right
first move.

**Coarse scenario trees bias EVPI and VSS upward**, not merely noisily. VSS falls from 7.3% at 3
scenarios to 3.3% at 20. Never quote VSS from a handful of scenarios.

**Progressive hedging is not monotone in ρ.** Small ρ never agrees, large ρ snaps to a poor point,
intermediate values cycle. Always sweep.

**Production learning changed no decision under cost minimisation** — cumulative production was pinned
by demand. Once quantity became a decision in Part 4c, output rose 13% and price fell. **Learning also
amplifies incumbency**: the firm further along the curve gains more per marginal unit.

**Pump-and-dump never pays under cost minimisation** — not even with free disposal and LR = 55%, since
utilisation is already 90%+ and dumping would require building. Flooding is a *competitive*
phenomenon, and when it appears it works through **sales at a depressed price**, not disposal.

**Fixed price manufactured a first-mover advantage.** 29% at fixed price, ~4% under Cournot. Price
adjustment substitutes for rationing. Results that depend on a rationing rule deserve suspicion.

**Commitment is worth ~20% of leader profit**, and it suppresses the follower's *capital formation* —
the durable form of deterrence, which then compounds through the learning channel.

**Tariffs redistribute and shrink.** Protection lifts R2's profit 6,713 → 11,124 but total welfare
falls 38,995 → 35,859 at every level tested; deadweight loss exceeds revenue collected, and tariff
revenue plateaus as rising rates shrink the base they are levied on.

**Quotas are dominated by tariffs.** A quota of 10 delivers protection comparable to a tariff of 9,
but collects **zero** revenue — the scarcity rent goes uncollected, so welfare is strictly worse for
the same distortion.

**Local content requirements can backfire on their intended beneficiary.** At a floor of 70, R2's
profit *falls* (6,713 → 5,289) while R1's rises. A tariff raises a rival's cost; a quantity mandate
constrains *your own* firm's optimisation, and if it binds in an unwanted direction it destroys value
domestically.

**Entry deterrence is robust to moderate intervention, then breaks suddenly.** Follower capacity is
completely unmoved (60.45) at tariffs of 0, 3 and 6 — the leader absorbs the duty and holds its
committed quantity — and only jumps to 88.27 at a tariff of 10. **Policy responses are steps, not
slopes**, which is the lumpy-investment structure of the whole series reappearing at the policy
level. Interpolating between a few tariff levels would have concluded the instrument was useless.

---

## Two lessons about method

**Approximation error inside an equilibrium is not the same animal as inside an optimisation.**
Piecewise revenue understates a single best response by 0.25% at 7 breakpoints, signed and bounded
exactly as theory predicts. At the *equilibrium* the error changes sign and reaches 12%, because each
firm's error perturbs its rival's problem and the perturbations compound around the loop. Validate a
discretisation at the level you report.

**Whether you need SOS2 depends on curvature and direction together.** Concave-and-minimised (Part 3's
learning curve) is dangerous. Concave-and-maximised (Part 4c's revenue) is safe — no SOS2, no
binaries. Same shape, opposite requirement.

---

## If the project continues

**Complete Part 4c-exact §6.** The collusion benchmark is still piecewise while Cournot is exact, so
that table mixes methods. Given the §4 finding, write `joint_profit_max_miqp`.

~~**Benders / L-shaped.**~~ Done — Part 2b. Multicut converged in 15 iterations against 22 for
single-cut, both to the extensive-form optimum exactly.

**Scale up — four targets, not ten.** Only where a reported finding is size-sensitive:
VSS/EVPI at 200–500 scenarios (already known to be a size artifact: 7.3% at 3 scenarios, 3.3% at 20);
the PH ρ sweep at 500–1,000; `Part4c_exact_MIQP` at full horizon; and Part 3's capacity-learning
effect, which was explicitly muted by model size. The rest of the instructional series stays small on
purpose — a 44k-variable notebook is not a demo.

**Wire Layer 2 of the Part 5 regression harness.** The hook takes a cfg dict, not a directory, and
`input_csvs/` is shaped differently: costs keyed by (Year, Stage, Input, Output) rather than scalar
per stage, and 2–4 technologies per stage where Part 5 has one commodity. Reaching \$9.51T needs the
technology index added to Part 5 first. The cheaper path is to retarget the test at *"Part 5
configured to match the original notebook reproduces the original notebook's objective"* and tighten
toward \$9.51T as features land. Assigned to a student.

**Endogenise policy.** Part 4e's levers are exogenous by design. Real trade policy is itself a game —
retaliation, strategic tariff-setting — which would make the model trilevel. Part 4f now has the
trilevel machinery, so this is closer than it was, but it remains a research project rather than a
notebook section.

**Couple Part 4f to Part 5.** The interdiction layer currently attacks a single-period network. Over
Part 5's multi-period core with its recycling loop it would answer something neither model can today:
*does recycling capacity built for cost reasons also harden the chain, and by how much?* That is also
the cleanest point of contact with the LLNL interdiction work, whose model is single-period with no
recycling.

---

## Reproducibility notes

- Every notebook was executed end-to-end in a fresh kernel; error counts reported above are from
  those runs. Fourteen notebooks: ten instructional, four production-track.
- The instructional series fits the restricted `pip` license (~2,000 vars) except the exact MIQP
  sections. The production-track notebooks pick up `gurobi.lic` from the folder if present and fall
  back to the restricted license otherwise.
- `Part4c_exact_MIQP` was verified at `SMALL = True` (3 periods); full-scale sections require a WLS
  license and were **not** run by me.
- Part 5's Layer 1 regression (the LP collapse invariant) runs on every execution. Layer 2 prints
  `SKIPPED` until `CALIBRATED` is set.
- Gurobi 13.0.2.

# Training plan

**Demonstration prototype. All data is synthetic.** The company and its people are invented. The roles
are the ones a fabricator of this size typically has, and the plan is written as it would be for one.

This plan sets out, role by role, what changes, what people need to learn, how they will be taught, how
long it takes and how competence is checked. It follows the phases in `docs/rollout-plan.md`. It covers
the six roles the change touches most, plus goods-in and stores and the quality team, because EN 1090
traceability depends on them. The Roadmap page of the app shows the same plan from
`config/roadmap.yaml`, and a test keeps the two in step.

## Principles

1. **Just in time.** Nobody is trained more than two weeks before they use what they learned. Training
   given months ahead is forgotten by go-live.
2. **Where the work is done.** Operators learn at the bay terminal and goods-in at the goods-in bench.
   Finance learns on a real month-end. Classrooms are kept for what cannot be learned at the workplace.
3. **Supervisors and floor champions first.** They are trained before their teams and help teach them,
   so help on the floor comes from someone the operators already know.
4. **Competence is checked, not attendance.** A signed register proves someone was in the room. Each
   role below has a check that proves they can do the job: an observed task, a supervised month-end, or
   the data itself.
5. **Checks are for coaching, not discipline.** Where a check looks at one person's records, it is
   limited to the training period, covered by the data protection impact assessment, and used only to
   decide who needs more help. This is part of the answer to risk R01 in `docs/risk-register.md`.
6. **Everyone can use it.** Quick-reference cards at every terminal are mostly pictures. They are
   translated where an operator's first language is not English, and nobody needs to read long text.
   Night shift is trained on night shift, and agency staff are trained before their first booking.

## Summary

| Role | Method | Duration per person | Competence check | When |
| --- | --- | --- | --- | --- |
| Shop-floor operators | Toolbox talk and hands-on at the bay terminal, then two weeks of floor-champion support | 45 minutes; 75 minutes for saw and stores operatives | Floor champion observes a booking, a correction and the paper fallback; first two weeks of bookings reviewed for coaching | Two weeks before their site goes live (months 11 and 13) |
| Site supervisors | Workshop off the floor, practical on the floor, first week shadowed; scorecard session in Phase 3 | 5 hours 30 minutes | Practical scenario on the test system; the site's shop-floor rules at threshold for four weeks after go-live | Month 7; two weeks before their site goes live |
| Purchasing | Desk sessions, then paired review of real queue items | 4 hours | First 20 review decisions checked by the Purchasing Manager; new orders pass the grade and code rules | Months 3 and 10 |
| Finance | Desk sessions, then supervised parallel month-ends | 4 hours 30 minutes, plus three supervised month-ends | Three parallel month-ends signed by the Finance Manager | Months 3, 8 and 13 |
| Project managers | Desk session, then a review of one of their own live jobs | 2 hours 30 minutes | Explains a margin movement on their own job from the drill-down; promised dates on every delivery | Months 8 and 10 |
| Senior management | Two workshops | 3 hours | At review 3, each member presents one KPI with its caveat and the decision it supports | Months 3 and 9 |
| Goods-in and stores | Toolbox talk, certificate reading at the bench, witnessed receipts; issue recording before go-live | 2 hours 45 minutes | First 10 receipts witnessed by the QA inspector; heat number, certificate and grade on every new receipt | Month 2; two weeks before their site goes live |
| Quality team | Desk session, then a mock traceability audit | 4 hours | Traces one assembly on a live EXC3 job to its mill certificate within 30 minutes, unaided | Months 2 and 10 |

## Shop-floor operators

**What changes for them.** Hours are booked on a terminal at the end of the bay instead of on a paper
sheet. The works order and operation are picked from a list of the live works orders for that bay, so no
number is typed. Each booking names the operator, which also becomes the record of which qualified
welder made which weld. Saw and stores operatives record which bar each cut came from, transfer the heat
number to cut pieces and offcuts, and return offcuts to stock with their heat number.

**What they need to learn.**

- Logging in, finding their works order and operation, entering hours, and correcting a mistake.
- What to do when the terminal is down: the paper fallback sheet, keyed by the supervisor the next day.
- Why it matters to them. Their hours are what the job is costed on. Rework hours are now visible, so
  estimates improve and they are not blamed for a job that was under-priced. And the booking data is not
  used to judge individuals: the Managing Director's written commitment is read out.
- For saw and stores operatives: reading the heat number on a bar, marking it on cut pieces and offcuts,
  and recording the issue against the cutting list.

**Delivery method.** A 30-minute toolbox talk at the start of a shift, then 15 minutes hands-on at the
bay terminal in pairs, with a floor champion. Saw and stores operatives get a further 30 minutes at the
saw. For two weeks after go-live a floor champion is on every shift to help.

**Duration.** 45 minutes per person; 75 minutes for saw and stores operatives.

**How competence is checked.** The floor champion watches each operator make a booking, correct one, and
explain the paper fallback, then signs the operator's checklist. For the first two weeks the supervisor
reviews each operator's bookings for a valid works order, an operation and sensible hours, to coach
anyone who is struggling. After two weeks the individual review stops and only site-level figures are
reported. The site is on track when at least 95% of its hours are booked within 24 hours against a live
works order by the end of week two.

**When.** In the two weeks before their site goes live: the pilot site in month 11, the second site in
month 13.

## Site supervisors

**What changes for them.** The four weekly spreadsheets (bookings, delivery notes, NCRs and capacity)
are retired. Supervisors check their team's bookings on the form each day, raise NCRs on the form with a
cost estimate, and complete delivery notes that cannot be saved without a works order, tonnage and the
contract promise date. They close works orders when the work is despatched. They work their own
exception queue, and each week they see their site's data quality score.

**What they need to learn.**

- Every form, including booking on an operator's behalf and approving the day's bookings.
- The paper fallback and keying it the next day.
- Their exception queue: what each exception means and how to correct it at source.
- Reading their site's weekly scorecard, and the escalation route in `docs/data-ownership.md`.
- How to coach an operator through the form, since they lead the floor champions.

**Delivery method.** A half-day workshop off the floor using the test system, one hour of practical
work at their own bays, and the first week after go-live shadowed by the programme team. In Phase 3 a
one-hour session introduces the site scorecard, and supervisors help test the forms with their
operators.

**Duration.** 5 hours 30 minutes: a 3 hour 30 minute workshop, 1 hour on the floor and a 1 hour scorecard
session, plus the shadowed week.

**How competence is checked.** Each supervisor completes a scenario on the test system, assessed by the
programme manager. The scenario covers a booking for an absent operator, a correction, an NCR with a cost,
a delivery note and five exceptions to clear. After go-live, the site's shop-floor rules (DQ-23, DQ-27,
DQ-28, DQ-29 and DQ-30) must be at threshold for four consecutive weeks.

**When.** The scorecard session in month 7. The forms workshop two weeks before their site goes live, so
in month 10 for the pilot site and month 12 for the second site.

## Purchasing

**What changes for them.** Buyers order only by approved material codes that include the grade. A new
code is requested from the master data service and approved by the Purchasing Manager before it is used.
Suppliers are picked from the golden list, never typed. From month 10, every subcontract and service is
bought on a purchase order: galvanising, paint, erection, profiling, plant hire, transport and
inspection. Every steel order states that a 3.1 mill certificate is required. Buyers work the review
queue for materials and suppliers, and the quantity and price exceptions on their own orders.

**What they need to learn.**

- The material code structure: section type, designation and grade, for example
  UB406X178X60-S355J2, and why grade can never be left off or guessed.
- How to request a new code, and how to decide a review queue item from its evidence.
- Raising orders for services and agreeing a price before the work is done.
- Their exception queue: short deliveries, overcharges and orders never received.

**Delivery method.** Two one-hour desk sessions, then the review queue itself becomes the training. A
buyer's first 20 decisions are made alongside the Purchasing Manager.

**Duration.** 4 hours: two 1-hour sessions and about 2 hours of paired decisions.

**How competence is checked.** The Purchasing Manager checks the buyer's first 20 review decisions. The
buyer works alone once 19 of the 20 agree. After that, new orders must meet rules DQ-03 (grade stated)
and DQ-04 (canonical code) at their thresholds. From month 10 there should be no invoice without a
purchase order in the buyer's spend categories.

**When.** Month 3, before the cleanse starts. Month 10, before the purchase order rule for services.

## Finance

**What changes for them.** Supplier accounts are created only through the master data service. Bank
detail changes need two signatures and a telephone check. Job codes come only from the crosswalk. The
three-way match exception queue replaces the check by eye. Month-end uses the warehouse KPI pack and the
job cost reconciliation, with weekly figures split to finance periods by the agreed calendar rule. From
month 14, steel is charged to jobs from recorded issues, not from the invoice.

**What they need to learn.**

- The supplier merge procedure, and why payment runs freeze on accounts being merged.
- Working the three-way match exception queue: chasing, accruing, holding and crediting.
- The job cost reconciliation drill-down, from a job's gap to the rows behind it.
- The calendar rule and the new month-end timetable.
- Charging steel from issues, and explaining the movement in job margins when that starts.

**Delivery method.** A 2-hour desk session on the queues and the merge procedure. A 1 hour 30 minute
session on month-end and the calendar rule. A 1-hour session on charging steel from issues. The three
parallel month-ends in Phase 3 are the practice, supervised by the Finance Manager.

**Duration.** 4 hours 30 minutes of sessions, plus three supervised month-ends.

**How competence is checked.** In each parallel month-end, the ledger clerks clear the exception queue.
The management accountant reconciles warehouse labour and material to the ledger within the agreed
tolerance, and the Finance Manager signs off each month-end. The old process is switched off only after
three consecutive signed month-ends.

**When.** Month 3 for the queues and merges. Month 8 for month-end, at the first parallel run. Month 13
for charging steel from issues.

## Project managers

**What changes for them.** Job margins come from the warehouse. Once steel is charged from issues,
margins on some live jobs will move, because material is no longer charged to whichever job the invoice
named. OTIF will be measured against the promise date in the contract, which the project manager enters
in the delivery schedule. Each job's NCR costs are visible. The traceability report for a job becomes
part of its handover file.

**What they need to learn.**

- Reading the KPI pack and the job cost reconciliation for their own jobs, including the caveats.
- Entering and revising contract promise dates.
- Requesting a job's traceability report for the customer's handover file.
- When and how to raise a disputed figure through the escalation route.

**Delivery method.** A 90-minute desk session, then an hour with the management accountant going
through one of their own live jobs.

**Duration.** 2 hours 30 minutes.

**How competence is checked.** At the first monthly job review after training, each project manager
explains the margin movement on one of their own jobs using the drill-down. After the delivery note form
goes live, every delivery on their jobs carries a contract promise date (rule DQ-29 at 100% for their
jobs).

**When.** Month 8 for the pack and job costs. Month 10 for promise dates, before the first site goes
live.

## Senior management

**What changes for them.** The monthly pack comes from the warehouse, not from spreadsheets. Every figure
carries its caveat and can be traced to the rows behind it. Decisions on data disputes that reach
step 3 or 4 of the escalation route come to them. They also carry a commitment the shop floor will test:
booking data is not used to judge individuals.

**What they need to learn.**

- Reading the KPI pack and the data quality index, and what each caveat means for a decision.
- Asking "show me the rows" and following a figure to its source.
- Their role at the quarterly reviews: approving phase exits against criteria, not dates.
- Why some figures will look worse before they look better, as set out in `docs/benefits-case.md`.

**Delivery method.** Two 90-minute workshops. The first uses the baseline pack and the second uses the
first pack built from the warehouse.

**Duration.** 3 hours.

**How competence is checked.** At review 3, each member of the management committee presents one KPI
from the pack with its caveat and the decision it supports. The pack is accepted only when the minutes
record that the caveats were discussed.

**When.** Month 3, alongside review 1. Month 9, alongside review 3.

## Goods-in and stores

**What changes for them.** From month 2, no steel is booked into stock without a heat number and a 3.1
mill certificate. Untraceable steel is red-tagged into a quarantine bay and the Quality Manager is told.
From go-live, the goods received note is completed on a form that needs heat number, certificate
reference and grade, with the certificate scanned and attached. Stores record material issues against
the cutting list, return offcuts with their heat number, and count stock to a cycle-count schedule.

**What they need to learn.**

- Reading a 3.1 mill certificate: heat number, grade, dimensions, and checking them against the steel and
  the delivery ticket.
- The quarantine procedure for steel that cannot be traced.
- Recording issues and offcut returns, and the cycle-count routine.

**Delivery method.** A 45-minute toolbox talk and an hour at the goods-in bench with the QA inspector
using real certificates. The QA inspector then witnesses each person's first 10 receipts. Before go-live,
a further hour covers the goods-in and issue forms.

**Duration.** 2 hours 45 minutes, plus the witnessed receipts.

**How competence is checked.** The QA inspector signs off each person after 10 witnessed receipts. From
then on, every new receipt must pass rules DQ-01, DQ-02 and DQ-03 (heat number, certificate and grade),
checked daily. Each week the QA inspector traces five issues from assembly back to certificate.

**When.** Month 2 for certificates and quarantine. The two weeks before each site goes live for the forms.

## Quality team

**What changes for them.** The traceability reconciliation shows every broken chain, and the Quality
Manager decides what happens to each. The factory production control procedures are rewritten for the
new records. NCRs arrive on a form with a cost, and are reminded after seven days if the cost is pending.
Before each cutover, the Quality Manager runs the traceability gate.

**What they need to learn.**

- Reading the traceability reconstruction and its exposure by job, customer and execution class.
- Deciding on a traceability gap, and when to involve the certification body or the customer.
- The NCR form and costing, and the traceability gate checklist.

**Delivery method.** A 2-hour desk session, then a 2-hour mock traceability audit on a live job.

**Duration.** 4 hours.

**How competence is checked.** In the mock audit, each member of the team traces one assembly on a live
EXC3 job from its delivery note, through its issue and receipt, to the mill certificate. They must do it
within 30 minutes without help.

**When.** Month 2 for traceability decisions. Month 10 for the procedures, the NCR form and the gate.

## Schedule

| Month | Training | Phase |
| --- | --- | --- |
| 2 | Goods-in and stores: certificates and quarantine. Quality team: traceability decisions | 1 |
| 3 | Senior management workshop 1. Purchasing: codes and review queue. Finance: queues and supplier merges | 1 and 2 |
| 7 | Site supervisors: scorecard session and form testing | 3 |
| 8 | Finance: month-end on the warehouse. Project managers: pack and job costs | 3 |
| 9 | Senior management workshop 2 | 3 |
| 10 | Purchasing: orders for services. Project managers: promise dates. Quality team: procedures and gate. Pilot site supervisors, floor champions, goods-in and stores | 4 |
| 11 | Pilot site operators | 4 |
| 12 | Second site supervisors, floor champions, goods-in and stores | 4 |
| 13 | Second site operators. Finance: charging steel from issues | 4 |
| 14 to 18 | Refreshers and new-starter induction handed to the business | 5 |

## New starters, agency staff and refreshers

- Operators and agency staff complete the operator training and the observed booking before their first
  shift on the new process. The floor champion keeps the checklist.
- Buyers, ledger clerks and stewards new to a role do the training for that role, and have their first 20
  decisions or their first month-end checked.
- Everyone gets a short refresher before each certification body surveillance visit, covering whatever
  the internal traceability audit found.
- In Phase 5 the training material, checklists and assessment scenarios pass to the owning managers.
  Keeping them current becomes part of each data owner's job.

## Training records

Each person's training, and the result of their competence check, is recorded against their name. The
records are kept with the factory production control records, because EN 1090 expects evidence that the
people whose work affects conformity are competent to do it. The programme manager keeps the records
until Phase 5, then hands them to the Quality Manager.

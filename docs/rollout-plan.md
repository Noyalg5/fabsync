# Rollout plan

**Demonstration prototype. All data is synthetic.** The company, its people and every figure quoted
here are invented for the FabSync demonstrator. The plan is written as it would be for a real
fabricator of this size, and every measured figure it quotes comes from the prototype's synthetic
data.

This plan takes FabSync from a demonstrator to the way the business runs. It covers 18 months in five
phases, with a management committee review at the end of every quarter. It goes with
`docs/risk-register.md`, `docs/training-plan.md` and `docs/benefits-case.md`, and it builds on the
design in `docs/integration-design.md` and `docs/data-ownership.md`. The Roadmap page of the app shows
the same phases, risks and training from `config/roadmap.yaml`, and a test keeps the two in step.

## The plan on one page

| Phase | Months | What it delivers |
| --- | --- | --- |
| 1. Discovery and baseline | 1 to 3 | The real state of the data, frozen as the baseline. Traceability contained at goods-in. Corvus knowledge written down. |
| 2. Master data cleanse | 3 to 8 | One supplier, one material code, one unit and one job number everywhere. The historic backlog cleared. |
| 3. Read-only integration and reporting | 5 to 10 | Nightly collection into the warehouse, with nothing written back. The monthly KPI pack, scorecards and exception queues replace hand-built reports. |
| 4. Process change and write-back | 9 to 15 | Shop-floor forms replace the spreadsheets. Material issues are recorded, every service is bought on a purchase order, and approved master data flows back to Corvus and finance. |
| 5. Embed and handover | 14 to 18 | The new way is business as usual, benefits are measured against the baseline, support is handed over and the programme closes. |

The order matters. Nothing is written back to Corvus or finance until the data has been cleaned
(Phase 2) and the read-only integration has run reliably for a month (Phase 3). The shop floor changes
last, when there is clean data for its pick lists and a working warehouse to receive what it records.

## Terms used

- A **phase** is a block of work with one objective. It starts only when its **entry criteria** are met
  and ends only when its **exit criteria** are met. Both are written as checks someone can make, not as
  intentions.
- The **management committee** is the Managing Director (chair), the programme sponsor and the four
  data owners. It meets at the end of each quarter to approve phase exits, release the next tranche of
  funding and decide what to do about the top risks.
- **Dual running** (or parallel running) is doing a job the old way and the new way at the same time,
  to prove the new way before the old one is switched off. It is expensive and tiring, so every parallel
  run in this plan has a fixed end date.
- **Write-back** is the integration sending approved changes, such as a merged supplier or a retired
  material code, back into Corvus or the finance system. Read-only integration only collects.
- A **cutover** is the day a site or a process stops using the old way.
- **Hypercare** is the two weeks after a cutover, when the programme team checks the new process every
  day and fixes problems the same day.
- The **baseline** is the set of measures taken before anything changes. Every benefit is measured
  against it. See `docs/benefits-case.md`.
- **Factory production control (FPC)** is the documented system of checks that EN 1090 certification
  rests on. Traceability from mill certificate to finished assembly is part of it.

Months are counted from mobilisation: month 1 is the month the sponsor is appointed. Calendar dates are
fixed at the first management committee review, once the financial year end, the year-end stocktake,
the works shutdowns and the certification body's surveillance visit are known.

## Timeline

■ marks the months a phase is active. ◆ marks a management committee review. ▒ marks dual running.

| | M1 | M2 | M3 | M4 | M5 | M6 | M7 | M8 | M9 | M10 | M11 | M12 | M13 | M14 | M15 | M16 | M17 | M18 |
| --- | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| Quarter | Q1 | | | Q2 | | | Q3 | | | Q4 | | | Q5 | | | Q6 | | |
| 1. Discovery and baseline | ■ | ■ | ■ | | | | | | | | | | | | | | | |
| 2. Master data cleanse | | | ■ | ■ | ■ | ■ | ■ | ■ | | | | | | | | | | |
| 3. Read-only integration and reporting | | | | | ■ | ■ | ■ | ■ | ■ | ■ | | | | | | | | |
| 4. Process change and write-back | | | | | | | | | ■ | ■ | ■ | ■ | ■ | ■ | ■ | | | |
| 5. Embed and handover | | | | | | | | | | | | | | ■ | ■ | ■ | ■ | ■ |
| Dual running: reports and KPI pack | | | | | | | | ▒ | ▒ | ▒ | | | | | | | | |
| Dual running: forms, pilot site | | | | | | | | | | | ▒ | | | | | | | |
| Dual running: forms, second site | | | | | | | | | | | | | ▒ | | | | | |
| Management committee review | | | ◆ | | | ◆ | | | ◆ | | | ◆ | | | ◆ | | | ◆ |

Phases overlap where the dependency between them is partial. Each phase's entry criteria say exactly
what must be finished before it starts.

### Milestones

| Month | Milestone |
| --- | --- |
| 1 | Sponsor, programme manager, data owners and stewards named; programme charter approved |
| 2 | Goods-in refuses steel without heat number and mill certificate at both sites; the prototype pipeline runs on real extracts |
| 3 | Baseline frozen and signed; Corvus runbook proven by the backup user; review 1 approves the re-baselined plan |
| 6 | First nightly loads running; review 2 |
| 8 | Master data cleanse complete; first parallel month-end on the warehouse |
| 9 | Review 3 approves the Phase 4 build and chooses the pilot site |
| 10 | Third parallel month-end; old reports switched off; no purchase order, no payment |
| 11 | Pilot site goes live on the shop-floor forms |
| 12 | Review 4 decides whether the second site goes live |
| 13 | Second site goes live |
| 14 | Steel charged to jobs from recorded issues; write-back automated |
| 15 | Both sites on the new process; review 5 approves Phase 4 exit |
| 18 | Benefits review signed; programme closed at review 6 |

## Management committee reviews

Each review looks at evidence prepared in advance and makes the decisions listed. A phase whose exit
falls between reviews (Phase 2 in month 8, Phase 3 in month 10) is approved by the sponsor against its
exit criteria and ratified at the next review.

| Review | Month | Decisions | Evidence in front of the committee |
| --- | --- | --- | --- |
| 1 | 3 | Accept the baseline; approve Phase 1 exit; approve the re-baselined plan and budget; release Phase 2 and Phase 3 funding | Signed baseline pack; profiling of the real extracts against the demonstrator; the cleanse sized from real queues; vendor confirmations; data protection impact assessment; goods-in control results |
| 2 | 6 | Confirm the cleanse is on track or add resource; approve the parallel reporting run | Cleanse burn-down against plan; first nightly load log; certificate recovery status; top risks |
| 3 | 9 | Ratify Phase 2 exit; approve the Phase 4 build; choose the pilot site | Master data rules at threshold; first parallel month-end; forms usability results; first benefits reading on stock accuracy, aged exceptions and WIP ageing |
| 4 | 12 | Go or no-go for the second site | Pilot site exit measures; dual-running hours; traceability on new work; benefits reading |
| 5 | 15 | Approve Phase 4 exit; start the handover; agree the scope of the benefits review | Phase 4 exit measures at both sites; write-back reconciliation; benefits reading |
| 6 | 18 | Accept the benefits review; close the programme; decide on replacing Corvus | Benefits review against the baseline; handover acceptance; remaining risks; the Corvus options paper |

At every review the committee also sees the programme's spend against plan, the very high and high
risks from `docs/risk-register.md`, and the order book against shop capacity for the next quarter, so
programme work is not planned into a contract peak.

## Roles

| Role | Who | Part in the programme |
| --- | --- | --- |
| Programme sponsor | A director, named in month 1 | Owns the business case; chairs the data governance group; approves phase exits between reviews; holds the contingency |
| Management committee | Managing Director (chair), sponsor, four data owners | Quarterly reviews; approves funding and phase exits |
| Programme manager | Full time for 18 months, seconded or contracted | Runs the plan, the risk register and benefits tracking; reports to the sponsor weekly |
| Integration lead | Contracted data engineer, full time months 2 to 15, part time after | Builds and runs the nightly loads, forms and write-back, starting from the prototype's code |
| Data owners | Purchasing Manager, Production Controller, Finance Manager, Quality Manager | Answer for their data, as set out in `docs/data-ownership.md`; sign off their KPIs and their phase exit criteria |
| Data stewards | Buyer, purchase and sales ledger clerks, management accountant, production planner, stores and goods-in supervisors, site supervisors, QA inspector | Work the review and exception queues; correct records at source |
| Corvus key user | The one person who knows Corvus's reports, extracts and codes | Knowledge capture in Phase 1; code blocks and extract jobs in Phases 2 and 3; half their day job backfilled |
| Corvus backup user | Named in month 1 | Learns and performs every task in the Corvus runbook |
| Floor champions | One operative per site per shift | Trained first; first line of help on the floor after cutover |
| Employee representatives | Elected or recognised representatives at each site | Consulted on the booking changes and on the data protection impact assessment |
| Corvus vendor and finance system supplier | External | Confirm extract and import rights; make configuration changes |
| IT support provider | External | Server, backup, network, Wi-Fi and terminals |
| Certification body | External | Briefed on changes to factory production control; consulted on traceability gaps |
| External auditor | External | Briefed on the finance cutover timetable |

## Phase 1. Discovery and baseline

**Objective.** Find out from the real systems how bad things are, and freeze that as the baseline every
benefit is measured against. Contain the EN 1090 exposure at goods-in before anything else changes, and
get the Corvus knowledge out of one person's head.

**Duration.** Months 1 to 3.

**Activities**

- Name the sponsor, programme manager, data owners and stewards. Fix the six management committee dates.
- Take real extracts from Corvus, the finance system and both sites' spreadsheets, and run the FabSync
  pipeline on them unchanged: ingest, profile, match, quality rules, reconcile, KPIs. Record every way the
  real data differs from the demonstrator, and add a contract or rule for each.
- Freeze the baseline: the nine KPIs, the data quality index, the size of every queue and the
  reconciliation exposures. Record each with its caveat and its monthly range over the last 12 months.
  The Finance Manager signs it, and it is stored as a snapshot that is never overwritten.
- Size the cleanse from the real queues. Stewards clear a timed sample of 50 items per domain, so
  minutes per item are measured rather than assumed. Time how long the current month-end reports and
  re-keying take, for the benefits case. Sample 50 late deliveries and 50 short deliveries to find out
  why they happened.
- Contain EN 1090 exposure by procedure, with no system change. Goods-in books no steel into stock
  without a heat number and a 3.1 mill certificate, and red-tags anything untraceable into a quarantine
  bay. The buyers request duplicate certificates for receipts that lack them (178 in the prototype). The
  Quality Manager assesses each exposed job by execution class, and briefs the certification body on the
  programme and on the planned changes to factory production control.
- Capture the Corvus knowledge. Record walkthroughs of every extract, report, batch routine, code
  convention and month-end task the key user performs; write the runbook; the backup user performs each
  task unaided while observed.
- Get written answers from the Corvus vendor and the finance system supplier: extract rights and cost,
  whether Corvus can accept import files, post material issues and make fields mandatory. Test each on a
  copy of Corvus.
- Agree the calendar rule: every day mapped to a production week (Monday start) and a finance period,
  and how weekly figures are split at a month end.
- Complete a data protection impact assessment for bookings and forms that name operators. Agree with
  employee representatives, in writing, what booking data will and will not be used for.
- Walk both sites with the supervisors and sit with operators at booking time, to find out why
  bookings are late, incomplete or wrong. The findings shape the form design in Phase 3.
- Survey Wi-Fi and terminal positions in every bay.
- Re-baseline this plan from the real sizing, for review 1.

**Entry criteria**

- The management committee has approved the programme charter and the Phase 1 budget.
- Sponsor and programme manager appointed.
- Each system's owner has agreed to production extracts being taken; the Corvus key user is released
  two days a week, with half their day job backfilled.

**Exit criteria**

- Baseline pack signed by the four data owners and the Finance Manager, and stored as a read-only
  snapshot.
- Real extracts profiled; every difference from the demonstrator documented with the rule or contract
  change that handles it.
- Cleanse sized in hours from the real queues and measured minutes per item, with a named steward and
  weekly hours for each domain.
- Goods-in control live at both sites for at least four weeks, with no receipt booked without heat
  number and certificate, checked by the Quality Manager against the goods received log.
- Duplicate certificates requested for every untraceable receipt; certification body briefed.
- Every task in the Corvus runbook performed by the backup user unaided.
- Vendor answers received in writing, or the fallback agreed.
- Data protection impact assessment approved; calendar rule signed by the Finance Manager and the
  Production Controller.
- Re-baselined plan and budget approved at review 1.

**Dependencies.** The Corvus vendor's response time. The key user's availability. Mills and
stockholders answering certificate requests, which carries on into Phase 2.

**Roles involved.** Programme sponsor, programme manager, the four data owners, Corvus key user and
backup user, integration lead (from month 2), goods-in supervisor, buyers, employee representatives,
Corvus vendor, finance system supplier, certification body.

## Phase 2. Master data cleanse

**Objective.** One supplier, one material code, one unit of measure and one job number in every system,
and the historic backlog of exceptions cleared. Phase 3 then carries clean records, and Phase 4 has
clean works orders and codes for its pick lists.

**Duration.** Months 3 to 8.

**Activities**

- Work the match review queue domain by domain, highest risk first. Materials without a grade come first,
  because each needs its mill certificate checked. Suppliers, works orders and jobs follow. Every
  decision is recorded with its evidence.
- Suppliers: reconcile statements, freeze payment runs on accounts being merged, merge duplicates in
  finance and map every Corvus code to one account, then block the old codes. Confirm the bank details
  on each surviving account by telephone to a number already on file.
- Set up subcontract and service suppliers as golden records with Corvus ordering codes. That covers
  galvanisers, painters, erectors, plant hire and hauliers, and means purchase orders can be raised for
  them in Phase 4.
- Materials: retire code variants and block them in Corvus; set one stocking unit per material. The
  approved changes go to Corvus and finance as change lists keyed by the steward. Automated write-back
  waits for Phase 4.
- Jobs: complete the crosswalk; map or close every finance job code with no Corvus job (20 in the
  prototype).
- Traceability: keep chasing duplicate certificates. The Quality Manager decides on every remaining gap
  (accept on evidence, test, or notify the customer), with the certification body where needed.
- Clear three-way match exceptions older than 90 days (1,076 lines in the prototype) by chasing,
  accruing, obtaining credit notes or writing off with the Finance Manager's approval.
- Recount every stock line not counted in the last 90 days and post agreed adjustments.
- Close works orders whose work has gone, so WIP shows only work still in the shop.
- Publish the golden records. Report each queue's burn-down weekly to the sponsor and monthly to the data
  governance group.

**Entry criteria**

- Phase 1 exit approved at review 1.
- Stewards named, with weekly hours ring-fenced from the Phase 1 sizing and written into their
  objectives.
- Stewards trained (see `docs/training-plan.md`: purchasing and finance).
- Supplier merge procedure approved by the Finance Manager.

**Exit criteria**

- Match review queue empty, or every open item accepted by its owner with a recorded reason.
- Master data rules DQ-04, DQ-05, DQ-07, DQ-08, DQ-09 and DQ-10 at threshold for four consecutive
  weekly runs.
- Every live job in the crosswalk, and no finance job code outside it.
- Every untraceable receipt either traced or given a recorded decision by the Quality Manager.
- No three-way exception older than 90 days without an owner's decision.
- Every stock line counted within the last 90 days.

**Dependencies.** Phase 1 sizing and stewards' time. The Corvus key user to block codes. The finance
system allowing accounts to be merged or closed. Mills and stockholders for certificates.

**Roles involved.** The four data owners and their stewards, Corvus key user and backup user, programme
manager, certification body and customers (for traceability decisions), temporary cleanse support if
the burn-down falls behind.

## Phase 3. Read-only integration and reporting

**Objective.** Collect data from Corvus and finance automatically every night into the warehouse,
without writing anything back, and replace the hand-built management reports with the KPI pack,
scorecards and exception queues. Read-only comes first, so a mistake in the integration can never
damage a working system.

**Duration.** Months 5 to 10.

**Activities**

- Build the nightly extracts IF-01 to IF-08 and the loads IF-16 to IF-18 from `docs/integration-design.md`,
  starting from the prototype's ingestion, matching, quality, reconciliation and KPI code. Run them on a
  company server inside the existing backup and patching, using read-only accounts with the least access
  needed.
- Monitor the loads: the run log is checked each morning, a failed load alerts its owner, and every report
  shows its "as at" date. The shop-floor spreadsheets keep loading as they are, because nothing changes on
  the floor yet.
- Build the calendar rule agreed in Phase 1 into the warehouse as a date table.
- Issue the monthly KPI pack and data quality scorecard from the warehouse, every figure with its caveat
  and signed by its owner. Deliver exception and review queues to each owner daily, with the escalation
  route in `docs/data-ownership.md` live.
- Run three month-ends in parallel (months 8, 9 and 10): the pack and the existing management reports
  side by side, every difference explained. The old reports are named at the start of the parallel run,
  and switched off at its end.
- Design the shop-floor forms with supervisors and operators, and usability-test them at both sites.

**Entry criteria**

- Phase 1 exit: vendor rights confirmed, data protection impact assessment approved, calendar rule
  agreed.
- Server provisioned by the IT support provider.
- Interface specifications signed by each interface owner.
- Phase 2 under way. Golden records are not a precondition, because the matching stage handles messy
  data, as the prototype shows.

**Exit criteria**

- 30 consecutive nightly loads with no unplanned failure, and any failure recovered by the next morning.
- Fewer than 0.1% of rows quarantined.
- KPI pack issued from the warehouse for three consecutive month-ends, reconciled to the management
  accounts within the tolerance the Finance Manager sets, and signed by the owners.
- Every old report on the parallel-run list switched off.
- Form designs signed by the supervisors at both sites after usability testing.

**Dependencies.** Phase 1 vendor answers, data protection impact assessment and calendar rule. The
server. Phase 2 progress on suppliers and materials, so the pack is readable.

**Roles involved.** Integration lead, Finance Manager (owner of the warehouse load), the other data
owners, management accountant, Corvus key user and backup user, finance system supplier, IT support
provider, site supervisors and operators (form design), programme manager.

## Phase 4. Process change and write-back

**Objective.** Change how data is created, so the drift cannot come back. Shop-floor forms replace the
spreadsheets, and material issues are recorded. Heat number, certificate and grade become compulsory,
every service is bought on a purchase order, and steel is charged to jobs from what was issued. Approved
master data flows back to Corvus and finance automatically.

**Duration.** Months 9 to 15.

**Activities**

- Build the forms for time bookings, delivery notes, non-conformance reports and weekly capacity
  (IF-09 to IF-12), with pick lists fed from the master data service (IF-15). The delivery note form
  captures the promised date from the contract, not the internal planned finish.
- Record material issues from the cutting lists, with the heat number transferred to cut pieces and to
  offcuts returned to stock. Make heat number, certificate and grade mandatory in Corvus. If Corvus cannot
  enforce them, the form checks them and the integration quarantines any gap the next morning.
- Update the factory production control procedures for the new records and notify the certification
  body. The Quality Manager's traceability gate must pass before each cutover.
- From month 10, no purchase order, no payment, for all spend except exempt overhead nominals. This uses
  the service supplier records set up in Phase 2.
- Pilot site go-live in month 11: four weeks of dual running with paper and form, then a hard switch-off,
  with the spreadsheets locked read-only. Two weeks of hypercare.
- Review 4 in month 12 decides on the second site against the pilot's exit measures.
- Second site go-live in month 13, with the pilot's lessons applied.
- From month 14, the first full month both sites record issues, finance charges steel to jobs from the
  recorded issues, not from the invoice.
- Write-back: approved codes to Corvus (IF-13), and supplier accounts and the job crosswalk to finance
  (IF-14), move from steward-keyed change lists to import files. This happens after a dry run on a copy.
  Bank details never travel this way.

**Entry criteria**

- Phase 2 exit: clean works orders and codes for the pick lists, and golden records to write back.
- Nightly loads stable for 30 nights. The full Phase 3 exit follows in month 10.
- Forms signed by supervisors after usability testing; training materials ready; floor champions trained.
- Employee representatives consulted; the data protection impact assessment covers the forms.
- Factory production control procedures updated and the Quality Manager's traceability gate passed.
- Cutover dates clear of the financial year end, the year-end stocktake, works shutdowns and the
  certification body's surveillance visit.
- Terminals and Wi-Fi installed and tested in every bay at the go-live site.

**Exit criteria**

- All four shop-floor spreadsheets retired at both sites and archived read-only.
- At each site, for eight consecutive weeks: at least 98% of hours booked on the form within 24 hours
  against a live works order; rules DQ-23, DQ-27, DQ-28, DQ-29 and DQ-30 at threshold.
- Material issues recorded for at least 95% of steel by weight on works orders started after go-live,
  and traceability coverage of at least 99% on that work.
- No invoice without a purchase order outside exempt nominals for two consecutive months.
- Write-back running for a month with no unreconciled difference between the master data service, Corvus
  and finance.

**Dependencies.** Phases 2 and 3. The Corvus vendor for mandatory fields, issue transactions and imports.
Terminals and Wi-Fi. Training delivered no more than two weeks before each go-live.

**Roles involved.** Production Controller (leading owner), site supervisors, floor champions, operators,
stores and goods-in, buyers, Finance Manager and management accountant, Quality Manager and QA inspector,
integration lead, Corvus key user and vendor, employee representatives, certification body, programme
manager.

## Phase 5. Embed and handover

**Objective.** Make the new way business as usual, owned by the business rather than by the programme.
Prove the benefits against the Phase 1 baseline, hand over support and close the programme.

**Duration.** Months 14 to 18.

**Activities**

- Make the monthly review of each owner's scorecard and exception queue the standing agenda of the data
  governance group. Review rules and thresholds quarterly.
- Measure every benefit against the Phase 1 baseline, restating the baseline wherever a definition
  changed, and write the benefits review for review 6.
- Hand over: runbooks for every interface and form, two trained people for each, and support
  arrangements with the IT support provider. The integration lead transfers knowledge to the internal
  support owner.
- Audit traceability internally on a sample of jobs ahead of the certification body's next
  surveillance visit.
- Put refresher training and new-starter induction in place.
- Record lessons learned, and write the options paper on replacing Corvus, using the clean data and the
  requirements this programme has uncovered.

**Entry criteria**

- Phase 4 exit measures met at the pilot site. The second site can finish Phase 4 in parallel.
- Support model agreed by the sponsor.
- Internal support owner named, with time set aside to take the handover.

**Exit criteria**

- The data quality index at or above its target for three consecutive months, with the queues cleared
  by the owners' own stewards and no programme staff.
- Benefits review signed by the Finance Manager, with each benefit shown against its baseline and the
  query that produces it.
- Runbooks accepted by the support owner; two trained people for every interface and form.
- Every open risk closed or moved to the company risk register with an owner.
- Programme closed at review 6.

**Dependencies.** Phase 4 exit at both sites (month 15). The support owner's time.

**Roles involved.** Programme sponsor, management committee, data owners and stewards, programme
manager (until close), integration lead (handover), internal support owner, IT support provider, Finance
Manager (benefits review), Quality Manager (audit).

## Programme controls

- **Weekly:** the programme manager reviews progress, queue burn-down, dual-running hours and risk
  triggers with the sponsor.
- **Monthly:** the data governance group reviews scorecards, queues and escalations, as set out in
  `docs/data-ownership.md`.
- **Quarterly:** the management committee review.
- **Tolerances:** the programme manager may move work within a phase by up to four weeks. The sponsor
  may move a phase exit by up to a quarter. Anything larger, or any change to an exit criterion, goes to
  the management committee. Exit criteria are never relaxed to make a date. A phase that cannot meet
  them is paused at its gate.

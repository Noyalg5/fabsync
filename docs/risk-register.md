# Risk register

**Demonstration prototype. All data is synthetic.** The company, its people and every figure quoted
here are invented for the FabSync demonstrator. Where a risk quotes a figure, it was measured by the
prototype on synthetic data. It shows the kind of evidence a real register should carry, not the size
of any real company's problem.

This register goes with `docs/rollout-plan.md`. It holds 23 risks across five categories. Each risk
is scored before and after mitigation, and has one owner who answers for it. The Roadmap page of the
app shows the same register from `config/roadmap.yaml`, and a test keeps the two in step.

The first seven risks are the ones that sink projects like this one. They seldom fail in a single
event. The data just quietly stops being true. They are described in full after the register.

## How risks are scored

**Likelihood** is the chance the risk happens at some point in the 18 months.

| Score | Label | Meaning |
| :-: | --- | --- |
| 1 | Rare | Less than 10% |
| 2 | Unlikely | 10% to 30% |
| 3 | Possible | 30% to 50% |
| 4 | Likely | 50% to 80% |
| 5 | Almost certain | More than 80% |

**Impact** is the effect if it does happen. The money thresholds are scaled to a fabricator turning over
about £11m a year, which is what the prototype's synthetic sales ledger shows for the 12 months to
August 2026.

| Score | Label | Meaning |
| :-: | --- | --- |
| 1 | Negligible | Absorbed within a phase; no effect on customers, compliance or benefits |
| 2 | Minor | Delay under a month, or cost under £10,000 |
| 3 | Moderate | Delay of one to three months, cost of £10,000 to £50,000, or one benefit lost |
| 4 | Major | Delay of three to six months, cost of £50,000 to £150,000, a phase that fails its exit, or a minor audit finding |
| 5 | Severe | The programme fails; a major EN 1090 nonconformity or suspended certification; a safety risk; or a loss above £150,000 |

The **inherent score** is likelihood times impact with no mitigation in place. The **residual score** is
the same product once the mitigation is working. Scores fall into four bands: 1 to 4 low, 5 to 9 medium,
10 to 14 high, 15 to 25 very high.

The programme manager reviews the register every month. A risk that reaches very high goes to the
sponsor the same week. The management committee sees every high and very high risk at each quarterly
review. When the programme closes, open risks move to the company risk register with an owner.

## The register

L is likelihood and I is impact. The owners are roles, set out in `docs/rollout-plan.md` and
`docs/data-ownership.md`.

| ID | Category | Risk | L | I | Inherent | Mitigation | Owner | Residual L | Residual I | Residual |
| --- | --- | --- | :-: | :-: | :-: | --- | --- | :-: | :-: | :-: |
| R01 | People | Shop-floor resistance to time-booking discipline | 4 | 5 | **20** | Design the booking form with operators at both sites and usability-test it before build sign-off: a booking takes under 30 seconds and is picked from the live works orders for that bay, with no numbers typed. The Managing Director commits in writing, agreed with employee representatives and recorded in the data protection impact assessment, that bookings are used for job costing, traceability and welder records and never for individual performance management. Train a floor champion per site per shift first, keep the paper fallback, show each site its own booking quality weekly, and pilot one site before the second. | Production Controller | 3 | 4 | **12** |
| R02 | Data | Master data cleanse effort underestimated by an order of magnitude | 4 | 4 | **16** | Size the cleanse in Phase 1 from the real queues, with minutes per item measured on a timed sample rather than assumed, and count everything the prototype's 9-hour estimate leaves out: certificate recovery, aged exceptions, recounts, stale works orders and bank detail checks. Plan at the measured rate plus 50%. Clean only records used in the last 24 months and archive the rest. Ring-fence steward hours and report the burn-down weekly; if it falls 20% behind for three weeks, bring in temporary cleanse support rather than stretch the phase. | Programme manager | 2 | 4 | **8** |
| R03 | People | Key-person dependency on the one person who understands Corvus | 3 | 5 | **15** | In Phase 1, record walkthroughs of every extract, report, batch routine and month-end task, write the runbook, and name a backup user who performs each task unaided before Phase 1 can exit. Backfill half the key user's day job so the programme gets their time without burning them out. Agree a retention arrangement to month 18, and add named consultant days to the Corvus support contract as a second line. | Programme sponsor | 2 | 3 | **6** |
| R04 | Compliance | EN 1090 compliance exposure during the transition | 3 | 5 | **15** | Contain at goods-in in Phase 1, before any system changes: no heat number and 3.1 certificate, no booking into stock, and untraceable steel red-tagged into a quarantine bay. Update the factory production control procedures and brief the certification body before each go-live. The Quality Manager's traceability gate must pass before any cutover, and every cutover keeps a paper fallback that captures heat numbers. Run the traceability reconciliation weekly through the transition, with any new receipt lacking a full chain raised as a same-day critical exception. | Quality Manager | 2 | 5 | **10** |
| R05 | People | Dual-running cost and fatigue | 4 | 3 | **12** | Give every parallel run a fixed end date and switch-off criteria agreed before it starts: three month-ends for reporting, four weeks per site for the forms. The owner switches off against the criteria, not by consensus, and the old spreadsheets are locked read-only that day. Budget the extra hours per role in the Phase 1 plan, backfill routine keying with temporary staff, and report the extra hours at every review. | Programme manager | 2 | 3 | **6** |
| R06 | Data | The finance calendar and the production week never align | 5 | 3 | **15** | Agree one calendar rule in Phase 1 and build it into the warehouse as a date table that maps every day to its production week and its finance period. Monthly KPIs allocate bookings by booking date, not by week, and weekly capacity is prorated by working days until the forms capture it daily. Every KPI states which calendar it uses, and the management accountant reconciles warehouse labour to the ledger each month with every difference explained. | Finance Manager | 2 | 2 | **4** |
| R07 | Commercial | Benefits claimed but never measured because no baseline was taken | 4 | 4 | **16** | Freeze the baseline at the end of Phase 1 from the real data, signed by the Finance Manager and stored as a snapshot that is never overwritten, with each measure's monthly range over 12 months so improvement can be told from noise. Give every benefit an owner, a KPI definition and the query that produces it. A changed definition restates the baseline instead of flattering the trend. Read benefits at reviews 3 to 6, and count one only when it has held for three months. | Finance Manager | 1 | 4 | **4** |
| R08 | Compliance | Certificates for steel already despatched cannot be recovered | 4 | 4 | **16** | Request duplicate certificates from mills and stockholders by heat number from Phase 1, starting with EXC3 work such as towers and rail structures. The Quality Manager assesses each exposed job by execution class and agrees with the certification body and the customer whether testing or notification is needed. Take legal and insurance advice before any customer is notified. | Quality Manager | 3 | 3 | **9** |
| R09 | Compliance | Booking data on named operators breaches data protection law as covert performance monitoring | 3 | 4 | **12** | Complete a data protection impact assessment before real bookings are loaded, and issue a privacy notice to employees. Limit the purposes to job costing, traceability and welder qualification records. Reports aggregate by works order, bay and site; operator-level data is open only to the Quality Manager for welder records. Set a retention period and delete to it. | Finance Manager | 1 | 4 | **4** |
| R10 | Compliance | Financial controls weaken at cutover | 2 | 4 | **8** | Keep every finance cutover at least six weeks away from the financial year end, and brief the external auditor on the timetable before Phase 3. The three-way match exception queue stays the control of record throughout, and no held invoice is paid. Archive retired spreadsheets and reports read-only for the statutory retention period. | Finance Manager | 1 | 4 | **4** |
| R11 | Technical | Corvus cannot record material issues or enforce mandatory fields | 3 | 4 | **12** | Test on a copy of Corvus in Phase 1 whether issues can be posted, fields made mandatory and import files accepted. If issues cannot be posted, record them on the shop-floor form against the cutting list and load them nightly. If fields cannot be made mandatory, check them at the form and quarantine any gap the next morning, so detection by the next morning replaces prevention. | Production Controller | 3 | 2 | **6** |
| R12 | Commercial | The Corvus vendor restricts or charges for extract and import access | 3 | 4 | **12** | Get written confirmation of extract and import rights and prices in Phase 1, before the Phase 3 build is committed. Fall back to scheduled report exports for reading and steward-keyed change lists for writing, both already allowed by the integration design. Hold a line for vendor fees in the contingency. | Purchasing Manager | 2 | 3 | **6** |
| R13 | Technical | Shop-floor terminals fail in the fabrication shop | 3 | 3 | **9** | Survey Wi-Fi in every bay in Phase 1, because steel-framed bays and cranes block the signal. Fit industrial-rated terminals at bay ends, usable in gloves and away from grinding and weld spatter. The form works offline and syncs later; the paper fallback sheet is keyed the next day and marked late. Hold spare terminals at each site. | Production Controller | 2 | 2 | **4** |
| R14 | Technical | Nightly loads fail or run partially and decisions are taken on stale figures | 3 | 3 | **9** | Keep loads all-or-nothing, as the prototype already is, so a failed load leaves the previous night's complete version in place. Show the "as at" date on every report. Alert the owner of a failed load by the next morning, and check the run log daily in hypercare and weekly after. | Integration lead | 2 | 2 | **4** |
| R15 | Technical | The new server and extract accounts widen the attack surface for finance and supplier data | 2 | 5 | **10** | Use read-only extract accounts with the least access needed, and keep the warehouse on a company server inside the existing backup, patching and access control. Bank details are never extracted. Apply Cyber Essentials controls to the new server and review access at every management committee review. | Finance Manager | 1 | 5 | **5** |
| R16 | Data | Real extracts are messier than the demonstrator suggests | 4 | 3 | **12** | Run the prototype pipeline on the real extracts in month 2 and profile them before committing any later date. Add a contract or rule for every new pattern found, and re-baseline the plan at review 1 from what the real data shows. | Integration lead | 2 | 3 | **6** |
| R17 | Data | A wrong automatic match merges two grades of the same section | 2 | 5 | **10** | Never infer grade where a section is stocked in more than one grade: those lines go to a person with the mill certificate. Merge automatically only at a score of 95 or more. The buyer audits a sample of 20 automatic matches each week during Phase 2, and every merge is reversible because the crosswalk keeps each original value. | Purchasing Manager | 1 | 5 | **5** |
| R18 | Data | A supplier merge or write-back causes a duplicate or misdirected payment | 2 | 5 | **10** | Reconcile supplier statements before merging and freeze payment runs on accounts being merged. Bank details never travel through the integration and change only under dual signature, confirmed by telephone to a number already on file. Write-back starts as steward-keyed change lists and is automated only after a dry run on a copy. | Finance Manager | 1 | 5 | **5** |
| R19 | Data | KPIs are read without their caveats and drive the wrong decision | 3 | 3 | **9** | Every KPI in the pack carries its caveat and is signed by its owner before issue. OTIF is labelled as despatch against the internal planned finish until the delivery note form captures the contract promise date, and is then restated. Senior management training covers reading the caveats. | Production Controller | 2 | 2 | **4** |
| R20 | People | Data owners and stewards have no time to clear the queues | 4 | 3 | **12** | Ring-fence steward hours from the measured Phase 1 sizing and write them into objectives. Review each owner's scorecard monthly at the data governance group, apply the escalation route's time limits, and backfill routine work where the hours cannot be found. | Programme sponsor | 2 | 3 | **6** |
| R21 | Commercial | A contract peak takes the same people and the programme stalls | 4 | 3 | **12** | Compare programme load with the order book at every review. Plan go-lives away from known peaks and shutdowns, and pilot at the site with the lighter load. If a peak hits, pause the phase cleanly at a gate rather than cut its exit criteria. | Programme sponsor | 3 | 2 | **6** |
| R22 | Commercial | Restated job costs change reported margins on live contracts | 3 | 3 | **9** | Restate from a fixed date forward and never reopen agreed final accounts. Explain each movement with the job cost reconciliation drill-down, and brief project managers before the first restated pack. | Finance Manager | 2 | 2 | **4** |
| R23 | Commercial | Budget overrun from vendor fees, contractor days and shop-floor hardware | 3 | 3 | **9** | Release funding phase by phase at the management committee reviews against the re-baselined plan. The sponsor holds the contingency, hardware and vendor work is bought on fixed-price quotes, and spend against plan is reported at every review. | Programme sponsor | 2 | 3 | **6** |

Before mitigation, 7 risks are very high, 10 high and 6 medium. After mitigation, 2 remain high
(R01 and R04), 13 are medium and 8 low. The two that stay high are the shop floor's acceptance of time
booking and EN 1090 exposure during the transition. No plan removes them. They are managed at every
review until the programme closes.

## Heat maps

Inherent scores, before mitigation:

| Impact \ Likelihood | 1 Rare | 2 Unlikely | 3 Possible | 4 Likely | 5 Almost certain |
| --- | --- | --- | --- | --- | --- |
| 5 Severe |  | R15, R17, R18 | R03, R04 | R01 |  |
| 4 Major |  | R10 | R09, R11, R12 | R02, R07, R08 |  |
| 3 Moderate |  |  | R13, R14, R19, R22, R23 | R05, R16, R20, R21 | R06 |
| 2 Minor |  |  |  |  |  |
| 1 Negligible |  |  |  |  |  |

Residual scores, with the mitigations working:

| Impact \ Likelihood | 1 Rare | 2 Unlikely | 3 Possible | 4 Likely | 5 Almost certain |
| --- | --- | --- | --- | --- | --- |
| 5 Severe | R15, R17, R18 | R04 |  |  |  |
| 4 Major | R07, R09, R10 | R02 | R01 |  |  |
| 3 Moderate |  | R03, R05, R12, R16, R20, R23 | R08 |  |  |
| 2 Minor |  | R06, R13, R14, R19, R22 | R11, R21 |  |  |
| 1 Negligible |  |  |  |  |  |

## What we watch

Each risk has an early warning indicator, and a trigger level at which its owner acts without waiting for
the next review. Most indicators come from the warehouse, so nobody has to compile them by hand.

| ID | Indicator | Trigger for action |
| --- | --- | --- |
| R01 | Hours booked on the form within 24 hours against a live works order, by site, weekly | Below 95% for two consecutive weeks |
| R02 | Cleanse burn-down against plan, weekly | 20% behind for three consecutive weeks |
| R03 | Runbook tasks the backup user has performed unaided | Any task not signed off by the end of month 3, or the key user absent for more than two weeks |
| R04 | New receipts without heat number or certificate (DQ-01, DQ-02) | Any one |
| R05 | Extra hours per week spent on dual running, by role | Above plan for two weeks, or any parallel run past its end date |
| R06 | Monthly difference between warehouse labour and ledger labour | Outside the agreed tolerance two months running |
| R07 | Benefits reported without a baseline and a query | Any one |
| R08 | Exposed jobs without a Quality Manager decision | Any EXC3 job still open at review 2 |
| R09 | Data protection impact assessment status; requests for operator-level productivity reports | Not approved by month 3, or any such request |
| R10 | Held invoices paid; payments without a match in a cutover month | Any one |
| R11 | Results of the tests on a copy of Corvus | Any test failed by month 3 |
| R12 | Vendor's written confirmation of rights and prices | Not received by month 2 |
| R13 | Share of bookings made on the paper fallback | Above 5% in any week |
| R14 | Failed or late nightly loads | Two in a month |
| R15 | Access review exceptions; unpatched critical vulnerabilities on the server | Any one |
| R16 | New data patterns needing a rule when real extracts are profiled | More than ten in month 2 |
| R17 | Wrong automatic matches in the weekly sample | Any merge across grades |
| R18 | Payments to a merged or blocked supplier account | Any one |
| R19 | KPI figures quoted without their caveat in minutes or decisions | Any one |
| R20 | Queue items older than the five-day steward limit | More than 10% of a queue |
| R21 | Order book hours against capacity for the next quarter | Above 95% at a review |
| R22 | Live contract margins moving after restatement | More than 5 points before the project manager is briefed |
| R23 | Programme spend against plan | More than 10% over at a review |

## The seven risks that sink projects like this

### R01. Shop-floor resistance to time-booking discipline

**Why it sinks projects.** Almost every figure the programme promises rests on time bookings: job cost,
labour variance, WIP, capacity and the welder record behind EN 1090. Operators see booking as admin at
best and surveillance at worst. If the form is slower than the pencil, they book the week from memory on
Friday, and the new system faithfully records fiction. Supervisors quietly restart their spreadsheets.
Nothing visibly breaks; the data just stops being true.

**What the prototype shows.** On the synthetic booking sheets, 189 shop-floor rows are quarantined as
unreadable or duplicated. 379 bookings name no operation and 276 name no operator. 242 hours are booked to
6 works orders Corvus has never heard of. The supervisors' weekly totals differ from the booking sheets in
198 of 204 site-weeks, by 1,118 hours in all.

**Early warning.** Booking completeness by site during the pilot. Bookings arriving in batches at the end
of a week. Spreadsheets reappearing on a supervisor's desk.

**If it happens anyway.** Review 4 holds the second site back. The programme goes back to the operators to
find out what is wrong with the form, and fixes the form, not the operators.

### R02. Master data cleanse effort underestimated by an order of magnitude

**Why it sinks projects.** Cleanse estimates are made from the tidy part of the data. The expensive part
is the item that needs a person to find a paper, ring a supplier or walk to the rack. Everything after
the cleanse depends on it. Write-back sends clean records, and the shop-floor pick lists show clean
works orders. So an underestimate here delays every later phase at once.

**What the prototype shows.** The match review queue is 93 decisions, estimated at 9.1 hours, using
minutes per item that are assumptions. It is tempting to plan on that figure. The same synthetic data also
holds 178 receipts whose certificates must be recovered and 246 order and receipt lines with no grade.
There are 1,074 purchasing exceptions older than 90 days, 40 stock lines not counted for 90 days, and
65 works orders in WIP for more than 90 days. On top of that come 20 finance-only job codes and 5
duplicate supplier entities, with 3 more likely. The prototype holds 47 materials and 63 supplier
entities. A Corvus installed in 2006 will hold thousands of codes, including bolts, consumables and items
nobody has bought for years. Ten times the queue estimate is a realistic starting point, not a
pessimistic one.

**Early warning.** The timed sample in Phase 1 against the assumed minutes per item, then the weekly
burn-down.

**If it happens anyway.** Bring in temporary cleanse support, and narrow the scope to records used in the
last 24 months. Do not start Phase 4 on a domain that is not clean, or the pick lists carry the mess onto
the shop floor.

### R03. Key-person dependency on the one person who understands Corvus

**Why it sinks projects.** A system installed in 2006 with its own reports and conventions is usually
understood by one person, often the planner or administrator who set it up. Every extract, code block and
write-back depends on them. The programme doubles their workload exactly when it needs them most, and
that is when people leave or go off sick.

**What the prototype shows.** Corvus writes fixed-width codes, truncates names and keeps its own customer
and supplier numbering. It records no material issues. Knowing which report produces which file, and what
each padded field means, is exactly the knowledge that sits in one head.

**Early warning.** Runbook tasks not yet performed by the backup user; the key user's overtime and
absence.

**If it happens anyway.** The backup user runs the runbook, and the vendor's named consultant days cover
the rest. Write-back work pauses until someone can own it.

### R04. EN 1090 compliance exposure during the transition

**Why it sinks projects.** Factory production control certification under EN 1090 is a licence to trade:
without it, structural steelwork cannot be UKCA or CE marked. The transition is the riskiest time for it.
Records move from paper to forms, people are learning new screens, and during dual running each side can
assume the other captured the heat number. A finding at a surveillance visit during the programme is
worse than one before it, because the programme was meant to fix exactly this.

**What the prototype shows.** What EN 1090-2 requires depends on each structure's execution class: 53 jobs
are EXC3 and 97 EXC2. Traceability coverage is 66.4% by weight on EXC3 work and 69.9% on EXC2. 786 tonnes
already despatched carry an EN 1090 compliance exposure, on 145 jobs for 38 customers: 384 tonnes of EXC3
steel without a complete chain from mill certificate to delivery, and 402 tonnes of S355 on EXC2 jobs with no
3.1 certificate shown. A further 316 tonnes on EXC2 work have incomplete chains, a good-practice gap rather
than a breach of the standard. Chains break where the heat number is missing (651 lines), the certificate is
missing (458), the grade is unconfirmed on receipt (656), there is no receipt on record (74) or there is no
delivery note (21). Four of the five breached critical data quality rules are about traceability, among them
DQ-41: 69 receipts of S355 with no 3.1 certificate.

**Early warning.** Any new receipt without heat number or certificate. Findings from the internal
traceability audit.

**If it happens anyway.** The Quality Manager uses the safety fast track in `docs/data-ownership.md` to
quarantine material or stop despatch at once. The certification body is told, and the affected process
goes back to its paper fallback, which captures heat numbers, until the gap is closed.

### R05. Dual-running cost and fatigue

**Why it sinks projects.** Dual running is sold as a safety net and becomes a trap. Supervisors fill in
the spreadsheet and the form, and finance produces two month-end packs. After a few weeks one gets
skipped, usually the new one. Or the old one is never switched off, because nobody wants to be the person
who switched it off. Tired people make keying errors. Those errors show up as differences between the two
runs, and the differences are used to extend the parallel run.

**What the plan commits to.** Three parallel month-ends for reporting (months 8 to 10), four weeks of
parallel running per site for the forms (months 11 and 13), and no more. The switch-off criteria are
written before each run starts.

**Early warning.** Extra hours by role, reported weekly. A parallel run past its end date. Differences
left unexplained for more than a week.

**If it happens anyway.** Switch off on the criteria. The owner may extend a run once, to a new fixed
date, and must record why.

### R06. The finance calendar and the production week never align

**Why it sinks projects.** Production plans and books in weeks commencing Monday; finance closes calendar
months. A week that straddles a month end is split in one system and not in the other. Utilisation,
labour cost and WIP then never tie to the management accounts. Every monthly meeting spends its first
half hour on whose number is right, and trust in the new figures drains away.

**What the prototype shows.** Of 106 production weeks in the synthetic capacity sheets, 22 straddle a
month end. They carry 13,880 of the 71,844 hours the supervisors report as booked, 19%. Finance posts job
costs by calendar month, the booking sheets are daily, and capacity is weekly: three calendars already.

**Early warning.** The monthly difference between labour in the warehouse and labour in the ledger.

**If it happens anyway.** Publish both views with the bridge between them, line by line. Do not try to
move finance onto production weeks. It is not the programme's decision, and it would move the argument
rather than end it.

### R07. Benefits claimed but never measured because no baseline was taken

**Why it sinks projects.** Once the new way is live, nobody can remember what before looked like, and
the old spreadsheets have gone. Benefits are asserted from anecdote and challenged by the board, and the
programme looks as if it cost money for nothing, which makes the next improvement harder to fund. Worse,
better data often makes a KPI look worse at first. Cost of quality rises when every NCR is costed. Without
a baseline, that reads as failure.

**What the prototype shows.** The mechanism exists. Every KPI has a definition, a caveat and a query.
Data quality results are appended per run and never overwritten, and raw extracts are kept exactly as
received. What a real rollout adds is the discipline to freeze the baseline, sign it and keep it. See
`docs/benefits-case.md`.

**Early warning.** Any benefit reported without a baseline and a query.

**If it happens anyway.** Rebuild the baseline from the Phase 1 extracts, which are archived read-only
for this purpose, and restate every benefit claimed so far.

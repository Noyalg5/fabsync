# Benefits case (ILLUSTRATIVE)

> **ILLUSTRATIVE. Demonstration prototype. All data is synthetic.** This whole document is illustrative.
> It is not a forecast for any real business. Every baseline is measured by the prototype on synthetic
> data. Every target and every pound value is modelled from those baselines and from assumptions stated
> below. The real baseline is taken from the business's own systems in Phase 1 of
> `docs/rollout-plan.md`, and it replaces every baseline here.

## What this document is

It says which measures each phase of the rollout moves, where each stands today in the prototype, what
the programme aims for, and why. It shows the method a real benefits case should follow: a measured
baseline, a stated mechanism, a target that follows from them by arithmetic anyone can check, and an
honest statement of what is not claimed.

It does not set the programme's cost against the benefits. Costs come from the plan re-baselined at
review 1, once the real cleanse has been sized.

## How to read the figures

Every figure carries one of three labels, and they are never mixed.

- **Measured (synthetic).** Calculated by FabSync from the synthetic extracts, as at 31 August 2026,
  over the 24 months of history, and reproducible from the table named beside it. A test
  (`tests/test_planning.py`) rebuilds the warehouse and fails if any baseline here stops agreeing with
  it.
- **Modelled.** Calculated from measured figures and stated assumptions by the arithmetic shown, or set
  as a planning target. A modelled figure is an estimate or an aim, never a result.
- **Assumption.** An input nobody has measured. Each is numbered (A1 to A9) and listed at the end with
  how it will be replaced by a measurement.

Confidence says how far a modelled figure can be trusted.

- **High:** the mechanism is direct and within the programme's control, such as a form that will not
  accept a works order that does not exist.
- **Medium:** the mechanism is direct but depends on people changing what they do.
- **Low:** the figure depends on an assumption or on things the programme does not control.

## What each phase moves

*ILLUSTRATIVE.* ● means the phase is expected to move the measure. ○ means the phase changes how the
measure is taken, through a new definition or more complete data, without claiming a move.

| Measure | 1. Discovery and baseline | 2. Master data cleanse | 3. Read-only integration and reporting | 4. Process change and write-back | 5. Embed and handover |
| --- | :-: | :-: | :-: | :-: | :-: |
| KPI-01 OTIF delivery performance | ○ | | | ● ○ | |
| KPI-02 Labour variance | | | | ○ | |
| KPI-03 Material yield and offcut waste | | | | ● ○ | |
| KPI-04 Stock accuracy | | ● | | ● | |
| KPI-05 Three-way match exception rate | | ● | ● | ● | |
| KPI-06 Material traceability coverage | ● | ● | | ● ○ | |
| KPI-07 WIP value and ageing | | ● | | ○ | |
| KPI-08 Capacity utilisation | | | | ○ | |
| KPI-09 NCR rate and cost of quality | ● | | | ○ | |
| DQI Data quality index | | ● | ● | ● | ● |

The programme claims no improvement in labour variance or capacity utilisation. It makes those figures
trustworthy, which is a different thing. Phase 5 moves nothing new. It proves the gains against the
baseline and shows they hold without the programme team.

## Phase by phase

### Phase 1. Discovery and baseline (months 1 to 3)

Phase 1's product is the baseline itself. The only measures it moves are the ones the goods-in control
changes at once.

*ILLUSTRATIVE. Baselines measured on synthetic data; targets modelled.*

| ID | Measure | Baseline, measured (synthetic) | Target, modelled | By month | Basis of the estimate | Confidence |
| --- | --- | --- | --- | :-: | --- | --- |
| S-04 | Receipts without a heat number or mill certificate | 178 of 989 receipts | None among receipts booked after the goods-in control starts | 2 | Goods-in refuses to book the steel. Rules DQ-01 and DQ-02 check every new receipt daily. | High |
| S-11 | Cost of NCRs raised for a missing mill certificate | £32k on 24 NCRs over 24 months | 75% lower (A7) | 15 | These NCRs start with steel accepted without its certificate, which the control now stops at the door. A7 stays an assumption until six months of the NCR log show the real fall. | Medium |

### Phase 2. Master data cleanse (months 3 to 8)

*ILLUSTRATIVE. Baselines measured on synthetic data; targets modelled.*

| ID | Measure | Baseline, measured (synthetic) | Target, modelled | By month | Basis of the estimate | Confidence |
| --- | --- | --- | --- | :-: | --- | --- |
| S-01 | Master data review queue | 93 items | Empty, or every open item accepted by its owner | 8 | Phase 2 exit criterion, with the work sized from the real queue in Phase 1 | High |
| S-02 | Finance job codes with no Corvus job | 20 | 0 | 8 | Each code mapped or closed. The crosswalk rule stops new ones being created. | High |
| S-03 | Duplicate supplier entities | 5 confirmed, 3 more likely | 0 | 8 | Merged in finance, one account per Corvus code, old codes blocked | High |
| S-04 | Receipts without a heat number or mill certificate, historic | 178 of 989 receipts | Every one traced or decided by the Quality Manager | 8 | A decision on every gap can be promised. A certificate for every gap cannot, because it depends on mills answering. | Medium |
| S-05 | Three-way match exceptions older than 90 days | 1,076 | None without an owner's decision | 8 | Each chased, accrued, credited or written off with approval | Medium |
| KPI-04 | Stock accuracy | 89.6% | 95% | 9 | Every line not counted in 90 days is recounted and every material gets one stocking unit. On the 106 counted lines, 95% allows 5 lines out, against 11 today. | Medium |
| KPI-07 | Share of WIP value over 90 days old | 54.9% of £714k | 32.8% | 9 | Works orders whose work has gone are closed. A5 puts 60% of the over-90-day value in that admin backlog, leaving 40% of £392k in a total that falls by the rest. The prototype cannot measure the backlog, because delivery notes do not name works orders. | Low |
| DQI | Data quality index | 92.1 | Master data rules DQ-04, DQ-05, DQ-07, DQ-08, DQ-09 and DQ-10 at threshold | 8 | Phase 2 exit criterion | Medium |

### Phase 3. Read-only integration and reporting (months 5 to 10)

Phase 3 moves few figures by itself. What it delivers is the nine KPIs every month, built without anyone
touching a spreadsheet, each traceable to its source rows. That is what makes every other benefit here
measurable.

*ILLUSTRATIVE. Baselines measured on synthetic data; targets modelled.*

| ID | Measure | Baseline, measured (synthetic) | Target, modelled | By month | Basis of the estimate | Confidence |
| --- | --- | --- | --- | :-: | --- | --- |
| S-06 | Purchase orders with no goods receipt, and receipts with no invoice | 148 lines (82 and 66) | 75% fewer (A8) | 12 | Each owner works the queue daily instead of finding the item at month-end, or never | Medium |

### Phase 4. Process change and write-back (months 9 to 15)

*ILLUSTRATIVE. Baselines measured on synthetic data; targets modelled.*

| ID | Measure | Baseline, measured (synthetic) | Target, modelled | By month | Basis of the estimate | Confidence |
| --- | --- | --- | --- | :-: | --- | --- |
| KPI-06 | Material traceability coverage | 68.7% | At least 99% on works orders started after go-live | 15 | Issues recorded from cutting lists replace the first-in first-out inference, and the heat number travels with cut pieces and offcuts | Medium |
| S-08 | Material cost charged to the wrong job | £1.43m over 24 months | Under 2% of material cost on jobs started after month 14 | 18 | Steel is charged from the issue, which removes the mechanism that creates the gap | High |
| S-09 | Hours booked to works orders not in Corvus | 242 hours | 0 | 11 | The form accepts only live works orders | High |
| S-10 | NCRs with no cost | 45 of 246 | Every NCR costed within 7 days | 13 | The NCR form reminds the Quality Manager after 7 days | High |
| S-07 | Invoices with no purchase order | 726 invoices, £3.41m over 24 months | None outside exempt overhead nominals | 12 | No purchase order, no payment from month 10, using the service suppliers set up in Phase 2 | Medium |
| S-13 | Capacity figures that disagree with the bookings | 198 of 204 site-weeks, 1,118 hours | None | 15 | Supervisors' totals and bookings come from the same form | High |
| KPI-05 | Three-way match exception rate | 53.8% | 11.4% | 18 | Quantity variances fall by A1 (80%), as agreed shortfalls are recorded on the order at receipt. Price variances fall by A2 (80%), as invoices beyond tolerance are held and credited. Missing receipts and invoices fall by A8 (75%). The arithmetic is (377 × 0.2 + 48 × 0.2 + 148 × 0.25) / 1,066 lines assessed. | Low |
| KPI-04 | Stock accuracy | 89.6% | Held at 95% or more | 18 | Recorded issues keep the book in step with the rack | Medium |
| KPI-01 | OTIF delivery performance | 16.7% | 37.5% on today's definition | 18 | A6 assumes a quarter of late deliveries have an information cause the programme removes: steel not found or held in the wrong unit, a works order that does not exist, a WIP backlog hiding real progress. That gives 16.7% plus a quarter of the 83.3% late. The programme adds no shop capacity, so it does not reach the 95% standard on its own. | Low |
| KPI-03 | Material yield and offcut waste | 76.2% (theoretical) | Restated baseline plus 2 points (A4) | 18 | Offcuts returned with their heat number can be reused. The baseline is restated once recorded issues show the actual yield. | Low |

### Phase 5. Embed and handover (months 14 to 18)

*ILLUSTRATIVE. Baselines measured on synthetic data; targets modelled.*

| ID | Measure | Baseline, measured (synthetic) | Target, modelled | By month | Basis of the estimate | Confidence |
| --- | --- | --- | --- | :-: | --- | --- |
| DQI | Data quality index | 92.1 | 98.1, held for three months | 18 | 98.1 is the index the prototype would score if every critical and high rule met its threshold and the medium and low rules stayed as they are today. The Phase 2 and Phase 4 exit criteria bring those rules to threshold, and Phase 5 shows they stay there without the programme team. | Medium |

## Summary at month 18

*ILLUSTRATIVE. Baselines measured on synthetic data; standards from `config/kpis.yaml`; targets
modelled.*

| ID | Measure | Baseline, measured (synthetic) | Source | Standard in `config/kpis.yaml` | Target at month 18, modelled | Moved by |
| --- | --- | --- | --- | --- | --- | --- |
| KPI-01 | OTIF delivery performance | 16.7% | `marts.kpi_scorecard` | 95% or more | 37.5% on today's definition, then restated | Phase 4 |
| KPI-02 | Labour variance | 7.4% | `marts.kpi_scorecard` | Within ±10% | Within ±10%, with every hour on a live works order | Measured better, not moved |
| KPI-03 | Material yield and offcut waste | 76.2% | `marts.kpi_scorecard` | 85% or more | Restated baseline plus 2 points | Phase 4 |
| KPI-04 | Stock accuracy | 89.6% | `marts.kpi_scorecard` | 95% or more | 95% | Phases 2 and 4 |
| KPI-05 | Three-way match exception rate | 53.8% | `marts.kpi_scorecard` | 5% or less | 11.4% | Phases 2, 3 and 4 |
| KPI-06 | Material traceability coverage | 68.7% | `marts.kpi_scorecard` | 100% | 100% on new receipts; at least 99% on new works orders | Phases 1, 2 and 4 |
| KPI-07 | WIP value and ageing | 54.9% over 90 days | `marts.kpi_scorecard` | No target | 32.8% over 90 days | Phase 2 |
| KPI-08 | Capacity utilisation | 86.1% | `marts.kpi_scorecard` | 75% to 95% | Within 75% to 95%, from one source | Measured better, not moved |
| KPI-09 | NCR rate and cost of quality | 1.3% | `marts.kpi_scorecard` | 2% or less | Every NCR costed; missing-certificate NCR cost 75% lower | Phases 1 and 4 |
| DQI | Data quality index | 92.1 | `governance.dq_results` | No target | 98.1 | Phases 2 to 5 |

The OTIF target shows why the labels matter. The standard is 95%, while the programme's modelled target
is 37.5%, resting on an assumption. Presenting the programme as the route to 95% would be the kind of
claim this document exists to prevent.

## Illustrative pound values

Only three benefits are given a pound value. Each comes from a measured input, one or two assumptions,
and arithmetic shown in full. A year means half of the 24-month measured total, which is itself a
modelling step.

*ILLUSTRATIVE. Inputs measured on synthetic data; every value modelled.*

| Benefit | Measured input (synthetic) | How the value is modelled | Low | Central | High | Confidence |
| --- | --- | --- | --: | --: | --: | --- |
| Overcharges stopped | 48 invoices beyond tolerance, £59k over 24 months | £30k a year, times A2 (50%, 80%, 95%) | £15k | £24k | £28k | Medium |
| Offcuts reused | 5,118 tonnes of bars bought for 3,899 tonnes used over 24 months (76.2% yield), at an average £1,068 a tonne | The steel no longer bought each year if yield rises by A4 (1, 2 or 4 points), at the average price less the scrap value A3 (£888 a tonne net) | £29k | £58k | £113k | Low |
| NCRs for a missing certificate avoided | 24 NCRs, £32k over 24 months | £16k a year, times A7 (50%, 75%, 90%) | £8k | £12k | £14k | Medium |
| **Total a year** | | | **£52k** | **£94k** | **£156k** | Low |

Against a synthetic turnover of £11.44m in the 12 months to August 2026, this is modest, and it is
meant to be. The strongest reasons for the programme are keeping EN 1090 certification and having
figures the business can decide from. Neither is given a pound value below.

## What is not claimed

These are real measured figures that are easy to turn into large, false savings.

*ILLUSTRATIVE. Measured on synthetic data.*

| Measured figure (synthetic) | Value | Why no pound benefit is claimed |
| --- | --- | --- |
| Invoices with no purchase order | £3.41m | The spend is real and may be correctly priced. Requiring an order is a control, not a saving. Any saving from quoting services competitively is speculative. |
| Short deliveries beyond the 2% tolerance | £116k | The invoices on these lines agree with the quantity received, so no money was lost. The cost is steel short at the bay. |
| Material cost charged to the wrong job | £1.43m | It cancels out across jobs, so the net effect is nil. The benefit is job margins that can be priced from, not cash. |
| Gross unexplained job cost gap | £1.74m | As above. It measures how wrong individual job costs are, not money lost. |
| WIP more than 90 days old | £392k | Closing works orders corrects the report. No cash moves. |
| Goods received but not invoiced | £428k | Accruals become accurate. The money is owed either way. |
| Stock value error | £15k | The book becomes accurate. Adjustments go both ways. |
| Hours booked to works orders not in Corvus | 242 hours | The cost moves to the right job. Nothing is saved. |
| Sales on jobs with incomplete traceability | £14.47m | This is the value of work exposed, not a loss. Keeping certification is a licence to trade, and it is not priced here. |
| Office time spent re-keying | Not measured | Phase 1 times it. It is claimed only once measured, and only if the hours are redeployed. |

## Figures that will look worse before they look better

Better data often makes a KPI look worse. Without a warning, that reads as the programme failing.

*ILLUSTRATIVE. Baselines measured on synthetic data; movements modelled.*

| Measure | Why it may worsen | Modelled effect |
| --- | --- | --- |
| KPI-09 Cost of quality | 45 of 246 NCRs carry no cost today and count as nil. Costing them all raises the figure. | 1.3% rises to about 1.59% if uncosted NCRs cost the same on average as costed ones (A9) |
| KPI-02 Labour variance | Hours now lost to works orders that do not exist, or to unreadable rows, will be captured against real jobs | Variance may rise within the ±10% band |
| KPI-06 Traceability coverage | Recorded issues replace an inference, and may reveal breaks the inference hid | Either direction; restated |
| KPI-01 OTIF | The promise date moves from the internal planned finish to the contract date | Either direction; restated |
| KPI-03 Material yield | Actual yield from recorded issues replaces a theoretical figure | Either direction; restated |
| DQI | Rules added in Phase 1 for patterns found in the real data widen what is checked | May fall at first |

## How the real benefits will be measured

1. **The real baseline replaces this one.** At the end of Phase 1, each baseline here is replaced by the
   same measure on the business's own data, signed by the Finance Manager and stored as a snapshot that
   is never overwritten.
2. **Same definition before and after.** If a definition changes, the baseline is restated by the new
   definition and the restatement is shown beside the old figure.
3. **Ranges, not points.** Monthly figures move a lot on their own. In the 12 months to August 2026,
   monthly OTIF ranged from 9.4% to 31.3% across the months with at least 20 measured deliveries. The
   monthly three-way exception rate ranged from 43.6% to 58.5% across the months with at least 20 order
   lines assessed, and monthly cost of quality from 0.11% to 3.10%. All of these are measured on synthetic
   data. A single month anywhere inside those ranges proves nothing.
4. **Held for three months.** A benefit counts only when it has held for three consecutive months.
5. **An owner and a query for each.** Every benefit has a named owner and the query that produces it,
   so anyone can check it.
6. **Other causes named.** Order mix, steel prices and staffing also move these figures. The benefits
   review says what else changed.
7. **Read at the reviews.** Review 3 reads the Phase 2 measures, review 4 the pilot site, review 5 the
   Phase 4 measures at both sites, and review 6 receives the full benefits review.

## Assumptions

*ILLUSTRATIVE. Every value below is an assumption, not a measurement.*

| ID | Assumption | Value used | Used in | How it will be replaced by a measurement |
| --- | --- | --- | --- | --- |
| A1 | Share of quantity variances that are agreed shortfalls, cleared by recording them on the order at receipt | 80% | KPI-05 | Buyers classify a sample of 50 quantity variances in Phase 1 |
| A2 | Share of overcharges recovered once invoices beyond tolerance are held | 80% (low 50%, high 95%) | KPI-05; overcharges stopped | Credit notes against held invoices in the first three months of Phase 3 |
| A3 | Scrap value of offcut steel | £180 a tonne | Offcuts reused | The scrap merchant's statements |
| A4 | Yield gained by reusing heat-numbered offcuts | 2 points (low 1, high 4) | KPI-03; offcuts reused | Restated yield from recorded issues, over three months |
| A5 | Share of the over-90-day WIP value that is work already gone, waiting to be closed | 60% | KPI-07 | Supervisors review every works order over 90 days old in Phase 2 |
| A6 | Share of late deliveries with an information cause the programme removes | 25% | KPI-01 | Root causes of a sample of 50 late deliveries in Phase 1 |
| A7 | Fall in NCRs for a missing mill certificate once goods-in refuses untraceable steel | 75% (low 50%, high 90%) | KPI-09; NCRs avoided | Six months of the NCR log after the control starts |
| A8 | Share of missing receipts and missing invoices cleared within 30 days once worked daily | 75% | KPI-05 | Queue ageing in the first three months of Phase 3 |
| A9 | Uncosted NCRs cost, on average, the same as costed ones | The average of the costed NCRs | KPI-09, figures that will look worse | Costs entered on the NCR form in Phase 4 |

---

**ILLUSTRATIVE.** Baselines are measured on synthetic data. Targets and pound values are modelled. No
figure in this document describes a real business.

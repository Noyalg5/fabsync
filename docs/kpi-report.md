# KPI report

**All data behind these KPIs is synthetic.** It represents no real company, supplier, customer or job.

As at 2026-08-31. Definitions, formulas and sources are in `docs/data-dictionary.md`. Every figure is shown with its caveat.

## Scorecard

| KPI | Value | Target | Status | Also | Owner |
| --- | ---: | --- | --- | --- | --- |
| KPI-01 OTIF delivery performance | **16.7%** | >= 95% | off target |  | Production Controller |
| KPI-02 Labour variance | **7.4%** | within ±10% | on target |  | Production Controller |
| KPI-03 Material yield and offcut waste | **76.2%** | >= 85% | off target |  | Production Controller |
| KPI-04 Stock accuracy | **89.6%** | >= 95% | off target |  | Production Controller |
| KPI-05 Three-way match exception rate | **53.8%** | <= 5% | off target | Value at risk: £4,315,268 | Finance Manager |
| KPI-06 Material traceability coverage | **68.7%** | >= 100% | off target |  | Quality Manager |
| KPI-07 WIP value and ageing | **£714,137** | no target | for information | Share of WIP over 90 days: 54.9% | Finance Manager |
| KPI-08 Capacity utilisation | **86.1%** | 75% to 95% | on target |  | Production Controller |
| KPI-09 NCR rate and cost of quality | **1.3%** | <= 2% | on target | NCRs per 100 tonnes despatched: 7.16 | Quality Manager |

## KPI-01 OTIF delivery performance

**16.7%**. Target >= 95%: off target.

The share of deliveries that reached the customer by the promised date with the full tonnage on the lorry.

> **Caveat.** Measures despatch from our yard, not arrival on site, so haulage delays are invisible. Delivery notes do not name the works order, so "in full" relies on matching each note to the works order on the same job that finished just before it, which can pair wrongly when two finish on the same day. Delivery notes with no promised date (about 4%) are left out, and so are notes quarantined as unreadable, so the true figure could be worse.

By site:

| Site code | Deliveries | Measured | On time % | In full % | Otif % |
| --- | --- | --- | --- | --- | --- |
| TEE | 339 | 326 | 15.3 | 92.3 | 15 |
| WKF | 378 | 361 | 18.8 | 93.4 | 18.3 |

Five customers with the lowest OTIF (five or more deliveries measured):

| Customer name | Deliveries | Measured | On time % | In full % | Otif % | Avg days late when late |
| --- | --- | --- | --- | --- | --- | --- |
| Ridley Structures | 14 | 14 | 0 | 78.6 | 0 | 9.5 |
| Westgate Rail Ltd | 13 | 13 | 0 | 100 | 0 | 10.6 |
| Kingsmead Retail Developments | 13 | 13 | 7.7 | 100 | 7.7 | 9.6 |
| Caledonian Rail Engineering Ltd | 27 | 25 | 8 | 88 | 8 | 12.7 |
| Skyreach Networks Ltd | 22 | 22 | 9.1 | 90.9 | 9.1 | 10.3 |

## KPI-02 Labour variance

**7.4%**. Target within ±10%: on target.

How many more (or fewer) hours the shop floor actually spent on completed work than the plan allowed.

> **Caveat.** Only as good as the booking sheets. Hours booked to a wrong or non-existent works order are left out (the job cost reconciliation reports how many), and unreadable or duplicate bookings are quarantined, so actual hours are understated. Planned hours are the estimator's figure, so a large variance can mean a poor estimate rather than poor performance. Works orders still in progress are excluded from the headline.

Five jobs with the largest variance on completed works:

| Job no | Works orders | Complete works orders | Planned hours | Actual hours | Variance hours | Variance % |
| --- | --- | --- | --- | --- | --- | --- |
| J-24-0869 | 4 | 4 | 174.2 | 238.23 | 64.03 | 36.8 |
| J-25-0123 | 2 | 2 | 218.4 | 296.06 | 77.66 | 35.6 |
| J-24-0854 | 5 | 5 | 264.2 | 357.72 | 93.52 | 35.4 |
| J-25-0124 | 3 | 3 | 179.3 | 239.62 | 60.32 | 33.6 |
| J-25-0145 | 7 | 6 | 328.2 | 438.38 | 110.19 | 33.6 |

## KPI-03 Material yield and offcut waste

**76.2%**. Target >= 85%: off target.

Of the steel bars we cut, the share that ends up in finished parts, and the share left over as offcut.

> **Caveat.** A theoretical yield. It assumes each BOM line is cut from its own bars, so real nesting across lines would do better, and it assumes offcuts are scrapped, although some are reused. It does not cover plate, because there is no profile nesting data. The received-to-issued ratio mixes waste with stock building up in the yard, so it is not a waste figure on its own.

By section type:

| Section type | Cut yield % | Offcut waste % | Issued kg | Received kg | Received to issued |
| --- | --- | --- | --- | --- | --- |
| L | 74.7 | 25.3 | 222,820 | 209,652 | 0.94 |
| FLAT | 75.2 | 24.8 | 62,184 | 52,554 | 0.85 |
| CHS | 75.7 | 24.3 | 284,087 | 298,140 | 1.05 |
| PFC | 75.7 | 24.3 | 303,771 | 309,446 | 1.02 |
| SHS | 75.8 | 24.2 | 204,812 | 207,690 | 1.01 |
| RHS | 76.2 | 23.8 | 431,067 | 428,368 | 0.99 |
| UB | 76.5 | 23.5 | 1,531,456 | 1,599,577 | 1.04 |
| UC | 76.6 | 23.4 | 859,184 | 920,049 | 1.07 |
| PLATE |  |  | 257,841 | 259,558 | 1.01 |

## KPI-04 Stock accuracy

**89.6%**. Target >= 95%: off target.

The share of stock lines where what we counted in the yard matches what the system says we have.

> **Caveat.** Counts every line equally, so a miscounted box of washers weighs the same as a missing rack of beams; the value error beside it shows which matters. It only covers lines that have been counted, and about a third were last counted more than 90 days ago. A count that agrees with a wrong book figure would pass.

By site:

| Site code | Counted lines | Accurate lines | Accuracy % | Meets target | Value error |
| --- | --- | --- | --- | --- | --- |
| TEE | 58 | 51 | 87.9 | no | 5,966.49 |
| WKF | 48 | 44 | 91.7 | no | 9,331.2 |
| All sites | 106 | 95 | 89.6 | no | 15,297.69 |

## KPI-05 Three-way match exception rate

**53.8%**. Target <= 5%: off target. Value at risk: £4,315,268.

The share of steel purchase orders that do not match cleanly across order, delivery and invoice, and the money tied up in all purchasing exceptions.

> **Caveat.** Value at risk is not money lost. Most of it is subcontract and service spend with no purchase order, which is a control weakness but may be correctly priced; that spend is in the value but not the rate, because it has no order to match against. A 2% quantity tolerance flags every short delivery, even where the shortfall was agreed with the stockholder. Corvus orders carry one line each, so a partial delivery against a multi-line order would not show here. Orders not yet due for receipt or invoice are excluded until they are.

Value at risk by category:

| Category | Lines | Value at risk | Over 90 days |
| --- | --- | --- | --- |
| invoice with no PO | 726 | 3,407,849.81 | 575 |
| missing invoice | 66 | 428,173.13 | 62 |
| missing GRN | 82 | 304,399.47 | 64 |
| quantity variance | 377 | 115,552.56 | 333 |
| price variance | 48 | 59,292.62 | 42 |
| matched | 493 | 0 | 0 |

## KPI-06 Material traceability coverage

**68.7%**. Target >= 100%: off target.

The share of steel used on our works orders that we can trace back to the mill certificate and cast it came from.

> **Caveat.** Corvus records no material issues, so which delivery went into which works order is inferred by allocating deliveries first-in first-out. A real audit would need the cutting lists. A chain that shows as complete here has the right references on file; that does not prove the certificates were checked or the steel physically marked. The target is 100%, because EN 1090 allows no gaps.

By site:

| Site code | Coverage % |
| --- | --- |
| TEE | 68.6 |
| WKF | 68.8 |

## KPI-07 WIP value and ageing

**£714,137**. No target is set; for information. Share of WIP over 90 days: 54.9%.

The value of work started on the shop floor but not yet delivered, and how long it has been sitting there.

> **Caveat.** Material is counted in full from the start of the works order, because Corvus does not record when steel is issued, so early-stage WIP is overstated. Labour is at a standard rate with no overhead. Works orders left open after the work has gone count as WIP until someone closes them, and many are, so the 90+ bucket is partly an admin backlog rather than stuck work.

Ageing:

| Age bucket | Works orders | Material value | Labour value | Wip value |
| --- | --- | --- | --- | --- |
| 0-30 days | 18 | 81,307.94 | 49,861.46 | 131,169.4 |
| 31-60 days | 18 | 100,717.39 | 61,725.98 | 162,443.36 |
| 61-90 days | 4 | 17,301.8 | 11,115 | 28,416.8 |
| 90+ days | 65 | 273,031.11 | 119,076.46 | 392,107.56 |

## KPI-08 Capacity utilisation

**86.1%**. Target 75% to 95%: on target.

The share of the hours our people were available in a week that were booked to jobs.

> **Caveat.** Uses the supervisors' own weekly totals, which drift a few per cent from the individual booking sheets (the cross-check column shows by how much). High utilisation is not the same as productive utilisation, because hours spent on rework count as booked. Weeks with no booked figure are left out.

By site:

| Site code | Weeks | Weeks reported | Available hours | Booked hours | Utilisation % | Weeks over 100 % |
| --- | --- | --- | --- | --- | --- | --- |
| TEE | 106 | 105 | 41,477 | 36,296 | 87.5 | 39 |
| WKF | 106 | 99 | 41,958 | 35,548 | 84.7 | 37 |

## KPI-09 NCR rate and cost of quality

**1.3%**. Target <= 2%: on target. NCRs per 100 tonnes despatched: 7.16.

How often something we make goes wrong, and what putting it right costs as a share of what we sell.

> **Caveat.** Covers only failure costs recorded on NCRs, not prevention or inspection, so the true cost of quality is higher. About a fifth of NCRs have no cost entered and count as nil. Turnover follows invoice timing, including applications for payment, so a single month's percentage can swing. Problems found and fixed without an NCR are invisible.

By NCR category:

| Category | Ncrs | Ncrs costed | Ncr cost | Open ncrs |
| --- | --- | --- | --- | --- |
| Weld defect | 50 | 42 | 46,417.25 | 20 |
| Dimensional error | 48 | 35 | 39,459.91 | 11 |
| Missing mill certificate | 24 | 21 | 31,925.6 | 5 |
| Wrong drawing revision | 57 | 46 | 28,820.12 | 16 |
| Missing fittings | 30 | 26 | 25,294.11 | 7 |
| Galvanising defect | 20 | 17 | 23,793.71 | 8 |
| Damage in transit | 17 | 14 | 19,509.33 | 6 |

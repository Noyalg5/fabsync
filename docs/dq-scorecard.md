# Data quality scorecard

**All data assessed here is synthetic.** It represents no real company, supplier, customer or job.

Produced by `make quality` from the 34 rules declared in `config/dq_rules.yaml`, evaluated as at 2026-08-31. Every run is kept in `governance.dq_results` so the index can be trended (`governance.v_dq_trend`). Failing records are in `governance.v_dq_exception_queue`.

## Headline data quality index: 92.1 / 100

7 of 34 rules meet their threshold. 4 critical rules are breached. 12,256 failing records are in the exception queue.

### How the index is calculated

For each rule, the pass rate is the share of records checked that pass. The rule's score is its pass
rate divided by its threshold, capped at 1. A rule that meets its threshold scores 1; one that falls short
scores in proportion. The index is the severity-weighted average of rule scores, times 100:

```
score_r = min(1, pass_rate_r / threshold_r)
DQI     = 100 x sum(weight_r x score_r) / sum(weight_r)
```

Severity weights: critical 8, high 4, medium 2, low 1. Each step up doubles the
weight, so one critical rule counts as much as eight low ones. Every scorecard line below uses the same
formula over its own rules. Rules that error are excluded and reported separately.

## By owning role

This is the view that makes governance actionable: each role owns its rules, its exceptions and
its score.

| Owner | Index | Rules met | Critical breaches | Records checked | Records failing |
| --- | ---: | ---: | ---: | ---: | ---: |
| Purchasing Manager | **88.0** | 2 of 8 | 1 | 20,627 | 1,618 |
| Quality Manager | **90.1** | 1 of 4 | 2 | 2,442 | 264 |
| Finance Manager | **91.7** | 0 of 6 | 1 | 2,819 | 207 |
| Production Controller | **96.1** | 4 of 16 |  | 123,735 | 10,167 |

- **Finance Manager:** 207 open exceptions. Most severe first: DQ-14 Invoice within tolerance of order value (53); DQ-13 Goods receipts invoiced within 30 days (66); DQ-11 Sales invoices raised against a Corvus job (32); DQ-16 Labour cost reconciles to booked hours (30).
- **Production Controller:** 10,167 open exceptions. Most severe first: DQ-23 Time bookings against a real works order (46); DQ-29 Promised date on every delivery note (30); DQ-20 Shop-floor entries readable (24); DQ-28 Operation named on every booking (379).
- **Purchasing Manager:** 1,618 open exceptions. Most severe first: DQ-03 Steel grade stated on every order and receipt (246); DQ-12 Overdue purchase orders have a goods receipt (82); DQ-07 One Corvus supplier code per supplier (8); DQ-09 Every Corvus supplier linked to a finance account (3).
- **Quality Manager:** 264 open exceptions. Most severe first: DQ-02 Mill certificate on every goods receipt (106); DQ-01 Heat number on every goods receipt (103); DQ-34 NCRs closed within 60 days (55).

## By source system

| System of record | Index | Rules met | Critical breaches | Records checked | Records failing |
| --- | ---: | ---: | ---: | ---: | ---: |
| Corvus MRP | **91.1** | 6 of 17 | 3 | 52,916 | 1,950 |
| Finance system | **91.7** | 0 of 6 | 1 | 2,819 | 207 |
| Shop-floor spreadsheets | **94.8** | 1 of 11 |  | 93,888 | 10,099 |

## By quality dimension

| Dimension | Index | Rules met | Critical breaches | Records checked | Records failing |
| --- | ---: | ---: | ---: | ---: | ---: |
| timeliness | **82.7** | 0 of 3 |  | 1,107 | 167 |
| uniqueness | **85.6** | 0 of 4 |  | 26,746 | 179 |
| consistency | **90.9** | 2 of 10 |  | 41,539 | 10,515 |
| completeness | **92.9** | 1 of 10 | 3 | 33,489 | 1,307 |
| accuracy | **93.7** | 0 of 2 | 1 | 1,024 | 64 |
| validity | **100.0** | 4 of 5 |  | 45,718 | 24 |

## Rules breaching their threshold

| Rule | Severity | Owner | Pass rate | Threshold | Failing | Consequence |
| --- | --- | --- | ---: | ---: | ---: | --- |
| DQ-03 Steel grade stated on every order and receipt | critical | Purchasing Manager | 88.2% | 100.0% | 246 | Where a section is stocked in more than one grade, an order without a grade may bring in S275 steel for an S355 design. That is a structural safety risk, and stock cannot be allocated to jobs with confidence. |
| DQ-02 Mill certificate on every goods receipt | critical | Quality Manager | 89.3% | 100.0% | 106 | Without the certificate there is no evidence of chemistry or strength. The steel cannot be used on EXC2 or higher work, and an auditor will raise a major finding. |
| DQ-01 Heat number on every goods receipt | critical | Quality Manager | 89.6% | 100.0% | 103 | Steel cannot be traced to its mill certificate. Under EN 1090-2 factory production control that is a nonconformity, and the finished steelwork cannot be UKCA or CE marked until it is resolved. |
| DQ-14 Invoice within tolerance of order value | critical | Finance Manager | 94.2% | 100.0% | 53 | Overcharges are paid without challenge. Across a year of steel buying that is a direct margin loss. |
| DQ-07 One Corvus supplier code per supplier | high | Purchasing Manager | 66.7% | 100.0% | 8 | Spend with one stockholder is split across codes. Volume rebates are missed, supplier performance looks better or worse than it is, and a stopped supplier can still be ordered from under its other code. |
| DQ-34 NCRs closed within 60 days | high | Quality Manager | 74.8% | 90.0% | 55 | Open NCRs mean suspect steelwork may already be on site. They are also an EN 1090 audit finding and a sign that root causes are not being fixed. |
| DQ-16 Labour cost reconciles to booked hours | high | Finance Manager | 80.0% | 95.0% | 30 | Job margins are wrong. A job looks profitable in finance while the shop floor spent far more hours on it, or the reverse, so pricing and estimating learn the wrong lessons. |
| DQ-09 Every Corvus supplier linked to a finance account | high | Purchasing Manager | 87.5% | 100.0% | 3 | Orders and payments cannot be tied together, so the three-way match fails for that supplier and spend analysis is incomplete. |
| DQ-10 Finance job codes exist in Corvus | high | Finance Manager | 88.2% | 100.0% | 20 | Costs and revenue on these jobs appear in finance with no production record, so job margin cannot be reported and WIP may be misstated. |
| DQ-08 One finance account per supplier | high | Finance Manager | 90.5% | 100.0% | 6 | Invoices can be paid twice across two accounts, statements do not reconcile, and credit notes land on the wrong account. |
| DQ-12 Overdue purchase orders have a goods receipt | high | Purchasing Manager | 92.3% | 97.0% | 82 | Either steel has not arrived and fabrication will stall, or it has arrived and was never booked in, so stock is understated and the invoice will fail the three-way match. |
| DQ-13 Goods receipts invoiced within 30 days | high | Finance Manager | 93.1% | 97.0% | 66 | Received-not-invoiced liabilities are missing from the accounts, month-end accruals are understated, and a late invoice may bypass the match. |
| DQ-11 Sales invoices raised against a Corvus job | high | Finance Manager | 94.3% | 100.0% | 32 | Revenue cannot be matched to the work that earned it. Margin by contract is wrong and retention releases cannot be tracked. |
| DQ-29 Promised date on every delivery note | high | Production Controller | 95.8% | 100.0% | 30 | On-time-in-full (OTIF) cannot be measured for that despatch, which is the headline customer measure. |
| DQ-23 Time bookings against a real works order | high | Production Controller | 99.6% | 100.0% | 46 | Hours on a works order Corvus has never heard of are charged to no job. Labour is lost from job costing and the real job looks cheaper than it was. |
| DQ-20 Shop-floor entries readable | high | Production Controller | 99.8% | 99.9% | 24 | Unreadable rows are quarantined and left out of every report, so hours, despatches and NCR costs are understated until someone fixes them. |
| DQ-18 Stock counted within 90 days | medium | Production Controller | 62.3% | 90.0% | 40 | Old counts hide losses and unreturned offcuts. The longer the gap, the bigger the surprise at year end. |
| DQ-05 One unit of measure per material | medium | Purchasing Manager | 70.2% | 100.0% | 14 | A section bought in kilograms, stocked in 12 m bars and issued in metres cannot be reconciled. Stock value, material usage variance and scrap rates are all misstated. |
| DQ-04 Materials recorded under their canonical code | medium | Purchasing Manager | 84.4% | 98.0% | 1,265 | The same beam shows as several stock items. Stock looks short when it is not, buyers reorder what is already in the yard, and tonnage reports split one material into many lines. |
| DQ-17 Stock count agrees with the book | medium | Production Controller | 89.6% | 98.0% | 11 | Planning allocates steel that is not there, or buys steel that is. Stock valuation at year end is misstated. |
| DQ-33 Works orders closed off promptly | medium | Production Controller | 90.8% | 95.0% | 72 | Open works orders keep material and labour in WIP long after the work has gone, which overstates WIP and hides overruns. |
| DQ-28 Operation named on every booking | medium | Production Controller | 97.0% | 99.0% | 379 | Hours cannot be compared with the routing, so bottlenecks at welding or blasting are invisible. |
| DQ-30 Tonnage on every delivery note | medium | Production Controller | 97.4% | 99.0% | 19 | Tonnage despatched, the headline throughput figure, is understated, and haulage cannot be checked against the load. |
| DQ-27 Operator named on every booking | medium | Production Controller | 97.8% | 99.0% | 276 | Welding cannot be tied to a qualified welder for EN ISO 9606 records, and productivity by operator cannot be measured. |
| DQ-19 No duplicate rows in shop-floor records | medium | Production Controller | 98.8% | 99.5% | 162 | Duplicated bookings double-count hours on the job. Duplicated delivery notes overstate tonnage despatched. |
| DQ-21 Booking numbers unique | medium | Production Controller | 100.0% | 100.0% | 3 | When two different bookings share a number, only the first is kept, so the hours on the edited copy are lost. |
| DQ-22 Shop-floor dates in the UK house format | low | Production Controller | 33.6% | 95.0% | 9,105 | A date such as 03/04/2025 is read differently by different people and tools. Mixed formats cause silent month and day swaps when data is copied between sheets. |

## Seeded defects detected

Each defect seeded into the synthetic sources (data/raw/DEFECTS.md) and the rules that catch it.

| Defect | Rules | Failing records |
| ---: | --- | ---: |
| 1 | DQ-03, DQ-04 | 1,511 |
| 2 | DQ-07, DQ-08, DQ-09 | 17 |
| 3 | DQ-10, DQ-11 | 52 |
| 4 | DQ-05, DQ-06 | 14 |
| 5 | DQ-12, DQ-13, DQ-14 | 201 |
| 6 | DQ-01, DQ-02 | 209 |
| 7 | DQ-16 | 30 |
| 8 | DQ-17 | 11 |
| 9 | DQ-19, DQ-20, DQ-21, DQ-22 | 9,294 |
| 10 | DQ-23 | 46 |

## All rules

| Rule | Dimension | Severity | System | Owner | Checked | Failing | Pass rate | Threshold | Met |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | :---: |
| DQ-01 Heat number on every goods receipt | completeness | critical | Corvus MRP | Quality Manager | 989 | 103 | 89.6% | 100.0% | **no** |
| DQ-02 Mill certificate on every goods receipt | completeness | critical | Corvus MRP | Quality Manager | 989 | 106 | 89.3% | 100.0% | **no** |
| DQ-03 Steel grade stated on every order and receipt | completeness | critical | Corvus MRP | Purchasing Manager | 2,093 | 246 | 88.2% | 100.0% | **no** |
| DQ-04 Materials recorded under their canonical code | consistency | medium | Corvus MRP | Purchasing Manager | 8,132 | 1,265 | 84.4% | 98.0% | **no** |
| DQ-05 One unit of measure per material | consistency | medium | Corvus MRP | Purchasing Manager | 47 | 14 | 70.2% | 100.0% | **no** |
| DQ-06 Unit of measure valid for the material | validity | high | Corvus MRP | Purchasing Manager | 8,132 | 0 | 100.0% | 100.0% | yes |
| DQ-07 One Corvus supplier code per supplier | uniqueness | high | Corvus MRP | Purchasing Manager | 24 | 8 | 66.7% | 100.0% | **no** |
| DQ-08 One finance account per supplier | uniqueness | high | Finance system | Finance Manager | 63 | 6 | 90.5% | 100.0% | **no** |
| DQ-09 Every Corvus supplier linked to a finance account | consistency | high | Corvus MRP | Purchasing Manager | 24 | 3 | 87.5% | 100.0% | **no** |
| DQ-10 Finance job codes exist in Corvus | consistency | high | Finance system | Finance Manager | 170 | 20 | 88.2% | 100.0% | **no** |
| DQ-11 Sales invoices raised against a Corvus job | consistency | high | Finance system | Finance Manager | 559 | 32 | 94.3% | 100.0% | **no** |
| DQ-12 Overdue purchase orders have a goods receipt | completeness | high | Corvus MRP | Purchasing Manager | 1,071 | 82 | 92.3% | 97.0% | **no** |
| DQ-13 Goods receipts invoiced within 30 days | completeness | high | Finance system | Finance Manager | 959 | 66 | 93.1% | 97.0% | **no** |
| DQ-14 Invoice within tolerance of order value | accuracy | critical | Finance system | Finance Manager | 918 | 53 | 94.2% | 100.0% | **no** |
| DQ-15 Purchase dates in sequence | validity | high | Corvus MRP | Purchasing Manager | 1,104 | 0 | 100.0% | 100.0% | yes |
| DQ-16 Labour cost reconciles to booked hours | consistency | high | Finance system | Finance Manager | 150 | 30 | 80.0% | 95.0% | **no** |
| DQ-17 Stock count agrees with the book | accuracy | medium | Corvus MRP | Production Controller | 106 | 11 | 89.6% | 98.0% | **no** |
| DQ-18 Stock counted within 90 days | timeliness | medium | Corvus MRP | Production Controller | 106 | 40 | 62.3% | 90.0% | **no** |
| DQ-19 No duplicate rows in shop-floor records | uniqueness | medium | Shop-floor spreadsheets | Production Controller | 13,927 | 162 | 98.8% | 99.5% | **no** |
| DQ-20 Shop-floor entries readable | validity | high | Shop-floor spreadsheets | Production Controller | 13,927 | 24 | 99.8% | 99.9% | **no** |
| DQ-21 Booking numbers unique | uniqueness | medium | Shop-floor spreadsheets | Production Controller | 12,732 | 3 | 100.0% | 100.0% | **no** |
| DQ-22 Shop-floor dates in the UK house format | consistency | low | Shop-floor spreadsheets | Production Controller | 13,715 | 9,105 | 33.6% | 95.0% | **no** |
| DQ-23 Time bookings against a real works order | consistency | high | Shop-floor spreadsheets | Production Controller | 12,563 | 46 | 99.6% | 100.0% | **no** |
| DQ-24 NCRs raised against a real works order | consistency | high | Shop-floor spreadsheets | Quality Manager | 246 | 0 | 100.0% | 100.0% | yes |
| DQ-25 BOM lines belong to a works order | consistency | critical | Corvus MRP | Production Controller | 5,933 | 0 | 100.0% | 100.0% | yes |
| DQ-26 Started works orders have a bill of material | completeness | high | Corvus MRP | Production Controller | 828 | 0 | 100.0% | 100.0% | yes |
| DQ-27 Operator named on every booking | completeness | medium | Shop-floor spreadsheets | Production Controller | 12,563 | 276 | 97.8% | 99.0% | **no** |
| DQ-28 Operation named on every booking | completeness | medium | Shop-floor spreadsheets | Production Controller | 12,563 | 379 | 97.0% | 99.0% | **no** |
| DQ-29 Promised date on every delivery note | completeness | high | Shop-floor spreadsheets | Production Controller | 717 | 30 | 95.8% | 100.0% | **no** |
| DQ-30 Tonnage on every delivery note | completeness | medium | Shop-floor spreadsheets | Production Controller | 717 | 19 | 97.4% | 99.0% | **no** |
| DQ-31 Works order and NCR dates in sequence | validity | medium | Corvus MRP | Production Controller | 1,106 | 0 | 100.0% | 100.0% | yes |
| DQ-32 Quantities and hours positive and plausible | validity | high | Corvus MRP | Production Controller | 21,449 | 0 | 100.0% | 100.0% | yes |
| DQ-33 Works orders closed off promptly | timeliness | medium | Corvus MRP | Production Controller | 783 | 72 | 90.8% | 95.0% | **no** |
| DQ-34 NCRs closed within 60 days | timeliness | high | Shop-floor spreadsheets | Quality Manager | 218 | 55 | 74.8% | 90.0% | **no** |

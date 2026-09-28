# Data quality scorecard

**All data assessed here is synthetic.** It represents no real company, supplier, customer or job.

Produced by `make quality` from the 41 rules declared in `config/dq_rules.yaml`, evaluated as at 2026-08-31. Every run is kept in `governance.dq_results` so the index can be trended (`governance.v_dq_trend`). Failing records are in `governance.v_dq_exception_queue`.

## Headline data quality index: 92.1 / 100

7 of 41 rules meet their threshold. 5 critical rules are breached. 13,172 failing records are in the exception queue.

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
| Purchasing Manager | **87.7** | 2 of 9 | 1 | 21,731 | 1,625 |
| Quality Manager | **89.8** | 1 of 6 | 3 | 3,350 | 378 |
| Finance Manager | **92.2** | 0 of 7 | 1 | 5,158 | 219 |
| Production Controller | **96.4** | 4 of 19 |  | 139,678 | 10,950 |

- **Finance Manager:** 219 open exceptions. Most severe first: DQ-14 Invoice within tolerance of order value (53); DQ-13 Goods receipts invoiced within 30 days (66); DQ-11 Sales invoices raised against a Corvus job (32); DQ-16 Labour cost reconciles to booked hours (30).
- **Production Controller:** 10,950 open exceptions. Most severe first: DQ-23 Time bookings against a real works order (46); DQ-29 Promised date on every delivery note (30); DQ-20 Shop-floor entries readable (24); DQ-28 Operation named on every booking (379).
- **Purchasing Manager:** 1,625 open exceptions. Most severe first: DQ-03 Steel grade stated on every order and receipt (246); DQ-12 Overdue purchase orders have a goods receipt (82); DQ-07 One Corvus supplier code per supplier (10); DQ-09 Every Corvus supplier linked to a finance account (3).
- **Quality Manager:** 378 open exceptions. Most severe first: DQ-02 Mill certificate on every goods receipt (106); DQ-01 Heat number on every goods receipt (103); DQ-41 3.1 inspection document on every S355 receipt (69); DQ-34 NCRs closed within 60 days (55).

## By source system

| System of record | Index | Rules met | Critical breaches | Records checked | Records failing |
| --- | ---: | ---: | ---: | ---: | ---: |
| Corvus MRP | **91.0** | 6 of 20 | 4 | 55,541 | 2,027 |
| Finance system | **92.2** | 0 of 7 | 1 | 5,158 | 219 |
| Shop-floor spreadsheets | **94.6** | 1 of 14 |  | 109,218 | 10,926 |

## By quality dimension

| Dimension | Index | Rules met | Critical breaches | Records checked | Records failing |
| --- | ---: | ---: | ---: | ---: | ---: |
| timeliness | **82.8** | 0 of 3 |  | 1,106 | 166 |
| uniqueness | **82.8** | 0 of 4 |  | 26,746 | 181 |
| consistency | **90.9** | 2 of 10 |  | 42,626 | 11,260 |
| completeness | **92.3** | 1 of 13 | 4 | 35,114 | 1,456 |
| accuracy | **93.7** | 0 of 2 | 1 | 1,024 | 64 |
| validity | **99.9** | 4 of 9 |  | 63,301 | 45 |

## Rules breaching their threshold

| Rule | Severity | Owner | Pass rate | Threshold | Failing | Consequence |
| --- | --- | --- | ---: | ---: | ---: | --- |
| DQ-03 Steel grade stated on every order and receipt | critical | Purchasing Manager | 88.2% | 100.0% | 246 | Where a section is stocked in more than one grade, an order without a grade may bring in S275 steel for an S355 design. That is a structural safety risk, and stock cannot be allocated to jobs with confidence. |
| DQ-02 Mill certificate on every goods receipt | critical | Quality Manager | 89.3% | 100.0% | 106 | Without the certificate there is no evidence of chemistry or strength. EN 1090-2 requires a 3.1 inspection document for S355 at every execution class (DQ-41), and full traceability to the certificate on EXC3 and EXC4 work. |
| DQ-41 3.1 inspection document on every S355 receipt | critical | Quality Manager | 89.6% | 100.0% | 69 | EN 1090-2 requires a 3.1 inspection document for S355 at every execution class, EXC2 included. S355 from this delivery cannot be used on any certified structure, and any already despatched is an EN 1090 compliance exposure. |
| DQ-01 Heat number on every goods receipt | critical | Quality Manager | 89.6% | 100.0% | 103 | Steel cannot be traced to its mill certificate. EN 1090-2 requires that trace, from receipt to hand over, on EXC3 and EXC4 work, so steel from this delivery cannot go into an EXC3 structure until it is resolved; on EXC2 work the gap is a failure of good practice rather than of the standard. |
| DQ-14 Invoice within tolerance of order value | critical | Finance Manager | 94.2% | 100.0% | 53 | Overcharges are paid without challenge. Across a year of steel buying that is a direct margin loss. |
| DQ-07 One Corvus supplier code per supplier | high | Purchasing Manager | 58.3% | 100.0% | 10 | Spend with one stockholder is split across codes. Volume rebates are missed, supplier performance looks better or worse than it is, and a stopped supplier can still be ordered from under its other code. |
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
| DQ-39 Cost entered on every NCR | medium | Quality Manager | 81.7% | 95.0% | 45 | An NCR with no cost counts as nil, so the cost of quality is understated and the defects that cost most cannot be ranked. |
| DQ-04 Materials recorded under their canonical code | medium | Purchasing Manager | 84.4% | 98.0% | 1,265 | The same beam shows as several stock items. Stock looks short when it is not, buyers reorder what is already in the yard, and tonnage reports split one material into many lines. |
| DQ-17 Stock count agrees with the book | medium | Production Controller | 89.6% | 98.0% | 11 | Planning allocates steel that is not there, or buys steel that is. Stock valuation at year end is misstated. |
| DQ-33 Works orders closed off promptly | medium | Production Controller | 90.9% | 95.0% | 71 | Open works orders keep material and labour in WIP long after the work has gone, which overstates WIP and hides overruns. |
| DQ-28 Operation named on every booking | medium | Production Controller | 97.0% | 99.0% | 379 | Hours cannot be compared with the routing, so bottlenecks at welding or blasting are invisible. |
| DQ-30 Tonnage on every delivery note | medium | Production Controller | 97.4% | 99.0% | 19 | Tonnage despatched, the headline throughput figure, is understated, and haulage cannot be checked against the load. |
| DQ-27 Operator named on every booking | medium | Production Controller | 97.8% | 99.0% | 276 | Welding cannot be tied to a qualified welder for EN ISO 9606 records, and productivity by operator cannot be measured. |
| DQ-19 No duplicate rows in shop-floor records | medium | Production Controller | 98.8% | 99.5% | 162 | Duplicated bookings double-count hours on the job. Duplicated delivery notes overstate tonnage despatched. |
| DQ-37 Invoices not dated after the extract | medium | Finance Manager | 99.5% | 100.0% | 12 | A future-dated invoice is posted to a period that has not happened, so the month's costs, accruals and turnover are wrong and the invoice may be paid early. |
| DQ-35 Purchase orders not dated after the extract | medium | Purchasing Manager | 99.5% | 100.0% | 5 | An order dated in the future is a keying error. It lands in the wrong month, so spend, commitments and the three-way match are reported in the wrong period. |
| DQ-36 Works orders not finished after the extract | medium | Production Controller | 99.8% | 100.0% | 2 | Work booked as finished before it is finished drops out of WIP and appears ready to despatch, so delivery promises and job margins are wrong. |
| DQ-21 Booking numbers unique | medium | Production Controller | 100.0% | 100.0% | 3 | When two different bookings share a number, only the first is kept, so the hours on the edited copy are lost. |
| DQ-38 Shop-floor records not dated after the extract | medium | Production Controller | 100.0% | 100.0% | 2 | Hours booked or steel despatched on a date that has not happened distort labour, capacity and on-time delivery for the period. |
| DQ-22 Shop-floor dates in the UK house format | low | Production Controller | 33.5% | 95.0% | 9,850 | A date such as 03/04/2025 is read differently by different people and tools. Mixed formats cause silent month and day swaps when data is copied between sheets. |
| DQ-40 Vehicle recorded on every delivery note | low | Production Controller | 95.1% | 99.0% | 35 | The haulier's charges cannot be checked against the loads, and a load cannot be traced to its vehicle if it arrives damaged or incomplete. |

## Seeded defects detected

Each defect seeded into the synthetic sources (data/raw/DEFECTS.md) and the rules that catch it.

| Defect | Rules | Failing records |
| ---: | --- | ---: |
| 1 | DQ-03, DQ-04 | 1,511 |
| 2 | DQ-07, DQ-08, DQ-09 | 19 |
| 3 | DQ-10, DQ-11 | 52 |
| 4 | DQ-05 | 14 |
| 5 | DQ-12, DQ-13, DQ-14 | 201 |
| 6 | DQ-01, DQ-02, DQ-41 | 278 |
| 7 | DQ-16 | 30 |
| 8 | DQ-17 | 11 |
| 9 | DQ-19, DQ-20, DQ-21, DQ-22, DQ-27, DQ-28, DQ-29, DQ-30, DQ-39, DQ-40 | 10,823 |
| 10 | DQ-23 | 46 |
| 11 | DQ-18, DQ-33, DQ-34 | 166 |
| 13 | DQ-35, DQ-36, DQ-37, DQ-38 | 21 |

## All rules

| Rule | Dimension | Severity | System | Owner | Checked | Failing | Pass rate | Threshold | Met |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | :---: |
| DQ-01 Heat number on every goods receipt | completeness | critical | Corvus MRP | Quality Manager | 989 | 103 | 89.6% | 100.0% | **no** |
| DQ-02 Mill certificate on every goods receipt | completeness | critical | Corvus MRP | Quality Manager | 989 | 106 | 89.3% | 100.0% | **no** |
| DQ-41 3.1 inspection document on every S355 receipt | completeness | critical | Corvus MRP | Quality Manager | 662 | 69 | 89.6% | 100.0% | **no** |
| DQ-03 Steel grade stated on every order and receipt | completeness | critical | Corvus MRP | Purchasing Manager | 2,093 | 246 | 88.2% | 100.0% | **no** |
| DQ-04 Materials recorded under their canonical code | consistency | medium | Corvus MRP | Purchasing Manager | 8,132 | 1,265 | 84.4% | 98.0% | **no** |
| DQ-05 One unit of measure per material | consistency | medium | Corvus MRP | Purchasing Manager | 47 | 14 | 70.2% | 100.0% | **no** |
| DQ-06 Unit of measure valid for the material | validity | high | Corvus MRP | Purchasing Manager | 8,132 | 0 | 100.0% | 100.0% | yes |
| DQ-07 One Corvus supplier code per supplier | uniqueness | high | Corvus MRP | Purchasing Manager | 24 | 10 | 58.3% | 100.0% | **no** |
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
| DQ-22 Shop-floor dates in the UK house format | consistency | low | Shop-floor spreadsheets | Production Controller | 14,802 | 9,850 | 33.5% | 95.0% | **no** |
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
| DQ-33 Works orders closed off promptly | timeliness | medium | Corvus MRP | Production Controller | 782 | 71 | 90.9% | 95.0% | **no** |
| DQ-34 NCRs closed within 60 days | timeliness | high | Shop-floor spreadsheets | Quality Manager | 218 | 55 | 74.8% | 90.0% | **no** |
| DQ-35 Purchase orders not dated after the extract | validity | medium | Corvus MRP | Purchasing Manager | 1,104 | 5 | 99.5% | 100.0% | **no** |
| DQ-36 Works orders not finished after the extract | validity | medium | Corvus MRP | Production Controller | 860 | 2 | 99.8% | 100.0% | **no** |
| DQ-37 Invoices not dated after the extract | validity | medium | Finance system | Finance Manager | 2,339 | 12 | 99.5% | 100.0% | **no** |
| DQ-38 Shop-floor records not dated after the extract | validity | medium | Shop-floor spreadsheets | Production Controller | 13,280 | 2 | 100.0% | 100.0% | **no** |
| DQ-39 Cost entered on every NCR | completeness | medium | Shop-floor spreadsheets | Quality Manager | 246 | 45 | 81.7% | 95.0% | **no** |
| DQ-40 Vehicle recorded on every delivery note | completeness | low | Shop-floor spreadsheets | Production Controller | 717 | 35 | 95.1% | 99.0% | **no** |

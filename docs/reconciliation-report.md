# Reconciliation report

**All data reconciled here is synthetic.** It represents no real company, supplier, customer or job.

Produced by `make reconcile` as at 2026-08-31. Every figure below is stored in `recon.headline`
with the SQL that produces it and the SQL that lists its rows. The pipeline recomputes each figure from
those rows before publishing and refuses to publish one that does not reproduce. Every row carries its
source file and line.

## Exposure

| Engine | Exposure | Measured as |
| --- | ---: | --- |
| Three-way match | **£4,314,978.39** | purchase-to-pay value at risk (GBP) |
| Job cost reconciliation | **£1,735,365.44** | gross unexplained job cost gap (GBP) |
| Stock accuracy | **£15,297.69** | stock value error (GBP) |
| Material traceability | **786.153 t** | tonnes despatched with an EN 1090 compliance exposure |

## 1. Three-way match

Purchase order to goods received note to purchase invoice. Tolerances: quantity ±2%; price ±5%. Rows: `recon.three_way_lines`, one per PO line and per invoice with no PO, each with its category, value at risk, age and a one-line reason.

| Figure | Value | How it is calculated | Rows behind it |
| --- | ---: | --- | --- |
| Purchase-to-pay value at risk | **£4,314,978.39** | Sum of value at risk over every line in an exception category | `SELECT * FROM recon.three_way_lines WHERE is_exception` |
| Lines: matched | **492** | Lines classified matched | `SELECT * FROM recon.three_way_lines WHERE category = 'matched'` |
| Lines: quantity variance | **373** | Lines classified quantity variance | `SELECT * FROM recon.three_way_lines WHERE category = 'quantity variance'` |
| Value at risk: quantity variance | **£115,129.39** | Value at risk on lines classified quantity variance | `SELECT * FROM recon.three_way_lines WHERE category = 'quantity variance'` |
| Lines: price variance | **53** | Lines classified price variance | `SELECT * FROM recon.three_way_lines WHERE category = 'price variance'` |
| Value at risk: price variance | **£59,426.59** | Value at risk on lines classified price variance | `SELECT * FROM recon.three_way_lines WHERE category = 'price variance'` |
| Lines: missing GRN | **82** | Lines classified missing GRN | `SELECT * FROM recon.three_way_lines WHERE category = 'missing GRN'` |
| Value at risk: missing GRN | **£304,399.47** | Value at risk on lines classified missing GRN | `SELECT * FROM recon.three_way_lines WHERE category = 'missing GRN'` |
| Lines: missing invoice | **66** | Lines classified missing invoice | `SELECT * FROM recon.three_way_lines WHERE category = 'missing invoice'` |
| Value at risk: missing invoice | **£428,173.13** | Value at risk on lines classified missing invoice | `SELECT * FROM recon.three_way_lines WHERE category = 'missing invoice'` |
| Lines: invoice with no PO | **726** | Lines classified invoice with no PO | `SELECT * FROM recon.three_way_lines WHERE category = 'invoice with no PO'` |
| Value at risk: invoice with no PO | **£3,407,849.81** | Value at risk on lines classified invoice with no PO | `SELECT * FROM recon.three_way_lines WHERE category = 'invoice with no PO'` |
| Lines: not yet due | **38** | Lines classified not yet due | `SELECT * FROM recon.three_way_lines WHERE category = 'not yet due'` |
| Exceptions older than 90 days | **1,074** | Exception lines aged over 90 days | `SELECT * FROM recon.three_way_lines WHERE is_exception AND age_days > 90` |

| Category | Lines | Value at risk | Oldest (days) |
| --- | --- | --- | --- |
| matched | 492 | £0 |  |
| quantity variance | 373 | £115,129 | 718.0 |
| price variance | 53 | £59,427 | 678.0 |
| missing GRN | 82 | £304,399 | 723.0 |
| missing invoice | 66 | £428,173 | 745.0 |
| invoice with no PO | 726 | £3,407,850 | 724.0 |
| not yet due | 38 | £0 |  |

Ageing of unmatched items, by lines:

| Category | 0-30 days | 31-60 days | 61-90 days | 91-180 days | over 180 days |
| --- | --- | --- | --- | --- | --- |
| invoice with no PO | 46 | 57 | 48 | 108 | 467 |
| missing GRN | 4 | 2 | 12 | 5 | 59 |
| missing invoice | 0 | 1 | 3 | 7 | 55 |
| price variance | 7 | 1 | 3 | 5 | 37 |
| quantity variance | 14 | 15 | 13 | 52 | 279 |

Invoices with no PO, by spend type. Overheads on nominal 7000 are exempt:

| Spend type | Invoices | Value |
| --- | --- | --- |
| galvanising | 118 | £882,171 |
| paint | 104 | £880,517 |
| erection | 58 | £425,547 |
| profiling | 40 | £334,776 |
| subcontract fabrication | 24 | £212,820 |
| consumables | 124 | £200,925 |
| plant hire | 131 | £178,143 |
| inspection | 24 | £150,000 |
| transport | 103 | £142,951 |

## 2. Job cost reconciliation

Three views per job: Corvus (BOM material at average purchase price per kg, planned hours at £38/h), finance (job cost ledger), shop floor (booked hours at £38/h). Gap = (finance material - BOM material) + (finance labour - booked labour). Rows: `recon.job_cost`, one per job; `recon.job_cost_detail` holds every BOM line, cost line and booking behind it; `recon.job_material` explains the material gap by material.

| Figure | Value | How it is calculated | Rows behind it |
| --- | ---: | --- | --- |
| Unexplained job cost gap (gross) | **£1,735,365.44** | Sum over jobs of \|(finance material - BOM material) + (finance labour - booked hours x rate)\| | `SELECT * FROM recon.job_cost WHERE true` |
| Unexplained job cost gap (net) | **-£79,994.00** | Signed sum of job gaps | `SELECT * FROM recon.job_cost WHERE true` |
| Labour gap, finance vs shop floor (gross) | **£248,112.04** | Sum over jobs of \|finance labour - booked hours x standard rate\| | `SELECT * FROM recon.job_cost WHERE true` |
| Material gap on Corvus jobs (gross) | **£1,542,326.96** | Sum over Corvus jobs of \|finance material - BOM material\| | `SELECT * FROM recon.job_cost WHERE in_corvus` |
| Material cost charged to the wrong job | **£1,427,473.18** | Gross material gap less the net: the part that cancels out across jobs because steel invoiced to one job was issued to another. Detail by material in recon.job_material | `SELECT * FROM recon.job_cost WHERE in_corvus` |
| Jobs with a gap over 10% | **124** | Jobs whose gap exceeds 10% of reference cost | `SELECT * FROM recon.job_cost WHERE abs(gap_pct) > 0.10` |
| Finance cost on jobs Corvus does not hold | **£235,634.96** | All finance cost lines on unmapped codes | `SELECT * FROM recon.job_cost_detail WHERE NOT job_in_corvus` |
| Largest gap: J-25-0164 | **£63,204.83** | finance material £144,026 vs BOM material £81,519; charged £13,797 more UB406X178X60-S355J2 than issued; issued £3,163 of CHS168.3X6.3-S355J2 charged elsewhere; finance labour £58,829 vs 1,529.8 booked hours (£58,131) | `SELECT * FROM recon.job_cost WHERE job_no = 'J-25-0164'` |
| Hours booked to works orders not in Corvus | **242.0 h** | Bookings on orphan works orders: cost that reaches no job | `SELECT * FROM core.time_bookings WHERE NOT wo_matched` |
| Total corvus material | **£4,286,998.40** | Sum of corvus material detail rows | `SELECT * FROM recon.job_cost_detail WHERE view = 'corvus' AND component = 'material'` |
| Total finance material | **£4,172,144.62** | Sum of finance material detail rows | `SELECT * FROM recon.job_cost_detail WHERE view = 'finance' AND component = 'material'` |
| Total finance labour | **£2,849,911.89** | Sum of finance labour detail rows | `SELECT * FROM recon.job_cost_detail WHERE view = 'finance' AND component = 'labour'` |
| Total ops labour | **£2,815,052.11** | Sum of ops labour detail rows | `SELECT * FROM recon.job_cost_detail WHERE view = 'ops' AND component = 'labour'` |

Most of the material gap is steel charged to the wrong job. Finance posts each steel invoice to a single job, but one purchase order feeds several jobs. Totals agree while individual job margins are wrong. The labour gap cannot move between jobs this way, because bookings name the works order, so a labour gap is a genuine disagreement between payroll allocation and the shop floor.

Top 20 jobs by unexplained gap:

| # | Job | Customer | BOM material | Finance material | Booked labour | Finance labour | Gap | Gap % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | J-25-0164 | Westgate Rail Ltd | £81,519 | £144,026 | £58,131 | £58,829 | £63,205 | 45.3% |
| 2 | J-25-0138 | Harborough Industrial Ltd | £90,331 | £145,815 | £47,315 | £46,652 | £54,822 | 39.8% |
| 3 | J-25-0122 | Stanmore Build Ltd | £71,590 | £116,879 | £36,845 | £36,808 | £45,253 | 41.7% |
| 4 | J-26-0121 | Lowther Construction Ltd | £46,396 | £70,045 | £36,635 | £56,931 | £43,944 | 52.9% |
| 5 | J-24-0859 | Meridian Construction plc | £41,805 | £71,782 | £28,145 | £39,403 | £41,236 | 59.0% |
| 6 | J-26-0109 | Ridley Structures | £27,220 | £67,810 | £19,473 | £19,590 | £40,707 | 87.2% |
| 7 | J-26-0144 | Thornbury Estates Ltd | £45,321 | £27,356 | £37,949 | £22,049 | -£33,866 | -40.7% |
| 8 | J-26-0107 | Brackley Logistics Parks | £52,949 | £20,853 | £29,344 | £29,138 | -£32,301 | -39.2% |
| 9 | J-26-0103 | Harborough Industrial Ltd | £50,302 | £19,888 | £35,593 | £35,166 | -£30,841 | -35.9% |
| 10 | J-24-0866 | Meridian Construction plc | £52,662 | £82,030 | £33,014 | £33,245 | £29,600 | 34.5% |
| 11 | J-25-0165 | Thornbury Estates Ltd | £55,220 | £26,937 | £30,531 | £30,775 | -£28,039 | -32.7% |
| 12 | J-25-0130 | Caledonian Rail Engineering Ltd | £33,310 | £61,077 | £17,954 | £17,936 | £27,750 | 54.1% |
| 13 | J-26-0101 | Whitmore Warehousing plc | £31,378 | £6,158 | £15,286 | £15,103 | -£25,403 | -54.4% |
| 14 | J-25-0139 | Kingsmead Retail Developments | £47,714 | £22,995 | £20,235 | £20,437 | -£24,517 | -36.1% |
| 15 | J-25-0168 | Oakridge Developments | £31,600 | £7,631 | £18,630 | £18,741 | -£23,857 | -47.5% |
| 16 | J-25-0161 | Meridian Construction plc | £57,082 | £65,401 | £37,655 | £52,454 | £23,117 | 24.4% |
| 17 | J-26-0138 | Lowther Construction Ltd | £50,197 | £73,045 | £30,656 | £30,902 | £23,094 | 28.6% |
| 18 | J-26-0108 | Ashcroft Build Ltd | £55,960 | £78,465 | £28,912 | £28,480 | £22,073 | 26.0% |
| 19 | J-26-0102 | Ridley Structures | £55,721 | £77,436 | £34,372 | £34,373 | £21,716 | 24.1% |
| 20 | J-25-0152 | Kestrel Main Contractors Ltd | £50,936 | £37,518 | £27,583 | £19,528 | -£21,473 | -27.4% |

Top 10 jobs by labour gap, where finance and the shop floor disagree on hours:

| Job | Booked hours | Booked labour | Finance labour | Labour gap | Gap % |
| --- | --- | --- | --- | --- | --- |
| J-26-0121 | 964.1 | £36,635 | £56,931 | £20,295 | 55.4% |
| J-26-0144 | 998.7 | £37,949 | £22,049 | -£15,901 | -41.9% |
| J-25-0161 | 990.9 | £37,655 | £52,454 | £14,798 | 39.3% |
| J-25-0103 | 561.5 | £21,335 | £34,971 | £13,636 | 63.9% |
| J-25-0163 | 780.9 | £29,674 | £17,775 | -£11,899 | -40.1% |
| J-24-0859 | 740.7 | £28,145 | £39,403 | £11,258 | 40.0% |
| J-25-0105 | 452.6 | £17,200 | £27,777 | £10,577 | 61.5% |
| J-24-0872 | 655.2 | £24,897 | £16,183 | -£8,714 | -35.0% |
| J-25-0136 | 697.4 | £26,502 | £18,074 | -£8,428 | -31.8% |
| J-25-0152 | 725.9 | £27,583 | £19,528 | -£8,054 | -29.2% |

## 3. Stock accuracy

Book against counted quantity. A line is accurate when the count agrees within 0% of book; target 95% of lines. Rows: `recon.stock_lines`.

| Figure | Value | How it is calculated | Rows behind it |
| --- | ---: | --- | --- |
| Stock line accuracy | **89.62%** | Share of counted lines agreeing with the book; target 95% | `SELECT * FROM recon.stock_lines WHERE true` |
| Stock value error | **£15,297.69** | Sum of \|counted - book\| x unit cost | `SELECT * FROM recon.stock_lines WHERE NOT accurate` |
| Net stock adjustment if counts are right | **£4,537.31** | Sum of (counted - book) x unit cost | `SELECT * FROM recon.stock_lines WHERE NOT accurate` |
| Lines where count disagrees with book | **11** | Counted lines outside tolerance | `SELECT * FROM recon.stock_lines WHERE NOT accurate` |
| Steel miscounted | **14,050.2 kg** | Sum of \|counted - book\| converted to kg with the golden mass | `SELECT * FROM recon.stock_lines WHERE NOT accurate AND abs_error_kg IS NOT NULL` |
| Site and section groups below target | **8** | Site x section type groups whose line accuracy is below target | `SELECT * FROM recon.stock_summary WHERE NOT meets_target` |
| Stock line accuracy, TEE | **87.93%** | Line accuracy at TEE | `SELECT * FROM recon.stock_lines WHERE site_code = 'TEE'` |
| Stock line accuracy, WKF | **91.67%** | Line accuracy at WKF | `SELECT * FROM recon.stock_lines WHERE site_code = 'WKF'` |

| Site | Section | Lines | Accurate | Accuracy | Error kg | Value error | Value accuracy | Meets target |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TEE | CHS | 5 | 5 | 100.0% | 0.0 | £0 | 100.0% | True |
| TEE | CONSUMABLE | 7 | 7 | 100.0% | 0.0 | £0 | 100.0% | True |
| TEE | FLAT | 2 | 2 | 100.0% | 0.0 | £0 | 100.0% | True |
| TEE | L | 4 | 4 | 100.0% | 0.0 | £0 | 100.0% | True |
| TEE | PFC | 5 | 4 | 80.0% | 706.7 | £660 | 98.5% | False |
| TEE | PLATE | 9 | 6 | 66.7% | 97.9 | £88 | 97.5% | False |
| TEE | RHS | 4 | 4 | 100.0% | 0.0 | £0 | 100.0% | True |
| TEE | SHS | 5 | 3 | 60.0% | 2,110.8 | £2,617 | 87.2% | False |
| TEE | UB | 10 | 9 | 90.0% | 2,548.2 | £2,602 | 99.1% | False |
| TEE | UC | 7 | 7 | 100.0% | 0.0 | £0 | 100.0% | True |
| WKF | CHS | 4 | 3 | 75.0% | 604.8 | £724 | 98.2% | False |
| WKF | CONSUMABLE | 7 | 7 | 100.0% | 0.0 | £0 | 100.0% | True |
| WKF | FLAT | 2 | 1 | 50.0% | 123.7 | £117 | 96.3% | False |
| WKF | L | 5 | 4 | 80.0% | 1,853.3 | £1,895 | 91.4% | False |
| WKF | PFC | 4 | 4 | 100.0% | 0.0 | £0 | 100.0% | True |
| WKF | PLATE | 5 | 5 | 100.0% | 0.0 | £0 | 100.0% | True |
| WKF | RHS | 1 | 1 | 100.0% | 0.0 | £0 | 100.0% | True |
| WKF | SHS | 3 | 3 | 100.0% | 0.0 | £0 | 100.0% | True |
| WKF | UB | 11 | 10 | 90.9% | 6,004.8 | £6,596 | 97.3% | False |
| WKF | UC | 6 | 6 | 100.0% | 0.0 | £0 | 100.0% | True |

Top offending lines by value (11 of the 11 lines that disagree; the list stops at 20):

| # | Material | Site | Location | Book | Counted | Unit | Value error |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1.0 | UB610X229X125-S355J2 | WKF | BAY 2 | 35.0 | 39.0 | EA | £6,596 |
| 2.0 | UB406X178X60-S355J2 | TEE | YARD | 309.9 | 267.5 | M | £2,602 |
| 3.0 | SHS100X100X6.3-S355J2 | TEE | RACK A3 | 435.6 | 543.2 | M | £2,464 |
| 4.0 | L150X90X12-S355J0 | WKF | RACK B2 | 447.8 | 362.0 | M | £1,895 |
| 5.0 | CHS168.3X6.3-S355J2 | WKF | BAY 4 | 39.0 | 37.0 | EA | £724 |
| 6.0 | PFC200X75X23-S355J0 | TEE | BAY 4 | 645.3 | 675.5 | M | £660 |
| 7.0 | SHS80X80X5-S355J2 | TEE | BAY 2 | 89.7 | 100.9 | M | £153 |
| 8.0 | FLAT50X8-S275JR | WKF | RACK A3 | 598.6 | 559.2 | M | £117 |
| 9.0 | PLT8-S275JR | TEE | PLATE STORE | 416.7 | 469.2 | KG | £45 |
| 10.0 | PLT25-S355J2 | TEE | PLATE STORE | 145.7 | 111.3 | KG | £32 |
| 11.0 | PLT20-S355J2 | TEE | PLATE STORE | 69.5 | 58.5 | KG | £11 |

## 4. Material traceability

Chain: mill certificate and heat number, goods receipt, material issue, works order, delivery note.
Corvus records no material issues, so which receipt supplied which works order is reconstructed by allocating confirmed-grade receipts first-in first-out, in kg, to BOM lines. That the link has to be inferred at all is a finding. Rows: `recon.trace_lines`, one per BOM line on a started works order; `recon.trace_allocations`, receipt to BOM line; `recon.trace_receipts`, one per goods receipt; `recon.trace_jobs` and `recon.trace_customers`.

What EN 1090-2 (clause 5.2) requires depends on the execution class the designer specified for the structure, which Corvus records on every works order. On EXC3 and EXC4 work, steel must be traceable from receipt to hand over, so any incomplete chain on steel already despatched is a compliance exposure. On EXC2 work full traceability is not required, but S355 needs a 3.1 inspection document at every class: S355 despatched on an EXC2 job with no certified receipt covering it is a compliance exposure too. Any other incomplete chain on EXC2 work is a quality and good-practice gap, reported separately.

| Figure | Value | How it is calculated | Rows behind it |
| --- | ---: | --- | --- |
| Material traceability coverage, all work | **68.73%** | Share of BOM kilograms on started works orders traced to a receipt with heat number and certificate | `SELECT * FROM recon.trace_lines WHERE true` |
| Material traceability coverage on EXC3 work | **66.44%** | The same share on EXC3 jobs, where EN 1090-2 requires full traceability | `SELECT * FROM recon.trace_lines WHERE traceability_required` |
| Material traceability coverage on EXC2 work | **69.88%** | The same share on EXC2 jobs, where full traceability is good practice | `SELECT * FROM recon.trace_lines WHERE NOT traceability_required` |
| Jobs with an EN 1090 compliance exposure | **145** | EXC3 jobs despatched with an incomplete chain, and EXC2 jobs despatched with S355 whose 3.1 inspection document cannot be shown | `SELECT * FROM recon.trace_jobs WHERE en1090_exposure` |
| Customers with an EN 1090 compliance exposure | **38** | Distinct customers of jobs with a compliance exposure | `SELECT * FROM recon.trace_jobs WHERE en1090_exposure` |
| Despatched steel with an EN 1090 compliance exposure | **786.153 t** | BOM kilograms already on site where EN 1090-2 clause 5.2 is not met | `SELECT * FROM recon.trace_lines WHERE compliance_exposure` |
| EXC3 steel despatched with an incomplete chain | **384.003 t** | Part of the compliance exposure: full traceability is required | `SELECT * FROM recon.trace_lines WHERE exposure = 'EN 1090: EXC3 chain incomplete'` |
| EXC2 S355 steel despatched with no 3.1 document shown | **402.150 t** | Part of the compliance exposure: S355 needs a 3.1 inspection document at every class, and no certified receipt covers this steel | `SELECT * FROM recon.trace_lines WHERE exposure = 'EN 1090: S355 with no 3.1 document shown'` |
| Sales value of jobs with a compliance exposure | **£14,350,729.90** | Invoiced sales on jobs with an EN 1090 compliance exposure | `SELECT * FROM recon.trace_jobs WHERE en1090_exposure` |
| EXC2 jobs despatched with an incomplete chain | **92** | A quality and good-practice gap, not an EN 1090 requirement on EXC2 work | `SELECT * FROM recon.trace_jobs WHERE practice_gap` |
| EXC2 steel despatched with an incomplete chain | **316.474 t** | A quality and good-practice gap, not an EN 1090 requirement on EXC2 work | `SELECT * FROM recon.trace_lines WHERE practice_gap` |
| S355 receipts without a 3.1 inspection document | **69** | Receipts of confirmed S355 steel with no mill certificate; required at every execution class | `SELECT * FROM recon.trace_receipts WHERE s355 AND NOT document_31` |
| Break at receipt: heat number missing | **651** | BOM lines whose chain first fails at: receipt: heat number missing | `SELECT * FROM recon.trace_lines WHERE break_at = 'receipt: heat number missing'` |
| Break at receipt: mill certificate missing | **458** | BOM lines whose chain first fails at: receipt: mill certificate missing | `SELECT * FROM recon.trace_lines WHERE break_at = 'receipt: mill certificate missing'` |
| Break at issue: receipt grade unconfirmed | **656** | BOM lines whose chain first fails at: issue: receipt grade unconfirmed | `SELECT * FROM recon.trace_lines WHERE break_at = 'issue: receipt grade unconfirmed'` |
| Break at issue: no receipt on record | **74** | BOM lines whose chain first fails at: issue: no receipt on record | `SELECT * FROM recon.trace_lines WHERE break_at = 'issue: no receipt on record'` |
| Break at despatch: no delivery note | **21** | BOM lines whose chain first fails at: despatch: no delivery note | `SELECT * FROM recon.trace_lines WHERE break_at = 'despatch: no delivery note'` |

Jobs by execution class:

| Execution class | Jobs | With a compliance exposure | With a good-practice gap |
| --- | --- | --- | --- |
| EXC2 | 97 | 92 | 92 |
| EXC3 | 53 | 53 | 0 |

Where chains break:

| Break point | BOM lines | kg | Already despatched |
| --- | --- | --- | --- |
| complete | 3,847 | 2,731,910.9 | 0 |
| despatch: no delivery note | 21 | 22,511.7 | 0 |
| issue: no receipt on record | 74 | 65,357.9 | 65 |
| issue: receipt grade unconfirmed | 656 | 375,279.9 | 552 |
| receipt: heat number missing | 651 | 530,674.0 | 560 |
| receipt: mill certificate missing | 458 | 281,636.4 | 400 |

Despatched steel by what it means and where its chain breaks:

| Meaning | Break point | BOM lines | kg |
| --- | --- | --- | --- |
| EN 1090: EXC3 chain incomplete | issue: no receipt on record | 18 | 19,558.0 |
| EN 1090: EXC3 chain incomplete | issue: receipt grade unconfirmed | 201 | 104,963.3 |
| EN 1090: EXC3 chain incomplete | receipt: heat number missing | 248 | 172,952.8 |
| EN 1090: EXC3 chain incomplete | receipt: mill certificate missing | 143 | 86,529.3 |
| EN 1090: S355 with no 3.1 document shown | issue: no receipt on record | 40 | 39,063.6 |
| EN 1090: S355 with no 3.1 document shown | issue: receipt grade unconfirmed | 225 | 138,813.6 |
| EN 1090: S355 with no 3.1 document shown | receipt: heat number missing | 82 | 69,898.4 |
| EN 1090: S355 with no 3.1 document shown | receipt: mill certificate missing | 195 | 154,374.0 |
| good practice: EXC2 chain incomplete | issue: no receipt on record | 7 | 1,414.1 |
| good practice: EXC2 chain incomplete | issue: receipt grade unconfirmed | 126 | 73,630.9 |
| good practice: EXC2 chain incomplete | receipt: heat number missing | 230 | 222,151.9 |
| good practice: EXC2 chain incomplete | receipt: mill certificate missing | 62 | 19,276.8 |

A single receipt without a heat number or certificate taints every works order it supplied. Because one delivery of steel feeds many jobs, a minority of untraceable receipts reaches almost every job.

EN 1090 compliance exposure by customer:

| Customer | Jobs | BOM lines | Exposed kg | Sales value |
| --- | --- | --- | --- | --- |
| Lowther Construction Ltd | 10 | 77 | 60,185.2 | £1,282,189 |
| Caledonian Rail Engineering Ltd | 4 | 55 | 53,621.8 | £856,012 |
| Harborough Industrial Ltd | 4 | 30 | 47,160.6 | £543,460 |
| Beacon Mast Services Ltd | 9 | 106 | 38,566.9 | £553,176 |
| Westgate Rail Ltd | 2 | 26 | 34,949.6 | £561,293 |
| Stanmore Build Ltd | 5 | 37 | 33,570.8 | £534,504 |
| Severn Rail Projects Ltd | 3 | 46 | 33,114.3 | £393,471 |
| Denton Steel Erectors | 6 | 32 | 32,407.3 | £656,047 |
| Ashcroft Build Ltd | 2 | 45 | 28,510.4 | £313,760 |
| Meridian Construction plc | 3 | 31 | 27,861.2 | £575,227 |
| Brackley Logistics Parks | 5 | 42 | 27,605.1 | £543,715 |
| Ridley Structures | 4 | 27 | 27,350.2 | £494,274 |
| Thornbury Estates Ltd | 5 | 29 | 25,265.3 | £459,759 |
| Fairfield Architectural Ltd | 4 | 35 | 24,502.1 | £386,786 |
| Oakridge Developments | 4 | 27 | 24,260.0 | £306,019 |
| Bramhall Group plc | 3 | 31 | 23,308.9 | £485,858 |
| Highland Mast & Tower Ltd | 7 | 57 | 22,240.6 | £307,906 |
| Whitmore Warehousing plc | 3 | 30 | 21,230.1 | £260,026 |
| Wharfe Valley Homes | 7 | 32 | 21,056.0 | £564,725 |
| Lindsey Energy Services | 6 | 28 | 20,785.1 | £571,977 |
| Calder Engineering Ltd | 5 | 35 | 19,952.8 | £536,031 |
| Eastway Civils Ltd | 3 | 23 | 15,687.1 | £423,022 |
| Ellesmere Interiors Ltd | 6 | 32 | 14,759.4 | £350,958 |
| Aerial Sites UK Ltd | 4 | 53 | 13,788.6 | £212,261 |
| Fenwick Communications plc | 2 | 26 | 12,861.9 | £124,554 |
| Skyreach Networks Ltd | 5 | 42 | 11,844.9 | £172,973 |
| Orbital Wireless Infrastructure | 3 | 23 | 10,934.4 | £158,651 |
| Kestrel Main Contractors Ltd | 1 | 5 | 9,943.6 | £147,047 |
| Pennine Rail Alliance | 1 | 6 | 9,322.3 | £114,451 |
| Northgate Telecom Infrastructure Ltd | 3 | 17 | 9,205.4 | £151,796 |
| Kingsmead Retail Developments | 3 | 12 | 8,961.6 | £251,551 |
| Northern Route Partners | 3 | 15 | 8,231.5 | £325,565 |
| Marlow Facades Ltd | 1 | 9 | 4,203.3 | £111,879 |
| Pendle Networks Ltd | 3 | 9 | 3,542.0 | £142,398 |
| Holbeck Developments Ltd | 3 | 12 | 3,401.2 | £171,121 |
| Meridian Telecom Build Ltd | 1 | 6 | 1,169.0 | £70,773 |
| Harland & Cole Construction | 1 | 3 | 671.6 | £163,894 |
| Greyfriars Property Group | 1 | 1 | 121.0 | £71,619 |

Top 15 jobs with a compliance exposure:

| Job | Class | Customer | Coverage | Exposed lines | Exposed kg | Tonnes despatched |
| --- | --- | --- | --- | --- | --- | --- |
| J-25-0164 | EXC3 | Westgate Rail Ltd | 56.4% | 21 | 31,622.0 | 72.9 |
| J-26-0103 | EXC2 | Harborough Industrial Ltd | 30.5% | 9 | 29,814.3 | 47.6 |
| J-26-0102 | EXC3 | Ridley Structures | 56.9% | 18 | 23,357.0 | 54.2 |
| J-26-0113 | EXC3 | Caledonian Rail Engineering Ltd | 64.3% | 20 | 22,637.8 | 61.4 |
| J-26-0108 | EXC3 | Ashcroft Build Ltd | 52.1% | 28 | 20,772.1 | 46.8 |
| J-25-0147 | EXC3 | Caledonian Rail Engineering Ltd | 63.6% | 13 | 19,899.5 | 52.4 |
| J-24-0866 | EXC3 | Meridian Construction plc | 59.8% | 15 | 18,834.9 | 44.9 |
| J-25-0158 | EXC3 | Severn Rail Projects Ltd | 61.9% | 10 | 16,956.8 | 43.5 |
| J-26-0138 | EXC3 | Lowther Construction Ltd | 56.9% | 9 | 15,701.2 | 34.6 |
| J-24-0852 | EXC2 | Denton Steel Erectors | 66.0% | 8 | 14,684.2 | 51.9 |
| J-25-0173 | EXC3 | Bramhall Group plc | 57.6% | 13 | 14,443.7 | 34.0 |
| J-25-0167 | EXC2 | Whitmore Warehousing plc | 62.7% | 17 | 13,370.8 | 38.9 |
| J-26-0107 | EXC2 | Brackley Logistics Parks | 66.8% | 15 | 13,089.1 | 48.0 |
| J-26-0131 | EXC2 | Harborough Industrial Ltd | 56.4% | 9 | 12,934.9 | 38.2 |
| J-25-0122 | EXC2 | Stanmore Build Ltd | 79.4% | 9 | 12,236.3 | 65.1 |

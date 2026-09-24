# Reconciliation report

**All data reconciled here is synthetic.** It represents no real company, supplier, customer or job.

Produced by `make reconcile` as at 2026-08-31. Every figure below is stored in `recon.headline`
with the SQL that produces it and the SQL that lists its rows. The pipeline recomputes each figure from
those rows before publishing and refuses to publish one that does not reproduce. Every row carries its
source file and line.

## Exposure

| Engine | Exposure | Measured as |
| --- | ---: | --- |
| Three-way match | **£4,315,267.60** | purchase-to-pay value at risk (GBP) |
| Job cost reconciliation | **£1,735,365.44** | gross unexplained job cost gap (GBP) |
| Stock accuracy | **£15,297.69** | stock value error (GBP) |
| Material traceability | **1,102.627 t** | tonnes despatched without full traceability |

## 1. Three-way match

Purchase order to goods received note to purchase invoice. Tolerances: quantity ±2%; price the greater of 5% or £50. Rows: `recon.three_way_lines`, one per PO line and per invoice with no PO, each with its category, value at risk, age and a one-line reason.

| Figure | Value | How it is calculated | Rows behind it |
| --- | ---: | --- | --- |
| Purchase-to-pay value at risk | **£4,315,267.60** | Sum of value at risk over every line in an exception category | `SELECT * FROM recon.three_way_lines WHERE is_exception` |
| Lines: matched | **493** | Lines classified matched | `SELECT * FROM recon.three_way_lines WHERE category = 'matched'` |
| Lines: quantity variance | **377** | Lines classified quantity variance | `SELECT * FROM recon.three_way_lines WHERE category = 'quantity variance'` |
| Value at risk: quantity variance | **£115,552.56** | Value at risk on lines classified quantity variance | `SELECT * FROM recon.three_way_lines WHERE category = 'quantity variance'` |
| Lines: price variance | **48** | Lines classified price variance | `SELECT * FROM recon.three_way_lines WHERE category = 'price variance'` |
| Value at risk: price variance | **£59,292.62** | Value at risk on lines classified price variance | `SELECT * FROM recon.three_way_lines WHERE category = 'price variance'` |
| Lines: missing GRN | **82** | Lines classified missing GRN | `SELECT * FROM recon.three_way_lines WHERE category = 'missing GRN'` |
| Value at risk: missing GRN | **£304,399.47** | Value at risk on lines classified missing GRN | `SELECT * FROM recon.three_way_lines WHERE category = 'missing GRN'` |
| Lines: missing invoice | **66** | Lines classified missing invoice | `SELECT * FROM recon.three_way_lines WHERE category = 'missing invoice'` |
| Value at risk: missing invoice | **£428,173.13** | Value at risk on lines classified missing invoice | `SELECT * FROM recon.three_way_lines WHERE category = 'missing invoice'` |
| Lines: invoice with no PO | **726** | Lines classified invoice with no PO | `SELECT * FROM recon.three_way_lines WHERE category = 'invoice with no PO'` |
| Value at risk: invoice with no PO | **£3,407,849.81** | Value at risk on lines classified invoice with no PO | `SELECT * FROM recon.three_way_lines WHERE category = 'invoice with no PO'` |
| Lines: not yet due | **38** | Lines classified not yet due | `SELECT * FROM recon.three_way_lines WHERE category = 'not yet due'` |
| Exceptions older than 90 days | **1,076** | Exception lines aged over 90 days | `SELECT * FROM recon.three_way_lines WHERE is_exception AND age_days > 90` |

| Category | Lines | Value at risk | Oldest (days) |
| --- | --- | --- | --- |
| matched | 493 | £0 |  |
| quantity variance | 377 | £115,553 | 718.0 |
| price variance | 48 | £59,293 | 678.0 |
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
| price variance | 5 | 0 | 1 | 5 | 37 |
| quantity variance | 15 | 15 | 14 | 52 | 281 |

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
Corvus records no material issues, so which receipt supplied which works order is reconstructed by allocating confirmed-grade receipts first-in first-out, in kg, to BOM lines. That the link has to be inferred at all is a finding. Rows: `recon.trace_lines`, one per BOM line on a started works order; `recon.trace_allocations`, receipt to BOM line; `recon.trace_jobs` and `recon.trace_customers`.

| Figure | Value | How it is calculated | Rows behind it |
| --- | ---: | --- | --- |
| Material traceability coverage | **68.73%** | Share of BOM kilograms on started works orders traced to a receipt with heat number and certificate | `SELECT * FROM recon.trace_lines WHERE true` |
| Jobs despatched with an incomplete chain | **148** | EN 1090 factory production control exposure: steel already on site without full traceability | `SELECT * FROM recon.trace_jobs WHERE en1090_exposure` |
| Customers with exposed jobs | **38** | Distinct customers of exposed jobs | `SELECT * FROM recon.trace_jobs WHERE en1090_exposure` |
| Despatched steel without full traceability | **1,102.627 t** | BOM kilograms on despatched works orders whose material chain is broken | `SELECT * FROM recon.trace_lines WHERE exposed` |
| Sales value of exposed jobs | **£14,465,876.29** | Invoiced sales on jobs with an EN 1090 exposure | `SELECT * FROM recon.trace_jobs WHERE en1090_exposure` |
| Break at receipt: heat number missing | **651** | BOM lines whose chain first fails at: receipt: heat number missing | `SELECT * FROM recon.trace_lines WHERE break_at = 'receipt: heat number missing'` |
| Break at receipt: mill certificate missing | **458** | BOM lines whose chain first fails at: receipt: mill certificate missing | `SELECT * FROM recon.trace_lines WHERE break_at = 'receipt: mill certificate missing'` |
| Break at issue: receipt grade unconfirmed | **656** | BOM lines whose chain first fails at: issue: receipt grade unconfirmed | `SELECT * FROM recon.trace_lines WHERE break_at = 'issue: receipt grade unconfirmed'` |
| Break at issue: no receipt on record | **74** | BOM lines whose chain first fails at: issue: no receipt on record | `SELECT * FROM recon.trace_lines WHERE break_at = 'issue: no receipt on record'` |
| Break at despatch: no delivery note | **21** | BOM lines whose chain first fails at: despatch: no delivery note | `SELECT * FROM recon.trace_lines WHERE break_at = 'despatch: no delivery note'` |

Where chains break:

| Break point | BOM lines | kg | Already despatched |
| --- | --- | --- | --- |
| complete | 3,847 | 2,731,910.9 | 0 |
| despatch: no delivery note | 21 | 22,511.7 | 0 |
| issue: no receipt on record | 74 | 65,357.9 | 65 |
| issue: receipt grade unconfirmed | 656 | 375,279.9 | 552 |
| receipt: heat number missing | 651 | 530,674.0 | 560 |
| receipt: mill certificate missing | 458 | 281,636.4 | 400 |

A single receipt without a heat number or certificate taints every works order it supplied. Because one delivery of steel feeds many jobs, a minority of untraceable receipts reaches almost every job.

EN 1090 exposure by customer:

| Customer | Jobs | BOM lines | Untraceable kg | Sales value |
| --- | --- | --- | --- | --- |
| Lowther Construction Ltd | 11 | 135 | 138,872.4 | £1,321,872 |
| Thornbury Estates Ltd | 5 | 58 | 66,975.7 | £459,759 |
| Harborough Industrial Ltd | 4 | 58 | 59,805.1 | £543,460 |
| Caledonian Rail Engineering Ltd | 4 | 62 | 58,708.1 | £856,012 |
| Oakridge Developments | 4 | 46 | 47,590.1 | £306,019 |
| Stanmore Build Ltd | 5 | 58 | 43,809.5 | £534,504 |
| Bramhall Group plc | 3 | 47 | 42,936.6 | £485,858 |
| Denton Steel Erectors | 6 | 53 | 42,144.7 | £656,047 |
| Brackley Logistics Parks | 5 | 65 | 39,029.8 | £543,715 |
| Beacon Mast Services Ltd | 9 | 106 | 38,566.9 | £553,176 |
| Lindsey Energy Services | 6 | 59 | 38,257.2 | £571,977 |
| Westgate Rail Ltd | 2 | 26 | 34,949.6 | £561,293 |
| Calder Engineering Ltd | 5 | 60 | 34,691.2 | £536,031 |
| Ridley Structures | 4 | 31 | 33,604.3 | £494,274 |
| Severn Rail Projects Ltd | 3 | 46 | 33,114.3 | £393,471 |
| Meridian Construction plc | 3 | 35 | 30,432.8 | £575,227 |
| Ashcroft Build Ltd | 2 | 45 | 28,510.4 | £313,760 |
| Fairfield Architectural Ltd | 4 | 41 | 27,105.1 | £386,786 |
| Wharfe Valley Homes | 7 | 50 | 24,803.4 | £564,725 |
| Whitmore Warehousing plc | 3 | 40 | 24,645.5 | £260,026 |
| Highland Mast & Tower Ltd | 7 | 61 | 24,304.0 | £307,906 |
| Ellesmere Interiors Ltd | 6 | 48 | 22,391.1 | £350,958 |
| Kestrel Main Contractors Ltd | 1 | 19 | 20,221.4 | £147,047 |
| Eastway Civils Ltd | 3 | 29 | 18,387.2 | £423,022 |
| Northern Route Partners | 3 | 28 | 16,742.6 | £325,565 |
| Kingsmead Retail Developments | 3 | 18 | 14,170.7 | £251,551 |
| Aerial Sites UK Ltd | 4 | 53 | 13,788.6 | £212,261 |
| Fenwick Communications plc | 2 | 29 | 13,768.0 | £124,554 |
| Skyreach Networks Ltd | 5 | 45 | 13,146.5 | £172,973 |
| Orbital Wireless Infrastructure | 3 | 23 | 10,934.4 | £158,651 |
| Northgate Telecom Infrastructure Ltd | 3 | 21 | 9,709.1 | £151,796 |
| Pennine Rail Alliance | 1 | 6 | 9,322.3 | £114,451 |
| Marlow Facades Ltd | 2 | 18 | 7,318.5 | £149,287 |
| Greyfriars Property Group | 2 | 12 | 6,528.1 | £109,675 |
| Holbeck Developments Ltd | 3 | 17 | 4,734.1 | £171,121 |
| Pendle Networks Ltd | 3 | 12 | 3,774.1 | £142,398 |
| Harland & Cole Construction | 1 | 5 | 2,717.5 | £163,894 |
| Meridian Telecom Build Ltd | 1 | 12 | 2,115.8 | £70,773 |

Top 15 exposed jobs:

| Job | Customer | Coverage | Exposed lines | Untraceable kg | Tonnes despatched |
| --- | --- | --- | --- | --- | --- |
| J-25-0127 | Lowther Construction Ltd | 63.4% | 13 | 34,132.7 | 93.4 |
| J-26-0103 | Harborough Industrial Ltd | 30.5% | 19 | 33,123.6 | 47.6 |
| J-25-0164 | Westgate Rail Ltd | 56.4% | 21 | 31,622.0 | 72.9 |
| J-25-0157 | Bramhall Group plc | 59.2% | 25 | 24,468.1 | 32.0 |
| J-26-0102 | Ridley Structures | 56.9% | 18 | 23,357.0 | 54.2 |
| J-26-0113 | Caledonian Rail Engineering Ltd | 64.3% | 20 | 22,637.8 | 61.4 |
| J-26-0108 | Ashcroft Build Ltd | 52.1% | 28 | 20,772.1 | 46.8 |
| J-25-0152 | Kestrel Main Contractors Ltd | 56.5% | 19 | 20,221.4 | 45.3 |
| J-25-0131 | Lowther Construction Ltd | 60.2% | 17 | 20,166.6 | 50.7 |
| J-25-0147 | Caledonian Rail Engineering Ltd | 63.6% | 13 | 19,899.5 | 52.4 |
| J-24-0866 | Meridian Construction plc | 59.8% | 15 | 18,834.9 | 44.9 |
| J-26-0131 | Harborough Industrial Ltd | 56.4% | 17 | 18,730.5 | 38.2 |
| J-25-0165 | Thornbury Estates Ltd | 58.2% | 14 | 18,051.1 | 45.0 |
| J-24-0852 | Denton Steel Erectors | 66.0% | 17 | 17,647.2 | 51.9 |
| J-26-0106 | Oakridge Developments | 57.1% | 6 | 17,613.0 | 41.0 |

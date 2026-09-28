# Match quality report

**All data matched here is synthetic.** It represents no real company, supplier, customer or job.

Produced by the match stage (`make run-all`). Every figure is queryable in `governance.match_quality`,
the crosswalks in `core.*_xref`, and the combined review queue in `core.v_match_review_queue`.

Bands: a score of 95 or more is accepted automatically; 80 to 95 goes to a person; below 80 is never merged. Source values are
never overwritten: every crosswalk row keeps the value as written beside the canonical value, with
`method`, `score`, `matched_on` and `matched_at`.

## Summary

| Domain | Population | Values | Auto | Auto % | Auto % of rows | Review queue | Unmatched | Effort (h) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| material | distinct written forms per Corvus table | 423 | 340 | 80.4% | 96.8% | 83 | 0 | 8.3 |
| supplier | Corvus supplier codes | 24 | 21 | 87.5% | 89.5% | 4 | 1 | 0.3 |
| job | job references across all three systems | 774 | 754 | 97.4% | 97.6% | 0 | 20 | 0.0 |
| works order | distinct shop-floor works order references | 3,473 | 3,451 | 99.4% | 99.6% | 6 | 0 | 0.5 |

**Estimated manual effort to clear the review queue: 9.1 hours** (93 items). Minutes per item are assumptions in `config/matching.toml`: supplier 4, material 6, works order 5, job 3.
Unmatched values need investigation rather than review and are not in that estimate.

## Materials

423 distinct ways of writing a material across four Corvus tables resolve to 47 golden
materials. 14 of them are transacted in more than one unit of measure, and 0 carry a BOM unit weight off the reference by more than 2%.

Every BOM line resolves, because the BOM carries a grade column. Codes on purchase orders, goods
received and stock that omit the grade cannot be resolved from the data: where the section is held in
one grade the grade is proposed for confirmation; where it is held in several, a person must read the
mill certificate. Those review items cover 246 purchase order and goods received lines, each needing its own
certificate check. On EXC3 work that is an EN 1090 traceability exposure, and S355 needs its 3.1
certificate at every execution class: it is not a formatting problem.

| Method | Status | Values | Rows |
| --- | --- | --- | --- |
| canonical_code | auto | 188 | 6853 |
| parsed_code+grade_column | auto | 144 | 1001 |
| non_section_passthrough | auto | 7 | 14 |
| parsed_code+grade_in_description | auto | 1 | 1 |
| grade_inferred_single_stocked_grade | review | 54 | 148 |
| grade_ambiguous | review | 29 | 115 |

Survivorship: identity: parsed type + designation, grade from BOM column > code > description; mass: section catalogue > serial mass in designation > modal BOM unit weight; description: generated; base unit: M (plate KG).

Golden records with most variant spellings:

| Canonical | Description | Mass | Basis | Units seen | Written as |
| --- | --- | --- | --- | --- | --- |
| CHS114.3X5-S355J2 | CHS 114.3x5 S355J2 | 13.5 | kg/m | EA, KG, M | 114.3X5CHS, CHS114.3X5, CHS114.3X5-S355J2 |
| L150X90X12-S355J0 | L 150x90x12 S355J0 | 21.6 | kg/m | M | 150X90X12L, L150X90X12, L150X90X12-S355J0 |
| L75X75X8-S355J0 | L 75x75x8 S355J0 | 8.99 | kg/m | M | 75X75X8L, L75X75X8, L75X75X8-S355J0 |
| PFC100X50X10-S275JR | PFC 100x50x10 S275JR | 10.2 | kg/m | M | 100X50X10PFC, PFC100X50X10, PFC100X50X10-S275JR |
| PFC260X75X28-S355J0 | PFC 260x75x28 S355J0 | 27.6 | kg/m | M | 260X75X28PFC, PFC260X75X28, PFC260X75X28-S355J0 |
| PLT12-S355J2 | PLATE 12mm S355J2 | 94.2 | kg/m2 | KG | PL12MM, PLATE12, PLT12-S355J2 |
| PLT25-S355J2 | PLATE 25mm S355J2 | 196.25 | kg/m2 | KG | PL25MM, PLATE25, PLT25-S355J2 |
| RHS150X100X6.3-S355J2 | RHS 150x100x6.3 S355J2 | 23.1 | kg/m | M | 150X100X6.3RHS, RHS150X100X6.3, RHS150X100X6.3-S355J2 |

## Suppliers

24 Corvus supplier codes and 63 finance accounts were blocked on the first normalised token
and 109 pairs scored with rapidfuzz. Accepted links form 63 supplier entities.
2 entities hold more than one Corvus code and 3 hold more than one finance account: duplicates that exist today.

Finance accounts with no Corvus counterpart are expected: subcontractors, hauliers and overheads are
paid through finance but never appear on a Corvus steel purchase order.

### Review queue

One item per pair of supplier entities; approving it settles every record pair between them.

| Item | Entity A | Entity B | Best score | Evidence | Suggested action |
| --- | --- | --- | --- | --- | --- |
| SR001 | corvus_mrp:S0025, finance:AIR001 | corvus_mrp:S0034 | 88.9 | both codes' POs invoiced under AIR001 | approve merge: invoices corroborate |
| SR002 | finance:HUM003 | corvus_mrp:S0022, finance:HUM001, finance:HUM002 | 81.5 | 0 of S0022's 57 POs invoiced under HUM003 | check VAT number, address and bank details |
| SR003 | finance:TEE004 | corvus_mrp:S0073, finance:TEE001 | 90.0 | 0 of S0073's 71 POs invoiced under TEE004 | check VAT number, address and bank details |
| SR004 | corvus_mrp:S0021 | corvus_mrp:S0013, finance:TYN001 | 82.1 | 31 of S0021's 35 POs invoiced under TYN001 | approve merge: invoices corroborate |

### Duplicate entities found

| Entity | Canonical name | Corvus codes | Finance accounts |
| --- | --- | --- | --- |
| SUP0009 | Calder Metals Limited | S0040, S0043 | CAL001 |
| SUP0023 | Humber Steels Ltd | S0022 | HUM001, HUM002 |
| SUP0035 | Northern Hollow Sections Ltd | S0082, S0089 | NOR001 |
| SUP0036 | Northgate Steelworks Ltd | S0113 | NOR002, NOR003 |
| SUP0057 | Trent Plate and Sections Ltd | S0069 | TRE001, TRE002 |

### Likely missed: below the review floor but corroborated by invoices

These pairs score under the floor so they are never merged, but the invoices say they are the
same supplier. Name matching alone has limits; a steward should look at these.

| Record | Candidate | Score | Evidence |
| --- | --- | --- | --- |
| MERSEY TUBE | Mersey Tube and Section Ltd | 66.7 | 37 of S0094's 44 POs invoiced under MER001 |

Corvus codes with no finance counterpart at or above the floor:

| Code | Name | Best candidate | Score |
| --- | --- | --- | --- |
| S0094 | MERSEY TUBE | finance:MER001 | 66.7 |

## Jobs

150 Corvus jobs: 150 have a finance job code and 149 are referenced on shop-floor delivery notes. 20 finance job codes have no Corvus job.

| Method | Status | Values | Rows |
| --- | --- | --- | --- |
| derived_key | auto | 150 | 3471 |
| job_of_record | auto | 150 | 860 |
| exact | auto | 125 | 244 |
| case_normalised | auto | 89 | 129 |
| missing_prefix | auto | 86 | 126 |
| missing_hyphen | auto | 79 | 117 |
| zero_padding_restored | auto | 75 | 101 |
| derived_key_not_found | unmatched | 20 | 123 |

Unmatched, by side:

| Side | Reason | Values |
| --- | --- | --- |
| corvus_mrp | no shop-floor delivery note | 1 |
| finance | finance code with no Corvus job | 20 |

Finance codes with no Corvus job: `23754`, `23772`, `23812`, `23818`, `23837`, `23841`, `23849`, `23857`, `23877`, `23885`, `23888`, `23955`, `23956`, `23969`, `23989`, `24662`, `24686`, `24707`, `24716`, `24820`.

## Works orders

3,473 distinct ways a works order is written on time bookings and NCRs. 0 could not be parsed; 22 parse to a number Corvus does not hold.

| Method | Status | Values | Rows |
| --- | --- | --- | --- |
| wo_prefix | auto | 1978 | 6338 |
| bare_number | auto | 813 | 4311 |
| revision_suffix | auto | 660 | 2114 |
| wo_prefix_not_in_corvus | review | 12 | 21 |
| bare_number_not_in_corvus | review | 6 | 19 |
| revision_suffix_not_in_corvus | review | 4 | 6 |

Numbers not in Corvus MRP: 11000, 14088, 16011, 16056, 17049, 18019.

### Transposition candidates for review

| Item | Number | Written as | Rows | Candidate | Job | Site matches | Dates fit | Suggested action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| WR001 | 11000 | 11000, WO 11000, WO11000, wo-11000 | 8 | 10100 | J-24-0867 | False | False | weak candidate: ask the supervisor which job this was |
| WR002 | 14088 | 14088, 14088 (rev B), wo-14088 | 6 | 10488 | J-25-0159 | False | True | weak candidate: ask the supervisor which job this was |
| WR003 | 16011 | 16011, WO 16011, WO16011 | 6 | 10611 | J-26-0102 | True | False | weak candidate: ask the supervisor which job this was |
| WR004 | 16056 | 16056, 16056 (rev B), WO 16056, WO16056, wo-16056 | 9 | 10656 | J-26-0111 | False | False | weak candidate: ask the supervisor which job this was |
| WR005 | 17049 | 17049, 17049 (rev B), wo-17049 | 8 | 10749 | J-26-0129 | False | False | weak candidate: ask the supervisor which job this was |
| WR006 | 18019 | 18019, 18019 (rev B), WO 18019, wo-18019 | 9 | 10819 | J-26-0140 | False | False | weak candidate: ask the supervisor which job this was |

# Source profiling report

**All data profiled here is synthetic.** It is generated for the FabSync demonstrator and represents
no real company, person, supplier or transaction.

Produced by `make ingest` from the raw layer of the warehouse, before any cleaning. Every figure is also
queryable in `governance.profile_table`, `governance.profile_column` and `governance.profile_anomaly`.

Every source file opens with a SYNTHETIC DATA header comment. The raw layer records it, with the
file's SHA-256, in `governance.source_file`.

Inferred type is what a naive loader would guess from the values as received. A mismatch means that
guess disagrees with the contract, so loading without a contract would mistype the column.

## Summary

| System | Table | Rows | Blank cells | Exact duplicates | Duplicate keys | Type mismatches | Anomalies |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Corvus MRP (MRPII) | `works_orders` | 860 | 135 (1.1%) | 0 | 0 | 0 | 4 |
| Corvus MRP (MRPII) | `bom_lines` | 5,933 | 0 (0.0%) | 0 | 0 | 0 | 4 |
| Corvus MRP (MRPII) | `stock` | 106 | 0 (0.0%) | 0 | 0 | 0 | 4 |
| Corvus MRP (MRPII) | `purchase_orders` | 1,104 | 0 (0.0%) | 0 | 0 | 0 | 3 |
| Corvus MRP (MRPII) | `goods_received` | 989 | 209 (2.6%) | 0 | 0 | 0 | 4 |
| Finance system | `purchase_invoices` | 1,780 | 1,122 (6.3%) | 0 | 0 | 3 | 3 |
| Finance system | `sales_invoices` | 559 | 0 (0.0%) | 0 | 0 | 1 | 1 |
| Finance system | `job_costs` | 1,515 | 0 (0.0%) | 0 | 0 | 1 | 1 |
| Finance system | `supplier_master` | 63 | 0 (0.0%) | 0 | 0 | 0 | 0 |
| Shop-floor spreadsheets | `time_bookings` | 12,732 | 664 (0.7%) | 151 | 3 | 2 | 10 |
| Shop-floor spreadsheets | `delivery_notes` | 729 | 85 (1.7%) | 7 | 0 | 2 | 8 |
| Shop-floor spreadsheets | `ncr_log` | 254 | 123 (6.9%) | 4 | 0 | 2 | 8 |
| Shop-floor spreadsheets | `weekly_capacity` | 212 | 8 (0.9%) | 0 | 0 | 0 | 2 |

## What staging did with it

Every row that left the raw layer is either in staging or in quarantine. `governance.table_balance` holds this table; `governance.quarantine` holds each rejected row with its original values.

| Source file | Raw rows | Staged | Quarantined | Balanced |
| --- | ---: | ---: | ---: | :---: |
| `corvus_mrp/bom_lines.csv` | 5,933 | 5,933 | 0 | yes |
| `corvus_mrp/goods_received.csv` | 989 | 989 | 0 | yes |
| `corvus_mrp/purchase_orders.csv` | 1,104 | 1,104 | 0 | yes |
| `corvus_mrp/stock.csv` | 106 | 106 | 0 | yes |
| `corvus_mrp/works_orders.csv` | 860 | 860 | 0 | yes |
| `finance/job_costs.csv` | 1,515 | 1,515 | 0 | yes |
| `finance/purchase_invoices.csv` | 1,780 | 1,780 | 0 | yes |
| `finance/sales_invoices.csv` | 559 | 559 | 0 | yes |
| `finance/supplier_master.csv` | 63 | 63 | 0 | yes |
| `shop_floor/delivery_notes.csv` | 729 | 717 | 12 | yes |
| `shop_floor/ncr_log.csv` | 254 | 246 | 8 | yes |
| `shop_floor/time_bookings.csv` | 12,732 | 12,563 | 169 | yes |
| `shop_floor/weekly_capacity.csv` | 212 | 212 | 0 | yes |

| Source file | Rule | Column | Rows |
| --- | --- | --- | ---: |
| `shop_floor/delivery_notes.csv` | ST-02 Exact duplicate row: first occurrence kept, repeats quarantined | (whole row) | 7 |
| `shop_floor/delivery_notes.csv` | ST-04 Date must parse with one of the declared formats | promised_date | 3 |
| `shop_floor/delivery_notes.csv` | ST-05 Numeric must coerce after removing thousands separators, currency symbols and spaces | tonnage | 2 |
| `shop_floor/ncr_log.csv` | ST-02 Exact duplicate row: first occurrence kept, repeats quarantined | (whole row) | 4 |
| `shop_floor/ncr_log.csv` | ST-04 Date must parse with one of the declared formats | raised_date | 1 |
| `shop_floor/ncr_log.csv` | ST-05 Numeric must coerce after removing thousands separators, currency symbols and spaces | cost_impact | 3 |
| `shop_floor/time_bookings.csv` | ST-02 Exact duplicate row: first occurrence kept, repeats quarantined | (whole row) | 151 |
| `shop_floor/time_bookings.csv` | ST-03 Required column must not be blank | works_order | 4 |
| `shop_floor/time_bookings.csv` | ST-04 Date must parse with one of the declared formats | booking_date | 5 |
| `shop_floor/time_bookings.csv` | ST-05 Numeric must coerce after removing thousands separators, currency symbols and spaces | hours | 6 |
| `shop_floor/time_bookings.csv` | ST-08 Natural key must be unique: first occurrence kept, repeats quarantined | booking_id | 3 |

## Corvus MRP (MRPII)

- text case: UPPERCASE
- dates: DD/MM/YYYY
- padding: fixed-width fields, trailing spaces
- units: EA, M, KG
- supplier master: none; names typed on each purchase order

### `works_orders`

File `corvus_mrp/works_orders.csv`, 860 rows. Natural key: wo_no.

| # | Column | Declared | Inferred | Blank | Distinct | Anomalies |
| ---: | --- | --- | --- | ---: | ---: | ---: |
| 1 | `wo_no` | integer | integer | 0.0% | 860 |  |
| 2 | `job_no` | text | text | 0.0% | 150 |  |
| 3 | `customer_ref` | text | text | 0.0% | 150 | 1 |
| 4 | `part_code` | text | text | 0.0% | 52 | 1 |
| 5 | `description` | text | text | 0.0% | 332 | 1 |
| 6 | `qty` | integer | integer | 0.0% | 5 |  |
| 7 | `uom` | text | text | 0.0% | 1 |  |
| 8 | `planned_hours` | decimal | decimal | 0.0% | 654 |  |
| 9 | `planned_start` | date | date | 0.0% | 487 |  |
| 10 | `planned_finish` | date | date | 0.0% | 484 |  |
| 11 | `actual_finish` | date | date | 15.7% | 447 |  |
| 12 | `status` | text | text | 0.0% | 6 | 1 |
| 13 | `site` | text | text | 0.0% | 2 |  |
| 14 | `execution_class` | text | text | 0.0% | 2 |  |

| Column | Anomaly | Values | Sample |
| --- | --- | ---: | --- |
| `customer_ref` | leading or trailing whitespace | 860 | `"0196227        "`, `"PO718379       "`, `"0719227        "`, `"PO662544       "`, `"ORD-876396     "` |
| `part_code` | leading or trailing whitespace | 851 | `"B04            "`, `"B02            "`, `"C03            "`, `"C01            "`, `"B03            "` |
| `description` | leading or trailing whitespace | 859 | `"B04 FABRICATION               "`, `"B02 PAINTED FINISH            "`, `"C03 FABRICATION               "`, `"C01 FABRICATION               "`, `"B03 ASSEMBLY                  "` |
| `status` | leading or trailing whitespace | 860 | `"CLOSED    "`, `"OPEN      "`, `"COMPLETE  "`, `"CANCELLED "`, `"RELEASED  "` |

### `bom_lines`

File `corvus_mrp/bom_lines.csv`, 5,933 rows. Natural key: wo_no, line_no.

| # | Column | Declared | Inferred | Blank | Distinct | Anomalies |
| ---: | --- | --- | --- | ---: | ---: | ---: |
| 1 | `wo_no` | integer | integer | 0.0% | 860 |  |
| 2 | `line_no` | integer | integer | 0.0% | 11 |  |
| 3 | `material_code` | text | text | 0.0% | 81 | 2 |
| 4 | `description` | text | text | 0.0% | 114 | 2 |
| 5 | `section_type` | text | text | 0.0% | 9 |  |
| 6 | `grade` | text | text | 0.0% | 3 |  |
| 7 | `length_mm` | integer | integer | 0.0% | 11 |  |
| 8 | `qty` | decimal | decimal | 0.0% | 829 |  |
| 9 | `uom` | text | text | 0.0% | 2 |  |
| 10 | `unit_weight_kg` | decimal | decimal | 0.0% | 40 |  |

| Column | Anomaly | Values | Sample |
| --- | --- | ---: | --- |
| `material_code` | leading or trailing whitespace | 5,487 | `"152X152X23UC        "`, `"L50X50X6-S275JR     "`, `"RHS100X50X4-S355J2  "`, `"PLT10-S355J2        "`, `"PL25MM              "` |
| `material_code` | not in canonical form | 1,001 | `"152X152X23UC"`, `"PL25MM"`, `"254X146X31UB"`, `"UC254X254X73"`, `"PFC260X75X28"` |
| `description` | leading or trailing whitespace | 5,933 | `"152x152x23UC                  "`, `"L 50X50X6 S275JR              "`, `"RHS 100X50X4 S355J2           "`, `"PLATE 10MM S355J2             "`, `"PLATE 25MM S355J2             "` |
| `description` | same value written with different case or spacing | 1,536 | `"CHS 114.3X5 S355J2" / "CHS 114.3x5 S355J2"`, `"L 150X90X12 S355J0" / "L 150x90x12 S355J0"`, `"L 75X75X8 S355J0" / "L 75x75x8 S355J0"` |

### `stock`

File `corvus_mrp/stock.csv`, 106 rows. Natural key: material_code, site, location.

| # | Column | Declared | Inferred | Blank | Distinct | Anomalies |
| ---: | --- | --- | --- | ---: | ---: | ---: |
| 1 | `material_code` | text | text | 0.0% | 72 | 2 |
| 2 | `description` | text | text | 0.0% | 71 | 1 |
| 3 | `location` | text | text | 0.0% | 8 | 1 |
| 4 | `site` | text | text | 0.0% | 2 |  |
| 5 | `qty_on_hand` | decimal | decimal | 0.0% | 98 |  |
| 6 | `uom` | text | text | 0.0% | 3 |  |
| 7 | `unit_cost` | decimal | decimal | 0.0% | 64 |  |
| 8 | `last_count_date` | date | date | 0.0% | 82 |  |
| 9 | `counted_qty` | decimal | decimal | 0.0% | 98 |  |

| Column | Anomaly | Values | Sample |
| --- | --- | ---: | --- |
| `material_code` | leading or trailing whitespace | 99 | `"UB203X133X25-S275JR "`, `"203X133X25UB        "`, `"UB203X133X25-S355J2 "`, `"UB254X146X31-S275JR "`, `"254X146X31UB        "` |
| `material_code` | not in canonical form | 18 | `"203X133X25UB"`, `"254X146X31UB"`, `"UB305X165X40"`, `"UB406X178X60"`, `"152X152X23UC"` |
| `description` | leading or trailing whitespace | 106 | `"UB 203X133X25 S275JR          "`, `"UNIV BEAM 203X133X25          "`, `"UB 203X133X25 S355J2          "`, `"UB 254X146X31 S275JR          "`, `"UNIV BEAM 254X146X31          "` |
| `location` | leading or trailing whitespace | 106 | `"RACK A1     "`, `"RACK B2     "`, `"YARD        "`, `"BAY 4       "`, `"RACK A3     "` |

### `purchase_orders`

File `corvus_mrp/purchase_orders.csv`, 1,104 rows. Natural key: po_no.

| # | Column | Declared | Inferred | Blank | Distinct | Anomalies |
| ---: | --- | --- | --- | ---: | ---: | ---: |
| 1 | `po_no` | text | text | 0.0% | 1,104 |  |
| 2 | `supplier_code` | text | text | 0.0% | 24 |  |
| 3 | `supplier_name` | text | text | 0.0% | 24 | 1 |
| 4 | `material_code` | text | text | 0.0% | 80 | 2 |
| 5 | `qty` | decimal | decimal | 0.0% | 1,053 |  |
| 6 | `uom` | text | text | 0.0% | 2 |  |
| 7 | `unit_price` | decimal | decimal | 0.0% | 593 |  |
| 8 | `order_date` | date | date | 0.0% | 529 |  |
| 9 | `promised_date` | date | date | 0.0% | 576 |  |

| Column | Anomaly | Values | Sample |
| --- | --- | ---: | --- |
| `supplier_name` | leading or trailing whitespace | 1,104 | `"OUSE STEEL SERVICES LTD       "`, `"AIRE VALLEY STEELS            "`, `"CALDER METALS                 "`, `"TYNE STEEL STOCK              "`, `"DERWENT STEELS LTD            "` |
| `material_code` | leading or trailing whitespace | 1,015 | `"L150X90X12-S355J0   "`, `"L50X50X6-S275JR     "`, `"L75X75X8-S275JR     "`, `"L75X75X8            "`, `"PFC100X50X10-S275JR "` |
| `material_code` | not in canonical form | 130 | `"L75X75X8"`, `"UB203X133X25"`, `"114.3X5CHS"`, `"100X50X10PFC"`, `"PFC260X75X28"` |

### `goods_received`

File `corvus_mrp/goods_received.csv`, 989 rows. Natural key: grn_no.

| # | Column | Declared | Inferred | Blank | Distinct | Anomalies |
| ---: | --- | --- | --- | ---: | ---: | ---: |
| 1 | `grn_no` | text | text | 0.0% | 989 |  |
| 2 | `po_no` | text | text | 0.0% | 989 |  |
| 3 | `material_code` | text | text | 0.0% | 80 | 2 |
| 4 | `qty_received` | decimal | decimal | 0.0% | 936 |  |
| 5 | `uom` | text | text | 0.0% | 2 |  |
| 6 | `received_date` | date | date | 0.0% | 554 |  |
| 7 | `heat_number` | text | text | 10.4% | 886 | 1 |
| 8 | `mill_cert_ref` | text | text | 10.7% | 881 | 1 |

| Column | Anomaly | Values | Sample |
| --- | --- | ---: | --- |
| `material_code` | leading or trailing whitespace | 908 | `"L150X90X12-S355J0   "`, `"L50X50X6-S275JR     "`, `"L75X75X8-S275JR     "`, `"L75X75X8            "`, `"PFC100X50X10-S275JR "` |
| `material_code` | not in canonical form | 116 | `"L75X75X8"`, `"UB203X133X25"`, `"114.3X5CHS"`, `"100X50X10PFC"`, `"PFC260X75X28"` |
| `heat_number` | leading or trailing whitespace | 886 | `"339324    "`, `"449693    "`, `"H700618   "`, `"25A9163   "`, `"892434    "` |
| `mill_cert_ref` | leading or trailing whitespace | 883 | `"MC/2024/66653 "`, `"MC/2024/51643 "`, `"MC/2024/42333 "`, `"MC/2024/10386 "`, `"MC/2024/58202 "` |

## Finance system

- text case: Title Case
- dates: YYYY-MM-DD
- amounts: some stored as text with thousands separators
- job codes: YY + sequence without leading zeros, e.g. 24871

### `purchase_invoices`

File `finance/purchase_invoices.csv`, 1,780 rows. Natural key: invoice_no.

| # | Column | Declared | Inferred | Blank | Distinct | Anomalies |
| ---: | --- | --- | --- | ---: | ---: | ---: |
| 1 | `invoice_no` | text | text | 0.0% | 1,780 |  |
| 2 | `supplier_account` | text | text | 0.0% | 63 |  |
| 3 | `supplier_name` | text | text | 0.0% | 63 |  |
| 4 | `po_reference` | text | text | 48.4% | 919 |  |
| 5 | `net_amount` | decimal | **text** | 0.0% | 1,779 | 1 |
| 6 | `vat` | decimal | **text** | 0.0% | 1,768 | 1 |
| 7 | `gross` | decimal | **text** | 0.0% | 1,780 | 1 |
| 8 | `invoice_date` | date | date | 0.0% | 658 |  |
| 9 | `nominal_code` | text | integer | 0.0% | 11 |  |
| 10 | `job_code` | text | integer | 14.6% | 167 |  |

| Column | Anomaly | Values | Sample |
| --- | --- | ---: | --- |
| `net_amount` | number stored as text (separators, currency or spaces) | 414 | `"2,029.56"`, `"1,174.14"`, `"1,185.83"`, `"1,426.61"`, `"2,547.74"` |
| `vat` | number stored as text (separators, currency or spaces) | 138 | `"1,455.61"`, `"1,977.12"`, `"1,091.30"`, `"2,910.89"`, `"2,137.23"` |
| `gross` | number stored as text (separators, currency or spaces) | 462 | `"1,422.99"`, `"2,373.95"`, `"2,139.00"`, `"1,052.37"`, `"3,127.12"` |

### `sales_invoices`

File `finance/sales_invoices.csv`, 559 rows. Natural key: invoice_no.

| # | Column | Declared | Inferred | Blank | Distinct | Anomalies |
| ---: | --- | --- | --- | ---: | ---: | ---: |
| 1 | `customer_account` | text | text | 0.0% | 38 |  |
| 2 | `customer_name` | text | text | 0.0% | 38 |  |
| 3 | `job_code` | text | integer | 0.0% | 170 |  |
| 4 | `net_amount` | decimal | **text** | 0.0% | 559 | 1 |
| 5 | `invoice_date` | date | date | 0.0% | 359 |  |
| 6 | `invoice_no` | text | text | 0.0% | 559 |  |

| Column | Anomaly | Values | Sample |
| --- | --- | ---: | --- |
| `net_amount` | number stored as text (separators, currency or spaces) | 151 | `"13,244.83"`, `"13,380.59"`, `"36,211.72"`, `"10,706.22"`, `"9,898.01"` |

### `job_costs`

File `finance/job_costs.csv`, 1,515 rows. Natural key: job_code, cost_type, period.

| # | Column | Declared | Inferred | Blank | Distinct | Anomalies |
| ---: | --- | --- | --- | ---: | ---: | ---: |
| 1 | `job_code` | text | integer | 0.0% | 169 |  |
| 2 | `cost_type` | text | text | 0.0% | 4 |  |
| 3 | `period` | text | text | 0.0% | 26 |  |
| 4 | `amount` | decimal | **text** | 0.0% | 1,512 | 1 |

| Column | Anomaly | Values | Sample |
| --- | --- | ---: | --- |
| `amount` | number stored as text (separators, currency or spaces) | 462 | `"2,602.17"`, `"1,427.73"`, `"1,126.67"`, `"1,750.79"`, `"2,218.55"` |

### `supplier_master`

File `finance/supplier_master.csv`, 63 rows. Natural key: supplier_account.

| # | Column | Declared | Inferred | Blank | Distinct | Anomalies |
| ---: | --- | --- | --- | ---: | ---: | ---: |
| 1 | `supplier_account` | text | text | 0.0% | 63 |  |
| 2 | `supplier_name` | text | text | 0.0% | 63 |  |
| 3 | `payment_terms` | text | text | 0.0% | 4 |  |
| 4 | `currency` | text | text | 0.0% | 2 |  |

No anomalies.

## Shop-floor spreadsheets

- text case: mixed, with typos
- dates: DD/MM/YYYY, YYYY-MM-DD and DD-Mon-YY in the same column
- works order: free text: WO 12345, wo-12345, 12345, 12345 (rev B)
- blanks: common
- duplicates: copy-and-paste repeats

### `time_bookings`

File `shop_floor/time_bookings.csv`, 12,732 rows. Natural key: booking_id.

| # | Column | Declared | Inferred | Blank | Distinct | Anomalies |
| ---: | --- | --- | --- | ---: | ---: | ---: |
| 1 | `booking_id` | integer | integer | 0.0% | 12,578 |  |
| 2 | `operator` | text | text | 2.2% | 37 |  |
| 3 | `works_order` | text | text | 0.0% | 3,237 | 2 |
| 4 | `operation` | text | text | 3.0% | 31 | 1 |
| 5 | `hours` | decimal | **text** | 0.0% | 599 | 2 |
| 6 | `booking_date` | date | **text** | 0.0% | 2,042 | 2 |
| 7 | `site` | text | text | 0.0% | 10 | 1 |

| Column | Anomaly | Values | Sample |
| --- | --- | ---: | --- |
| `(row)` | exact duplicate rows | 151 | `{"booking_id": "500148"}`, `{"booking_id": "500895"}`, `{"booking_id": "500235"}` |
| `(row)` | duplicate natural key (booking_id) with differing values | 3 |  |
| `works_order` | blank in required column | 4 |  |
| `works_order` | not in canonical form | 8,424 | `"WO 10008"`, `"wo-10001"`, `"WO10001"`, `"WO 10001"`, `"WO10013"` |
| `operation` | same value written with different case or spacing | 8,326 | `"BLAST" / "Blast"`, `"DRILL" / "Drill"`, `"FIT" / "Fit"` |
| `hours` | leading or trailing whitespace | 1,935 | `"1.6 "`, `" 4"`, `"6.0 "`, `"9.5 "`, `"5.0 "` |
| `hours` | not a number | 6 | `"4hrs"`, `"7,5"`, `"half day"`, `"7.5."`, `"3,25"` |
| `booking_date` | mixed date formats (DD/MM/YYYY 4,279, YYYY-MM-DD 4,271, DD-Mon-YY 4,177); count is values outside the most common format | 8,448 |  |
| `booking_date` | not a valid date | 5 | `"w/c 03/03"`, `"31/02/2025"`, `"30-Feb-25"`, `"TBC"`, `"2025-13-02"` |
| `site` | same value written with different case or spacing | 5,079 | `"Teesside" / "teesside"`, `"Wakefield" / "wakefield"` |

### `delivery_notes`

File `shop_floor/delivery_notes.csv`, 729 rows. Natural key: dn_no.

| # | Column | Declared | Inferred | Blank | Distinct | Anomalies |
| ---: | --- | --- | --- | ---: | ---: | ---: |
| 1 | `dn_no` | text | text | 0.0% | 722 |  |
| 2 | `job` | text | text | 0.0% | 456 | 2 |
| 3 | `customer` | text | text | 0.0% | 150 | 1 |
| 4 | `despatch_date` | date | date | 0.0% | 605 | 1 |
| 5 | `promised_date` | date | **text** | 4.3% | 572 | 2 |
| 6 | `tonnage` | decimal | **text** | 2.6% | 497 | 1 |
| 7 | `vehicle` | text | text | 4.8% | 403 |  |

| Column | Anomaly | Values | Sample |
| --- | --- | ---: | --- |
| `(row)` | exact duplicate rows | 7 | `{"dn_no": "DN7209"}`, `{"dn_no": "DN7219"}`, `{"dn_no": "DN7625"}` |
| `job` | same value written with different case or spacing | 253 | `"J-24-0851" / "j-24-0851"`, `"J-24-0852" / "j-24-0852"`, `"J-24-0853" / "j-24-0853"` |
| `job` | not in canonical form | 482 | `"J24-0851"`, `"24-0851"`, `"j-24-0851"`, `"J-24-851"`, `"J-24-852"` |
| `customer` | same value written with different case or spacing | 396 | `"Aerial Sites UK" / "aerial sites uk"`, `"Ashcroft Build" / "ashcroft build"`, `"Beacon Mast Services" / "beacon mast services"` |
| `despatch_date` | mixed date formats (DD/MM/YYYY 236, YYYY-MM-DD 241, DD-Mon-YY 252); count is values outside the most common format | 477 |  |
| `promised_date` | mixed date formats (DD/MM/YYYY 197, YYYY-MM-DD 253, DD-Mon-YY 245); count is values outside the most common format | 442 |  |
| `promised_date` | not a valid date | 3 | `"ASAP"`, `"TBC"`, `"end of week"` |
| `tonnage` | not a number | 2 | `"approx 3"`, `"2.4t"` |

### `ncr_log`

File `shop_floor/ncr_log.csv`, 254 rows. Natural key: ncr_no.

| # | Column | Declared | Inferred | Blank | Distinct | Anomalies |
| ---: | --- | --- | --- | ---: | ---: | ---: |
| 1 | `ncr_no` | text | text | 0.0% | 250 |  |
| 2 | `works_order` | text | text | 0.0% | 241 | 1 |
| 3 | `raised_date` | date | **text** | 0.0% | 242 | 2 |
| 4 | `category` | text | text | 0.0% | 14 | 1 |
| 5 | `description` | text | text | 0.0% | 155 |  |
| 6 | `cost_impact` | decimal | **text** | 18.1% | 196 | 2 |
| 7 | `closed_date` | date | date | 30.3% | 168 | 1 |

| Column | Anomaly | Values | Sample |
| --- | --- | ---: | --- |
| `(row)` | exact duplicate rows | 4 | `{"ncr_no": "NCR-1076"}`, `{"ncr_no": "NCR-1083"}`, `{"ncr_no": "NCR-1180"}` |
| `works_order` | not in canonical form | 165 | `"WO 10696"`, `"10663 (rev B)"`, `"10811 (rev B)"`, `"10501 (rev B)"`, `"WO10150"` |
| `raised_date` | mixed date formats (DD/MM/YYYY 94, YYYY-MM-DD 76, DD-Mon-YY 83); count is values outside the most common format | 159 |  |
| `raised_date` | not a valid date | 1 | `"?"` |
| `category` | same value written with different case or spacing | 254 | `"Damage in transit" / "damage in transit"`, `"Dimensional error" / "dimensional error"`, `"Galvanising defect" / "galvanising defect"` |
| `cost_impact` | number stored as text (separators, currency or spaces) | 51 | `"£2,333"`, `"£125"`, `"£495"`, `"£245"`, `"£805"` |
| `cost_impact` | not a number | 3 | `"tbc"`, `"n/a"`, `"see QA"` |
| `closed_date` | mixed date formats (DD/MM/YYYY 64, YYYY-MM-DD 56, DD-Mon-YY 57); count is values outside the most common format | 113 |  |

### `weekly_capacity`

File `shop_floor/weekly_capacity.csv`, 212 rows. Natural key: week_commencing, site.

| # | Column | Declared | Inferred | Blank | Distinct | Anomalies |
| ---: | --- | --- | --- | ---: | ---: | ---: |
| 1 | `week_commencing` | date | date | 0.0% | 179 | 1 |
| 2 | `site` | text | text | 0.0% | 10 | 1 |
| 3 | `available_hours` | decimal | decimal | 0.0% | 190 |  |
| 4 | `booked_hours` | decimal | decimal | 3.8% | 200 |  |

| Column | Anomaly | Values | Sample |
| --- | --- | ---: | --- |
| `week_commencing` | mixed date formats (DD/MM/YYYY 81, YYYY-MM-DD 56, DD-Mon-YY 75); count is values outside the most common format | 131 |  |
| `site` | same value written with different case or spacing | 97 | `"Teesside" / "teesside"`, `"Wakefield" / "wakefield"` |

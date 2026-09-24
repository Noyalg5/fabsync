# Integration design

**Demonstration prototype. All data is synthetic.** The company, its systems' contents and every
record referred to here are invented for the FabSync demonstrator.

This document sets out how Corvus MRP, the finance system and the new shop-floor forms will exchange
data in the target design (see `docs/diagrams/to-be-architecture.png`). It covers three things:

1. every **interface** between systems;
2. which system is the **system of record** for each kind of data;
3. how conflicts between copies are settled.

It is written for managers who run the business, not for programmers. Every technical term is
explained the first time it appears.

## Terms used

- An **interface** is a regular, agreed movement of one kind of data from one system to another.
  An example is "every night, Corvus sends yesterday's goods received notes to the warehouse".
- The **system of record** for a kind of data is the one system where that data is created and
  corrected. Every other system holds a copy. If the copies disagree, the system of record is
  right unless a rule below says otherwise.
- **Master data** is the reference data that many transactions share: materials, suppliers,
  customers, jobs and works orders. **Transactional data** is the day-to-day activity recorded
  against it, such as orders, receipts, bookings and invoices.
- A **golden record** is the single agreed version of one piece of master data, such as one
  supplier. It is built from all the systems' copies using the rules in this document, and keeps a
  note of which system each field came from.
- A **crosswalk** is a translation table that lists every way a thing is written in each system
  against its golden record. For example, finance job 24871 and Corvus job J-24-0871 are the same
  job.
- The **integration layer** is the set of scheduled jobs that collect data from each system. It
  checks each record against its agreed layout, sets aside records that fail, and passes the rest
  on. In FabSync this is the ingestion stage.
- The **master data service** holds the golden records and crosswalks, and runs the review queue
  where a person decides uncertain matches. In FabSync this is the matching stage.
- A **nightly extract** is a file one system writes out each night for another to pick up. It is
  the simplest and most robust mechanism, and the one Corvus, installed in 2006, can support.
- A **form** is a screen where a person enters data directly. It replaces a spreadsheet, and it
  can refuse bad entries at the point of entry.
- **Quarantine** is where a record that fails a check is held, with its original values untouched,
  until someone corrects it at source. Nothing is silently dropped.
- **Lineage** is the record of where each figure came from: which file, which line and which rules
  touched it.

## Interface inventory

Each interface has an owner: the data owner who answers for it being complete and on time. The
**failure mode** says what goes wrong if the interface fails, and what the design does about it.

| ID | Source system | Target system | Direction | Entity | Frequency | Mechanism | Owner | Failure mode |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| IF-01 | Corvus MRP | Integration layer | One way | Works orders and bills of material | Nightly | Extract file | Production Controller | File missing or layout changed: the load stops, yesterday's data stays in use, and the owner is told the next morning. No partial load. |
| IF-02 | Corvus MRP | Integration layer | One way | Stock and cycle counts | Nightly | Extract file | Production Controller | File missing: stock figures are shown with their "as at" date so nobody mistakes old for current. |
| IF-03 | Corvus MRP | Integration layer | One way | Purchase orders and goods received notes, with heat number and certificate reference | Nightly | Extract file | Purchasing Manager (orders); Quality Manager (receipts) | Receipt with no heat number or certificate: loaded, but raised the same day as a critical exception to the Quality Manager. |
| IF-04 | Corvus MRP | Integration layer | One way | Material issues to works orders (new) | Nightly | Extract file | Production Controller | Issue against a heat number never received: quarantined, and the stores supervisor corrects it in Corvus. |
| IF-05 | Finance system | Integration layer | One way | Purchase invoices | Nightly | Extract file | Finance Manager | Invoice with no purchase order outside overheads: loaded and put in the exception queue. A duplicate invoice number is quarantined. |
| IF-06 | Finance system | Integration layer | One way | Sales invoices and applications for payment | Nightly | Extract file | Finance Manager | Invoice on a job code with no Corvus job: loaded, flagged unmatched, and listed for the Finance Manager. |
| IF-07 | Finance system | Integration layer | One way | Job cost ledger | Nightly, and at period end | Extract file | Finance Manager | Cost on an unknown job: flagged, and shown in the job cost reconciliation as finance-only cost. |
| IF-08 | Finance system | Integration layer | One way | Supplier accounts | Nightly | Extract file | Finance Manager | New account not in the master data service: sent to the review queue before any payment is made to it. |
| IF-09 | Shop-floor forms | Integration layer | One way | Time bookings | As entered, collected every 15 minutes | Form | Production Controller | Form unavailable: bookings go on the paper fallback sheet, are keyed the next day, and are marked as late entries. |
| IF-10 | Shop-floor forms | Integration layer | One way | Delivery notes | As entered | Form | Production Controller | A delivery note cannot be saved without a works order, tonnage and promised date, so the old gaps cannot recur. |
| IF-11 | Shop-floor forms | Integration layer | One way | Non-conformance reports (NCRs) | As entered | Form | Quality Manager | NCR saved without a cost is marked "estimate pending", and the Quality Manager is reminded after seven days. |
| IF-12 | Shop-floor forms | Integration layer | One way | Weekly capacity | Weekly | Form | Production Controller | A missing week shows as a gap, not as zero, so utilisation is not understated. |
| IF-13 | Master data service | Corvus MRP | One way | Approved material codes, supplier ordering codes, blocks on retired codes | Daily, after approval | Import file where Corvus accepts one; otherwise the steward keys from the approved change list | Purchasing Manager | A code keyed differently from the approval is caught by the next night's matching and returns to the review queue. |
| IF-14 | Master data service | Finance system | One way | Approved supplier accounts; job code crosswalk | Daily, after approval | Import file or keyed from the approved change list | Finance Manager | Bank details are never sent by this route. Changes to them follow the finance dual-signature control. |
| IF-15 | Master data service | Shop-floor forms | One way | Live works orders and jobs for the pick lists | Every 15 minutes | Direct read | Production Controller | Pick list out of date: a newly released works order cannot be picked until the next refresh. The supervisor can ask for an immediate refresh. |
| IF-16 | Integration layer | Master data service | Both ways | Every incoming material, supplier, job and works order reference | Nightly, and as forms are entered | Direct read | Owner of the entity | Reference that cannot be matched: goes to the review queue. It is never guessed and never merged below the review threshold. |
| IF-17 | Integration layer and master data service | Data warehouse | One way | Checked data, golden records, crosswalks, lineage and quarantine | Nightly, after all extracts have loaded | Database load | Finance Manager | Load fails: the warehouse keeps the previous night's version complete, and never a half-loaded one. Reports show their "as at" date. |
| IF-18 | Data warehouse | Reporting and data owners | One way | KPIs, data quality scorecard, reconciliations, exception and review queues | Daily; KPI pack monthly | Direct query | Each data owner for their queue | A queue not worked for two weeks triggers the escalation route in `docs/data-ownership.md`. |

## System of record per entity

| Entity | System of record | Copies held in | Notes |
| --- | --- | --- | --- |
| Material, meaning section, grade and plate | Master data service (golden record), issued to Corvus MRP | Corvus MRP, warehouse | Corvus keeps its codes, but only codes the master data service has approved. |
| Supplier | Finance system for the legal entity, payment terms and bank details; master data service for the golden record and crosswalk | Corvus MRP (ordering code), warehouse | Corvus ordering codes map to one finance account. |
| Customer | Finance system (the invoicing entity) | Corvus MRP (order reference), warehouse | |
| Job | Corvus MRP (the job number J-YY-NNNN) | Finance system (job code via the crosswalk), shop-floor forms, warehouse | A finance job code cannot be used until it is in the crosswalk. |
| Works order and bill of material | Corvus MRP | Shop-floor forms (pick list), warehouse | |
| Purchase order | Corvus MRP | Finance system (reference on the invoice), warehouse | |
| Goods received note, heat number and mill certificate reference | Corvus MRP, keyed from the certificate | Warehouse | The paper or scanned certificate is the evidence. The Corvus record points to it. |
| Material issue (new) | Corvus MRP | Warehouse | This is what makes the receipt-to-job link a record rather than an inference. |
| Stock and cycle count | Corvus MRP | Warehouse | |
| Supplier invoice and payment | Finance system | Warehouse | |
| Sales invoice and application for payment | Finance system | Warehouse | |
| Job cost | Finance system, calculated from Corvus issues and shop-floor bookings | Warehouse | Finance posts it; operational records determine it. |
| Time booking | Shop-floor forms | Finance system (payroll allocation), warehouse | |
| Delivery note | Shop-floor forms | Finance system (invoicing), warehouse | |
| Non-conformance report | Shop-floor forms | Warehouse | |
| Weekly capacity | Shop-floor forms | Warehouse | |

## Golden record conflict resolution rules

When two systems hold different values for the same thing, these rules decide which value goes
into the golden record. The principle behind every rule is simple. **The system closest to the
physical event, or to the legal obligation, wins.** The steel's certificate beats a typed
reference. The payee's registered name beats a buyer's shorthand. Hours booked on the floor beat an
allocation made in the office.

Every value in a golden record keeps a note of which system it came from. The losing value is never
deleted; it stays in the crosswalk beside the winner.

| Entity | Field | Winner | Why |
| --- | --- | --- | --- |
| Material | Section type and dimensions | Parsed from the Corvus code and description; the code and description must agree | They are physical facts written in the designation; disagreement means a keying error, so the record goes to review. |
| Material | Grade | BOM grade column, then the code, then the description. Never inferred when the section is stocked in more than one grade | Grade is a structural safety fact. An order without one is resolved from the mill certificate by a person, not by the system. |
| Material | Mass per metre | Section catalogue, then the mass written in the designation, then the most common BOM figure | Published section tables are the engineering reference; typed weights drift. |
| Material | Stocking unit | Master data service (metres for sections, kilograms for plate) | One unit per material ends the kilogram, bar and metre confusion. Conversions are held beside it. |
| Supplier | Legal name, address, VAT number | Finance system | Finance deals with the legal entity that is paid. |
| Supplier | Bank details | Finance system, under dual signature only | The main fraud risk. No other system may change them, and no automatic match may either. |
| Supplier | Ordering code | Corvus MRP, mapped to the golden supplier | Buyers keep the code they use, but it must point at one supplier. |
| Supplier | Whether two records are the same supplier | Match score of 95 or more merges automatically; 80 to 95 goes to a person with the invoice evidence; below 80 never merges | A wrong merge can misdirect a payment, so doubt always goes to a person. |
| Customer | Name and invoicing address | Finance system | The invoice goes to the legal customer. |
| Customer | Site delivery address and contacts | Corvus MRP (contract) | Delivery details belong to the contract, not the ledger. |
| Job | Job number | Corvus MRP | The job exists to make something; Corvus plans the making. |
| Job | Finance job code | Crosswalk: two-digit year plus the sequence number (J-24-0871 becomes 24871) | A fixed rule removes re-keying; a finance code that does not fit the rule is unmatched until a person maps it. |
| Works order | Number | Corvus MRP | Shop-floor references must resolve to a live Corvus works order; a number that does not exist is never guessed. |
| Works order | Drawing revision on a booking | Shop-floor entry, kept beside the works order | Where supervisors note a revision, it is evidence for NCRs and is kept, not discarded. |
| Goods receipt | Heat number and certificate reference | The mill certificate itself, over anything typed | The certificate is the legal evidence; the typed value is a pointer to it. |
| Goods receipt | Quantity received | Goods-in count, over the delivery ticket, over the order | What physically arrived is what is paid for; differences beyond 2% go to the buyer. |
| Supplier invoice | Price | Purchase order price, within tolerance (the greater of 5% or £50) | Beyond tolerance, the invoice is held until the buyer agrees the difference. |
| Job cost | Labour | Shop-floor bookings at the standard rate | The hours were worked on the floor; a payroll allocation that differs by more than 5% is corrected, not averaged. |
| Job cost | Material | Corvus material issues, valued at the average price paid per kilogram | Steel belongs to the job it went into, not to the job the invoice happened to name. |
| Stock | Quantity | Physical recount, once a second count confirms the first | One count can be wrong; two agreeing counts are posted as an adjustment with a reason. |
| Delivery | Promised date | The contract or customer programme | A date typed on the delivery note is a copy; the promise was made in the contract. |

When a rule cannot settle a conflict, for example when a grade cannot be read from any source or a
supplier match sits in the review band, the item goes to the review queue and follows the escalation
route in `docs/data-ownership.md`.

## What FabSync already demonstrates

| Design element | Where it runs in the prototype |
| --- | --- |
| Integration layer: layout checks, quarantine, lineage | `make ingest`; the Governance page, Lineage and quarantine tab |
| Master data service: golden records, crosswalks, review queue | `make match`; the Master data page |
| Conflict rules for materials, suppliers, jobs and works orders | `src/fabsync/match/`; thresholds in `config/matching.toml` |
| Exception queues by owner | `make quality`; the Data quality page |
| Reconciliations that expose the conflicts' cost | `make reconcile`; the Reconciliation page |

Not built in the prototype: the shop-floor forms, material issue recording in Corvus, and the
return interfaces that send approved records back to Corvus and finance (IF-13 to IF-15). These
are phase 2 and 3 work in the roadmap.

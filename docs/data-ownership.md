# Data ownership

**Demonstration prototype. All data is synthetic.** The company and its people are invented. The
roles are the ones a fabricator of this size typically has.

This document says who is answerable for each kind of data, where it lives, and what happens when
two versions disagree and no rule can settle it. It goes with `docs/integration-design.md`, which
sets out the systems and the conflict rules.

## Terms used

- A **data owner** is the manager answerable for a kind of data being right. The owner sets its
  rules, accepts its risks and makes the final call on disputes within it. Owners are senior roles,
  not IT staff.
- A **data steward** is the person who does the day-to-day work on that data on the owner's
  behalf: working the review and exception queues, correcting records at source, and raising what
  they cannot settle.
- An **entity** is one kind of thing the business keeps records about, such as a supplier, a works
  order or a goods receipt.
- The **review queue** holds uncertain matches for a person to decide, such as "are these two
  supplier records the same company?". The **exception queue** holds records that break a data
  quality rule, such as "this receipt has no heat number".
- The **master data service** holds the one agreed version of each material, supplier, customer,
  job and works order. See `docs/integration-design.md`.

## Ownership matrix

In the system columns:

- **C** means the entity is **created and corrected** here. This is its system of record, and each
  entity has exactly one.
- **W** means a **working copy** used in day-to-day operations, which is kept in step
  automatically.
- **R** means a **read-only copy** used for reporting.
- **–** means the system does not hold it.

| Entity | Corvus MRP | Finance system | Shop-floor forms | Master data service | Warehouse | Owning role | Data steward |
| --- | :---: | :---: | :---: | :---: | :---: | --- | --- |
| Material (section, grade, plate) | W | – | – | C | R | Purchasing Manager | Buyer |
| Supplier | W (ordering code) | C (legal entity, bank details) | – | W (golden record, crosswalk) | R | Finance Manager | Purchase ledger clerk, with the buyer for ordering codes |
| Customer | W (order reference) | C | – | W (golden record) | R | Finance Manager | Sales ledger clerk |
| Job | C | W (job code via crosswalk) | W (pick list) | W (crosswalk) | R | Finance Manager | Production planner, with the management accountant for job codes |
| Works order and bill of material | C | – | W (pick list) | W (crosswalk) | R | Production Controller | Production planner |
| Purchase order | C | W (invoice reference) | – | – | R | Purchasing Manager | Buyer |
| Goods received note, heat number, mill certificate | C | – | – | – | R | Quality Manager | Goods-in supervisor |
| Material issue to works order | C | – | – | – | R | Production Controller | Stores supervisor |
| Stock and cycle count | C | – | – | – | R | Production Controller | Stores supervisor |
| Supplier invoice and payment | – | C | – | – | R | Finance Manager | Purchase ledger clerk |
| Sales invoice and application for payment | – | C | – | – | R | Finance Manager | Sales ledger clerk |
| Job cost | W (issues) | C | W (bookings) | – | R | Finance Manager | Management accountant |
| Time booking | – | W (payroll allocation) | C | – | R | Production Controller | Site supervisors |
| Delivery note | – | W (invoicing) | C | – | R | Production Controller | Site supervisors |
| Non-conformance report | – | – | C | – | R | Quality Manager | QA inspector |
| Weekly capacity | – | – | C | – | R | Production Controller | Site supervisors |

Each owning role also owns the data quality rules and KPIs for its entities. The live counts of
rules, open exceptions and KPIs per owner are on the Governance page of the app, under Ownership
matrix.

## What each owner is answerable for

| Owning role | Entities | In practice |
| --- | --- | --- |
| Purchasing Manager | Material, purchase order | New material codes approved before use; old variants blocked; every order carries the full code with grade; services bought on a purchase order. |
| Production Controller | Works order and BOM, material issue, stock, time booking, delivery note, weekly capacity | Works orders closed when despatched; bookings only against live works orders; every stock line counted at least quarterly; every delivery note complete. |
| Finance Manager | Supplier, customer, job, invoices, job cost | One account per supplier and customer; every job code in the crosswalk before its first invoice; three-way match exceptions cleared within 30 days. |
| Quality Manager | Goods received note and traceability, non-conformance report | Heat number and certificate on every receipt; untraceable material quarantined; every NCR costed and closed within 60 days. |

## Escalation route

Most disagreements are settled automatically by the rules in `docs/integration-design.md`. The rest
follow this route. Each step has a time limit, so nothing sits in a queue indefinitely.

| Step | Who | When it applies | Time limit | What they can decide |
| --- | --- | --- | --- | --- |
| 0 | The rules, automatically | Every incoming record | Overnight | Apply the conflict rules; match automatically at a score of 95 or more; quarantine what fails a check |
| 1 | Data steward | An item in the review or exception queue for their entity | 5 working days | Correct the record at source; accept or reject a proposed match; chase a missing certificate or invoice |
| 2 | Data owner | The steward cannot settle it, or the fix touches another owner's data | A further 5 working days | Decide the disputed value, agreeing with the other owner if two are involved; approve a merge; accept a known exception with a reason |
| 3 | Data governance group: the four owners, chaired by the sponsor named at mobilisation | Two owners disagree, or a rule or threshold needs to change | Next monthly meeting, or within 2 working days if urgent | Change a rule, threshold or owner; decide between owners; commission a fix to a system or process |
| 4 | Managing Director | The decision has contractual or safety consequences, or a financial effect above £10,000 | Within 2 working days | Notify a customer or the certification body; restate job costs on a live contract; write off a disputed amount |

**Two fast tracks skip the queue.**

- **Safety.** If steel on a job cannot be traced to its mill certificate, the Quality Manager may
  quarantine the material or stop despatch at once. The escalation then runs in parallel, to
  decide what happens next.
- **Payments.** A change to a supplier's bank details never goes through the review queue. It needs
  the Finance Manager and a second authorised signatory, confirmed by telephone to a number already
  on file.

**Every decision is recorded.** Who decided, when, which values were chosen and why is kept with
the review item. That record, together with the lineage of every figure, is what lets an auditor or
customer follow any number back to its source.

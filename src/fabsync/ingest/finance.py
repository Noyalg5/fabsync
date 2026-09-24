"""Contract for the finance system export.

Conventions: Title Case names, dates YYYY-MM-DD, some amounts stored as text
with thousands separators, job codes as YY + sequence ("24871") where the
MRPII job number is "J-24-0871". All data is synthetic.
"""

from fabsync.ingest.contracts import DATE, DECIMAL, TEXT, Column, SourceContract, TableContract

FIN_DATE = ("%Y-%m-%d",)
JOB_CODE = r"^\d{4,6}$"

CONTRACT = SourceContract(
    system="finance",
    label="Finance system",
    conventions=(
        ("text case", "Title Case"),
        ("dates", "YYYY-MM-DD"),
        ("amounts", "some stored as text with thousands separators"),
        ("job codes", "YY + sequence without leading zeros, e.g. 24871"),
    ),
    tables=(
        TableContract(
            name="purchase_invoices", file="finance/purchase_invoices.csv", key=("invoice_no",),
            description="Purchase ledger invoices; steel invoices reference a PO, others do not",
            columns=(
                Column("invoice_no", TEXT, required=True),
                Column("supplier_account", TEXT, required=True),
                Column("supplier_name", TEXT, required=True),
                Column("po_reference", TEXT, description="Corvus PO number; blank for subcontract and overhead"),
                Column("net_amount", DECIMAL, required=True),
                Column("vat", DECIMAL, required=True),
                Column("gross", DECIMAL, required=True),
                Column("invoice_date", DATE, required=True, formats=FIN_DATE),
                Column("nominal_code", TEXT, required=True),
                Column("job_code", TEXT, pattern=JOB_CODE, description="Finance job code; blank for overheads"),
            ),
        ),
        TableContract(
            name="sales_invoices", file="finance/sales_invoices.csv", key=("invoice_no",),
            description="Sales ledger invoices and applications for payment",
            columns=(
                Column("customer_account", TEXT, required=True),
                Column("customer_name", TEXT, required=True),
                Column("job_code", TEXT, required=True, pattern=JOB_CODE),
                Column("net_amount", DECIMAL, required=True),
                Column("invoice_date", DATE, required=True, formats=FIN_DATE),
                Column("invoice_no", TEXT, required=True),
            ),
        ),
        TableContract(
            name="job_costs", file="finance/job_costs.csv", key=("job_code", "cost_type", "period"),
            description="Job cost ledger by period and cost type",
            columns=(
                Column("job_code", TEXT, required=True, pattern=JOB_CODE),
                Column("cost_type", TEXT, required=True, domain=("material", "labour", "subcontract", "plant")),
                Column("period", TEXT, required=True, pattern=r"^\d{4}-\d{2}$",
                       description="Accounting period YYYY-MM"),
                Column("amount", DECIMAL, required=True),
            ),
        ),
        TableContract(
            name="supplier_master", file="finance/supplier_master.csv", key=("supplier_account",),
            description="Purchase ledger supplier accounts",
            columns=(
                Column("supplier_account", TEXT, required=True),
                Column("supplier_name", TEXT, required=True),
                Column("payment_terms", TEXT),
                Column("currency", TEXT, required=True, domain=("GBP", "EUR")),
            ),
        ),
    ),
)

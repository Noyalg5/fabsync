"""Contract for Corvus MRP, the MRPII system installed in 2006.

Conventions: UPPERCASE text, dates DD/MM/YYYY, fixed-width padding that leaves
trailing whitespace, supplier names embedded in purchase orders with no clean
supplier master, units of measure EA, M and KG. All data is synthetic.
"""

from fabsync.ingest.contracts import DATE, DECIMAL, INTEGER, TEXT, Column, SourceContract, TableContract

MRP_DATE = ("%d/%m/%Y",)
UOM = ("EA", "M", "KG")
# Canonical Corvus code: kind + dimensions + grade, e.g. UB203X133X25-S355J2, PLT12-S355J2.
# Consumables (bolts, wire, paint) follow their own scheme and are allowed through.
MATERIAL_CODE = r"^((UB|UC|PFC|SHS|RHS|CHS|L|FLAT)[0-9X.]+|PLT\d+)-S\d{3}[A-Z0-9]+$|^(BOLT|NUT|WASH|WIRE|PAINT|GAS)-"

CONTRACT = SourceContract(
    system="corvus_mrp",
    label="Corvus MRP (MRPII)",
    conventions=(
        ("text case", "UPPERCASE"),
        ("dates", "DD/MM/YYYY"),
        ("padding", "fixed-width fields, trailing spaces"),
        ("units", "EA, M, KG"),
        ("supplier master", "none; names typed on each purchase order"),
    ),
    tables=(
        TableContract(
            name="works_orders", file="corvus_mrp/works_orders.csv", key=("wo_no",),
            description="Works orders: authorisation to fabricate assemblies for a job",
            columns=(
                Column("wo_no", INTEGER, required=True, description="Works order number"),
                Column("job_no", TEXT, required=True, pattern=r"^J-\d{2}-\d{4}$", description="Job number J-YY-NNNN"),
                Column("customer_ref", TEXT, description="Customer order reference"),
                Column("part_code", TEXT, required=True, description="Assembly mark"),
                Column("description", TEXT),
                Column("qty", INTEGER, required=True),
                Column("uom", TEXT, required=True, domain=UOM),
                Column("planned_hours", DECIMAL, required=True),
                Column("planned_start", DATE, required=True, formats=MRP_DATE),
                Column("planned_finish", DATE, required=True, formats=MRP_DATE),
                Column("actual_finish", DATE, formats=MRP_DATE),
                Column("status", TEXT, required=True,
                       domain=("PLANNED", "OPEN", "RELEASED", "COMPLETE", "CLOSED", "CANCELLED")),
                Column("site", TEXT, required=True, domain=("WKF", "TEE")),
            ),
        ),
        TableContract(
            name="bom_lines", file="corvus_mrp/bom_lines.csv", key=("wo_no", "line_no"),
            description="Bill of material lines per works order",
            columns=(
                Column("wo_no", INTEGER, required=True),
                Column("line_no", INTEGER, required=True),
                Column("material_code", TEXT, required=True, pattern=MATERIAL_CODE),
                Column("description", TEXT),
                Column("section_type", TEXT, required=True),
                Column("grade", TEXT, required=True),
                Column("length_mm", INTEGER, required=True),
                Column("qty", DECIMAL, required=True),
                Column("uom", TEXT, required=True, domain=UOM),
                Column("unit_weight_kg", DECIMAL, required=True, description="kg/m, or kg/m2 for plate"),
            ),
        ),
        TableContract(
            name="stock", file="corvus_mrp/stock.csv", key=("material_code", "site", "location"),
            description="Stock on hand by material, site and location, with last count",
            columns=(
                Column("material_code", TEXT, required=True, pattern=MATERIAL_CODE),
                Column("description", TEXT),
                Column("location", TEXT, required=True),
                Column("site", TEXT, required=True, domain=("WKF", "TEE")),
                Column("qty_on_hand", DECIMAL, required=True),
                Column("uom", TEXT, required=True, domain=UOM),
                Column("unit_cost", DECIMAL, required=True),
                Column("last_count_date", DATE, formats=MRP_DATE),
                Column("counted_qty", DECIMAL),
            ),
        ),
        TableContract(
            name="purchase_orders", file="corvus_mrp/purchase_orders.csv", key=("po_no",),
            description="Purchase orders for steel; one material line per order",
            columns=(
                Column("po_no", TEXT, required=True, pattern=r"^PO\d{6}$"),
                Column("supplier_code", TEXT, required=True, pattern=r"^S\d{4}$"),
                Column("supplier_name", TEXT, required=True, description="Typed on the order; no master"),
                Column("material_code", TEXT, required=True, pattern=MATERIAL_CODE),
                Column("qty", DECIMAL, required=True),
                Column("uom", TEXT, required=True, domain=UOM),
                Column("unit_price", DECIMAL, required=True),
                Column("order_date", DATE, required=True, formats=MRP_DATE),
                Column("promised_date", DATE, required=True, formats=MRP_DATE),
            ),
        ),
        TableContract(
            name="goods_received", file="corvus_mrp/goods_received.csv", key=("grn_no",),
            description="Goods received notes with heat number and mill certificate reference",
            columns=(
                Column("grn_no", TEXT, required=True, pattern=r"^GRN\d+$"),
                Column("po_no", TEXT, required=True, pattern=r"^PO\d{6}$"),
                Column("material_code", TEXT, required=True, pattern=MATERIAL_CODE),
                Column("qty_received", DECIMAL, required=True),
                Column("uom", TEXT, required=True, domain=UOM),
                Column("received_date", DATE, required=True, formats=MRP_DATE),
                Column("heat_number", TEXT, description="Mill cast identifier; EN 1090 traceability"),
                Column("mill_cert_ref", TEXT, description="EN 10204 3.1 certificate reference"),
            ),
        ),
    ),
)

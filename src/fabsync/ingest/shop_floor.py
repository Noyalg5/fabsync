"""Contract for the shop-floor spreadsheets kept by supervisors at each site.

Conventions: human entry. Mixed case, typos, blank cells, three date formats
in the same column, duplicate rows, and works orders written as "WO 12345",
"wo-12345", "12345" or "12345 (rev B)". All data is synthetic.
"""

from fabsync.ingest.contracts import DATE, DECIMAL, INTEGER, TEXT, Column, SourceContract, TableContract

OPS_DATES = ("%d/%m/%Y", "%Y-%m-%d", "%d-%b-%y")
WO = r"^\d{5}$"  # canonical works order: the bare Corvus number

CONTRACT = SourceContract(
    system="shop_floor",
    label="Shop-floor spreadsheets",
    conventions=(
        ("text case", "mixed, with typos"),
        ("dates", "DD/MM/YYYY, YYYY-MM-DD and DD-Mon-YY in the same column"),
        ("works order", "free text: WO 12345, wo-12345, 12345, 12345 (rev B)"),
        ("blanks", "common"),
        ("duplicates", "copy-and-paste repeats"),
    ),
    tables=(
        TableContract(
            name="time_bookings", file="shop_floor/time_bookings.csv", key=("booking_id",),
            description="Operator time bookings against works orders",
            columns=(
                Column("booking_id", INTEGER, required=True),
                Column("operator", TEXT),
                Column("works_order", TEXT, required=True, pattern=WO, description="Free-text works order reference"),
                Column("operation", TEXT),
                Column("hours", DECIMAL, required=True),
                Column("booking_date", DATE, required=True, formats=OPS_DATES),
                Column("site", TEXT, required=True, description="Site written many ways"),
            ),
        ),
        TableContract(
            name="delivery_notes", file="shop_floor/delivery_notes.csv", key=("dn_no",),
            description="Despatches to site with promised and actual dates and tonnage",
            columns=(
                Column("dn_no", TEXT, required=True, pattern=r"^DN\d+$"),
                Column("job", TEXT, required=True, pattern=r"^J-\d{2}-\d{4}$", description="Free-text job reference"),
                Column("customer", TEXT),
                Column("despatch_date", DATE, required=True, formats=OPS_DATES),
                Column("promised_date", DATE, formats=OPS_DATES),
                Column("tonnage", DECIMAL),
                Column("vehicle", TEXT),
            ),
        ),
        TableContract(
            name="ncr_log", file="shop_floor/ncr_log.csv", key=("ncr_no",),
            description="Non-conformance reports",
            columns=(
                Column("ncr_no", TEXT, required=True, pattern=r"^NCR-\d+$"),
                Column("works_order", TEXT, required=True, pattern=WO),
                Column("raised_date", DATE, required=True, formats=OPS_DATES),
                Column("category", TEXT, required=True),
                Column("description", TEXT),
                Column("cost_impact", DECIMAL, description="Pounds; typed with and without currency symbol"),
                Column("closed_date", DATE, formats=OPS_DATES),
            ),
        ),
        TableContract(
            name="weekly_capacity", file="shop_floor/weekly_capacity.csv", key=("week_commencing", "site"),
            description="Available and booked hours per site per week",
            columns=(
                Column("week_commencing", DATE, required=True, formats=OPS_DATES),
                Column("site", TEXT, required=True),
                Column("available_hours", DECIMAL, required=True),
                Column("booked_hours", DECIMAL),
            ),
        ),
    ),
)

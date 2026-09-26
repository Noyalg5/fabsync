"""FabSync colour semantics, shared by the app and the printed pack so a colour means the same thing in both.

One accent colour for emphasis and for anything new; one fixed colour per source system, used for that system
wherever it appears; neutral greys for text, rules and anything retired or secondary.
"""

ACCENT = "#0F5C7A"
ACCENT_FILL = "#E8F1F5"
INK = "#1F2933"
MUTED = "#7B8794"
RULE = "#CBD2D9"
GRID = "#EEF1F4"
PAPER = "#F5F7FA"
SYSTEM_COLOURS = {"corvus_mrp": "#3B6EA8", "finance": "#B07A2A", "shop_floor": "#4F8A55"}
SYSTEM_LABELS = {"corvus_mrp": "Corvus MRP", "finance": "Finance system", "shop_floor": "Shop-floor spreadsheets"}

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("KMS_DATA_DIR", BASE_DIR / "data"))
DB_PATH = Path(os.getenv("KMS_DB_PATH", BASE_DIR / "kms_database.db"))
GEO_MAPPING_PATH = Path(os.getenv("KMS_GEO_MAPPING", DATA_DIR / "geo_mapping.csv"))

ITEMS_FILE = os.getenv(
    "KMS_ITEMS_FILE",
    "53331_-_שמש_-_פרוט_מקטים-_kms.xlsx",
)
SUPPLIERS_FILE = os.getenv(
    "KMS_SUPPLIERS_FILE",
    "9028_דוח_ספקים_בעלי_הסכם_פעיל-kms (2).xlsx",
)
AGREEMENTS_FILE = os.getenv(
    "KMS_AGREEMENTS_FILE",
    "52593_-_שמש_-_הסכמי_מחירים_כללי-kms.xlsx",
)

UNIQUE_ID_COLUMNS = [
    'מק"ט',
    "רמת בסיס",
    "רמת חריגה",
    "אחוז לחריגה",
    "סוג זכאי",
    "סוג סכום",
]

REFUND_NOTE = "יש לבדוק את תאריך ביצוע השירות בהתאם להנחיות ההחזר."

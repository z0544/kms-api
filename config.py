"""קונפיגורציה מרכזית – Pydantic BaseSettings.

שומרת על תאימות מלאה לאחור: כל קוד שעשה
``from config import DB_PATH`` ימשיך לעבוד.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """הגדרות מערכת — קוראות מ-env vars עם prefix KMS_*."""

    model_config = SettingsConfigDict(
        env_prefix="KMS_",
        env_file=str(_BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # נתיבי בסיס
    base_dir: Path = Field(default=_BASE_DIR)
    data_dir: Path = Field(default=_BASE_DIR / "data")
    db_path: Path = Field(default=_BASE_DIR / "kms_database.db")
    geo_mapping: Path | None = None  # מחושב מ-data_dir אם לא הוגדר

    # קבצי Excel
    items_file: str = "53331_-_שמש_-_פרוט_מקטים-_kms.xlsx"
    suppliers_file: str = "9028_דוח_ספקים_בעלי_הסכם_פעיל-kms (2).xlsx"
    agreements_file: str = "52593_-_שמש_-_הסכמי_מחירים_כללי-kms.xlsx"

    # CORS — רשימת origins מותרים (מופרדים בפסיק)
    cors_origins: str = "*"

    # Logging
    log_level: str = "INFO"
    log_file: str | None = None

    # Admin endpoint לטעינת ETL מ-API (אם ריק — disabled)
    admin_token: str | None = None

    # FTS5 — opt-in בלבד (KMS_USE_FTS=1). ברירת מחדל: LIKE כמו תמיד.
    use_fts: bool = False

    @field_validator("data_dir", "db_path", "base_dir", mode="before")
    @classmethod
    def _expand_paths(cls, v):
        if v is None:
            return v
        return Path(str(v)).expanduser()

    @property
    def geo_mapping_path(self) -> Path:
        return self.geo_mapping or (self.data_dir / "geo_mapping.csv")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()


def get_admin_token() -> str | None:
    """מחזיר אסימון מנהל — מ-settings או ישירות מ-.env (fallback)."""
    if settings.admin_token:
        return settings.admin_token
    env_path = _BASE_DIR / ".env"
    if not env_path.is_file():
        return None
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        if key.strip().upper() == "KMS_ADMIN_TOKEN":
            token = val.strip().strip('"').strip("'")
            return token or None
    return None


# === תאימות לאחור: שמות המשתנים הישנים נשארים זמינים ===
BASE_DIR: Path = settings.base_dir
DATA_DIR: Path = settings.data_dir
DB_PATH: Path = settings.db_path
GEO_MAPPING_PATH: Path = settings.geo_mapping_path

ITEMS_FILE: str = settings.items_file
SUPPLIERS_FILE: str = settings.suppliers_file
AGREEMENTS_FILE: str = settings.agreements_file

CORS_ORIGINS: list[str] = settings.cors_origins_list
USE_FTS: bool = settings.use_fts

ENTITY_ID_PARTS = [
    'מק"ט',
    "סוג זכאי",
    "סוג סכום",
    "רמת בסיס",
    "רמת חריגה",
]

# עמודות לנורמליזציה ב-ETL (אחוז לחריגה לא חלק מה-entity_id)
UNIQUE_ID_COLUMNS = ENTITY_ID_PARTS + ["אחוז לחריגה"]

REFUND_NOTE = "יש לבדוק את תאריך ביצוע השירות בהתאם להנחיות ההחזר."

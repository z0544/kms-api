import math
from typing import Any


def clean_value(value: Any) -> Any:
    if value is None:
        return "לא מוגדר"
    if isinstance(value, float) and math.isnan(value):
        return "לא מוגדר"
    if isinstance(value, str) and value.strip().lower() in ("nan", "none", ""):
        return "לא מוגדר"
    return value


def clean_record(record: dict[str, Any], *, hide_undefined: bool = False) -> dict[str, Any]:
    cleaned = {key: clean_value(val) for key, val in record.items()}
    if hide_undefined:
        return {k: v for k, v in cleaned.items() if v != "לא מוגדר"}
    return cleaned

from shared.generics.errors import DrivingPortError


def safe_float(raw: str, field_name: str = "value", *, min_val: float | None = None) -> float:
    try:
        val = float(raw)
    except (ValueError, TypeError):
        raise DrivingPortError(f"Invalid {field_name}")
    if min_val is not None and val < min_val:
        raise DrivingPortError(f"{field_name} must be >= {min_val}")
    return val


def safe_int(raw: str | int, default: int, *, min_val: int = 1) -> int:
    try:
        val = int(raw)
    except (ValueError, TypeError):
        return default
    return max(val, min_val)


def parse_optional_int(
    raw: str | int | None,
    field_name: str = "value",
    *,
    min_val: int = 1,
) -> int | None:
    if raw in (None, ""):
        return None
    try:
        val = int(raw)
    except (ValueError, TypeError):
        raise DrivingPortError(f"Invalid {field_name}")
    if val < min_val:
        raise DrivingPortError(f"{field_name} must be >= {min_val}")
    return val


def parse_table_params(args: dict, default_sort: str = "created_at", default_dir: str = "desc") -> dict:
    return {
        "page": safe_int(args.get("page", 1), default=1),
        "limit": safe_int(args.get("limit", 20), default=20),
        "sort_by": args.get("sort_by", default_sort),
        "sort_dir": args.get("sort_dir", default_dir),
        "filters": {k: v for k, v in args.items()
                    if "__" in k and k not in ("sort_by", "sort_dir")},
    }

"""Per-type value generation with seeded randomness."""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from typing import Any


def make_rng(seed: int):
    """Return a new random.Random instance for reproducibility."""
    return random.Random(seed)


def gen_string(
    rng: random.Random,
    min_len: int | None = None,
    max_len: int | None = None,
    prefix: str = "val",
    nullable: bool = False,
    null_chance: float = 0.2,
) -> str | None:
    if nullable and rng.random() < null_chance:
        return None
    # NOT NULL string: never empty; respect max_length
    lo = min_len if min_len is not None else 1
    if lo < 1:
        lo = 1
    hi = max_len if max_len is not None else 255
    # Heuristic: Avoid extreme padding unless strictly needed.
    # If hi is large, pick a reasonable default length (e.g., 5-30) instead of max.
    target_len = rng.randint(lo, min(hi, 30)) if hi > 30 else rng.randint(lo, hi)
    
    base = f"{prefix}_{rng.randint(1, 9999)}"
    if target_len <= len(base):
        result = base[:target_len]
    else:
        # Avoid 'xxx' filler if it looks like a name/email, use random chars or just keep it short
        fill_char = rng.choice("abcdefghijklmnopqrstuvwxyz") 
        result = base + fill_char * (target_len - len(base))
    
    if max_len is not None and len(result) > max_len:
        result = result[:max_len]
    return result


def gen_int(
    rng: random.Random,
    min_val: int | None = None,
    max_val: int | None = None,
    nullable: bool = False,
    null_chance: float = 0.2,
) -> int | None:
    if nullable and rng.random() < null_chance:
        return None
    lo = min_val if min_val is not None else 0
    hi = max_val if max_val is not None else (2**31 - 1)
    if lo > hi:
        lo, hi = hi, lo
    return rng.randint(int(lo), int(hi))


def gen_float(
    rng: random.Random,
    min_val: float | None = None,
    max_val: float | None = None,
    nullable: bool = False,
    null_chance: float = 0.2,
) -> float | None:
    if nullable and rng.random() < null_chance:
        return None
    lo = min_val if min_val is not None else 0.0
    hi = max_val if max_val is not None else 1e10
    if lo > hi:
        lo, hi = hi, lo
    val = round(rng.uniform(lo, hi), 2)
    # Clamp to schema bounds so we never exceed min/max (e.g. Mongo maximum)
    if min_val is not None and val < min_val:
        val = float(min_val)
    if max_val is not None and val > max_val:
        val = float(max_val)
    return val


def gen_bool(rng: random.Random, nullable: bool = False, null_chance: float = 0.1) -> bool | None:
    if nullable and rng.random() < null_chance:
        return None
    return rng.choice([True, False])


def gen_date(rng: random.Random, nullable: bool = False, null_chance: float = 0.2) -> date | None:
    if nullable and rng.random() < null_chance:
        return None
    d = date(2020, 1, 1) + timedelta(days=rng.randint(0, 2000))
    return d


def gen_datetime(rng: random.Random, nullable: bool = False, null_chance: float = 0.2) -> datetime | None:
    if nullable and rng.random() < null_chance:
        return None
    dt = datetime(2020, 1, 1) + timedelta(seconds=rng.randint(0, 2000 * 86400))
    return dt


def gen_enum(
    rng: random.Random,
    values: list[str],
    nullable: bool = False,
    null_chance: float = 0.15,
) -> str | None:
    """Only use allowed enum values. values must be non-empty when nullable is False."""
    if nullable and rng.random() < null_chance:
        return None
    if not values:
        raise ValueError("enum_values must be non-empty for enum field when generating a value")
    return rng.choice(values)


BoundaryKind = str  # "min" | "max" | "zero" | "empty" | "max_length"


def gen_boundary_value(
    field_name: str,
    data_type: str,
    kind: BoundaryKind,
    *,
    enum_values: list[str] | None = None,
    max_length: int | None = None,
    min_length: int | None = None,
    min_value: int | float | None = None,
    max_value: int | float | None = None,
    nullable: bool = True,
    unique_suffix: int | None = None,
) -> Any:
    """Generate a deterministic boundary value (no RNG). Schema-compliant; never empty for NOT NULL string."""
    if enum_values:
        if kind == "min":
            return enum_values[0]
        if kind == "max":
            return enum_values[-1]
        return enum_values[0]
    type_lower = (data_type or "string").lower()
    if type_lower in ("int", "integer"):
        if kind == "zero":
            return int(min_value) if min_value is not None else 0
        if kind == "min":
            return int(min_value) if min_value is not None else 0
        if kind == "max":
            return int(max_value) if max_value is not None else (2**31 - 1)
        return 0
    if type_lower in ("float", "number", "decimal"):
        if kind == "zero":
            return float(min_value) if min_value is not None else 0.0
        if kind == "min":
            return float(min_value) if min_value is not None else 0.0
        if kind == "max":
            # Use schema maximum when set so boundary row never exceeds (e.g. Mongo maximum)
            return float(max_value) if max_value is not None else 1e10
        return 0.0
    if type_lower in ("bool", "boolean"):
        return kind == "max"
    if type_lower in ("date", "datetime", "timestamp"):
        if kind == "min":
            return date(2020, 1, 1) if type_lower == "date" else datetime(2020, 1, 1)
        if kind == "max":
            return date(2030, 12, 31) if type_lower == "date" else datetime(2030, 12, 31)
        return date(2020, 1, 1) if type_lower == "date" else datetime(2020, 1, 1)
    # string: never empty for NOT NULL (nullable=False)
    if kind == "empty":
        return "" if nullable else ("a" * (min_length or 1))
    if kind == "max_length" and max_length is not None:
        base = "x" * min(max_length, 2000)
        if unique_suffix is not None:
            suffix = "_" + str(unique_suffix)
            if max_length and len(suffix) < max_length:
                base = base[: max_length - len(suffix)] + suffix
        return base
    if kind == "min":
        if nullable and (min_length == 0 or min_length is None):
            return ""
        base = "a" * (min_length or 1)
        if unique_suffix is not None:
            suffix = "_" + str(unique_suffix)
            base = base + suffix
            if max_length and len(base) > max_length:
                base = base[:max_length]
        return base
    # String "max" boundary: cap at max_length when set, else 255 so we never exceed schema/DB expectations
    if kind == "max":
        cap = min(max_length or 255, 2000)
        base = "x" * cap
        if unique_suffix is not None:
            suffix = "_" + str(unique_suffix)
            if max_length and len(suffix) < max_length:
                base = base[: max_length - len(suffix)] + suffix
            elif not max_length:
                base = base + suffix
        return base
    return "a" if not nullable else ""


def gen_value_for_field(
    field_name: str,
    data_type: str,
    rng: random.Random,
    *,
    nullable: bool = True,
    enum_values: list[str] | None = None,
    max_length: int | None = None,
    min_length: int | None = None,
    min_value: int | float | None = None,
    max_value: int | float | None = None,
    null_chance: float = 0.2,
    prefix_override: str | None = None,
    semantic_pool: list[Any] | None = None,
) -> Any:
    """Generate a single value. Strict: enum only from enum_values; NOT NULL never null/empty; lengths and numerics within bounds."""
    # Priority 1: Semantic Pool (AI-generated)
    if semantic_pool and (data_type or "string").lower() == "string":
        # Check null chance if applicable
        if nullable and rng.random() < null_chance:
            return None
        val = rng.choice(semantic_pool)
        # Ensure it fits within max_length
        if max_length and len(str(val)) > max_length:
            val = str(val)[:max_length]
        return val

    if enum_values:
        return gen_enum(rng, list(enum_values), nullable=nullable, null_chance=null_chance)
    type_lower = (data_type or "string").lower()
    # Heuristic for numbers that should likely be positive
    price_names = {"total", "amount", "price", "count", "quantity", "balance", "cost", "sum"}
    if field_name.lower() in price_names:
        if min_value is None or min_value < 0:
            # If user didn't explicitly allow negative in schema, default to positive
            min_value = 0.0 if type_lower in ("float", "number", "decimal") else 1

    if type_lower in ("int", "integer"):
        return gen_int(
            rng,
            min_val=int(min_value) if min_value is not None else None,
            max_val=int(max_value) if max_value is not None else None,
            nullable=nullable,
            null_chance=null_chance,
        )
    if type_lower in ("float", "number", "decimal"):
        return gen_float(
            rng,
            min_val=float(min_value) if min_value is not None else None,
            max_val=float(max_value) if max_value is not None else None,
            nullable=nullable,
            null_chance=null_chance,
        )
    if type_lower in ("bool", "boolean"):
        return gen_bool(rng, nullable=nullable, null_chance=null_chance)
    if type_lower == "date":
        return gen_date(rng, nullable=nullable, null_chance=null_chance)
    if type_lower in ("datetime", "timestamp"):
        return gen_datetime(rng, nullable=nullable, null_chance=null_chance)
    
    # Smarter prefix for strings based on name
    if prefix_override is None:
        if "email" in field_name.lower():
            prefix = "email"
        elif "name" in field_name.lower():
            prefix = "name"
        else:
            prefix = field_name[:8] if field_name else "val"
    else:
        prefix = prefix_override

    return gen_string(
        rng,
        min_len=min_length if min_length is not None else 1,
        max_len=max_length or 255,
        prefix=prefix,
        nullable=nullable,
        null_chance=null_chance,
    )

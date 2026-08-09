"""ULID helpers. IDs are ULIDs across the system (spec §4.4): time-sortable and
collision-free. Prefixes match doc conventions (doc_, dec_, brf_, qry_, flg_, …)."""

from ulid import ULID


def new_id(prefix: str) -> str:
    return f"{prefix}_{ULID()}"


def gen_trace_id() -> str:
    return new_id("trc")

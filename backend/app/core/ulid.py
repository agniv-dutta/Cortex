"""ULID helpers.

IDs are ULIDs across the system (spec §4.4): time-sortable and collision-free.
When the optional ``ulid`` dependency is unavailable (for local test runners or
minimal environments), fall back to UUID4 so the app still boots cleanly.
"""

from uuid import uuid4

try:  # pragma: no cover - exercised implicitly when dependency is installed
    from ulid import ULID
except ModuleNotFoundError:  # pragma: no cover - fallback for lean envs/tests
    ULID = None  # type: ignore[assignment]


def new_id(prefix: str) -> str:
    if ULID is None:
        return f"{prefix}_{uuid4().hex}"
    return f"{prefix}_{ULID()}"


def gen_trace_id() -> str:
    return new_id("trc")

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Current UTC time as a naive datetime, matching the naive DB columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

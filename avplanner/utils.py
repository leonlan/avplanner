import datetime
from datetime import timedelta


def date_range(
    start: datetime.date, end: datetime.date
) -> list[datetime.date]:
    """
    Returns a list of dates between the start and end date (inclusive).
    """
    delta = (end - start).days
    return [start + timedelta(days=idx) for idx in range(delta + 1)]

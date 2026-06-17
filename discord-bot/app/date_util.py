"""Date utility module for timezone conversions."""

from datetime import date, datetime, timedelta, timezone


def gmt7_to_utc_range(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    """
    Convert an inclusive GMT+7 date range to UTC datetime boundaries.

    Returns (utc_start, utc_end) where:
      - utc_start = start_date 00:00:00 GMT+7
      - utc_end   = end_date   23:59:59 GMT+7
    """
    # GMT+7 is UTC+7. So 00:00 GMT+7 = 17:00 UTC (previous day)
    # 23:59:59 GMT+7 = 16:59:59 UTC (same day)
    start_naive = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0)
    end_naive = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59)

    utc_start = (start_naive - timedelta(hours=7)).replace(tzinfo=timezone.utc)
    utc_end = (end_naive - timedelta(hours=7)).replace(tzinfo=timezone.utc)

    return utc_start, utc_end

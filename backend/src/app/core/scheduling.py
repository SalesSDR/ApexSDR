import zoneinfo
from datetime import UTC, datetime, timedelta


def get_next_business_time(current_time: datetime, prospect_timezone: str = "America/New_York") -> datetime:
    """
    Guarantees next_action_at lands between Mon-Fri, 9 AM - 5 PM in the prospect's local timezone.
    """
    try:
        tz = zoneinfo.ZoneInfo(prospect_timezone)
    except Exception:
        tz = zoneinfo.ZoneInfo("America/New_York")

    local_time = current_time.astimezone(tz)

    # If weekend, move to Monday 9 AM
    if local_time.weekday() >= 5:
        days_ahead = 7 - local_time.weekday()
        local_time = local_time + timedelta(days=days_ahead)
        local_time = local_time.replace(hour=9, minute=0, second=0, microsecond=0)

    # Check if target hour lands during 9 AM - 5 PM
    elif local_time.hour < 9:
        local_time = local_time.replace(hour=9, minute=0, second=0, microsecond=0)

    elif local_time.hour >= 17:
        local_time = local_time + timedelta(days=1)
        if local_time.weekday() >= 5:
            local_time = local_time + timedelta(days=2)
        local_time = local_time.replace(hour=9, minute=0, second=0, microsecond=0)

    return local_time.astimezone(UTC)


def get_next_action_time(settings_obj, rule_obj, dev_mode: bool, delay_days: int) -> datetime:
    """
    Calculates the exact execution time. Overridden to 60s in dev_mode.
    """
    now_utc = datetime.now(UTC)
    if dev_mode:
        return now_utc + timedelta(seconds=60)

    scheduled_time = now_utc + timedelta(days=delay_days)
    prospect_tz = settings_obj.timezone if settings_obj and hasattr(settings_obj, "timezone") else "UTC"
    return get_next_business_time(scheduled_time, prospect_tz)

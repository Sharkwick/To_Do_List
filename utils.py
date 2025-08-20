import hashlib
from datetime import datetime, timedelta, timezone

def hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()

def format_task_timestamp(ts: datetime) -> str:
    if not isinstance(ts, datetime):
        return "N/A"
    tz_offset = timedelta(hours=5, minutes=30)
    local_time = ts + tz_offset
    return local_time.strftime("%d %B %Y at %H:%M:%S UTC+5:30")

def to_datetime(ts):
    if isinstance(ts, datetime):
        return ts
    try:
        return ts.ToDatetime()  # Firestore Timestamp
    except:
        try:
            return datetime.fromisoformat(ts)
        except:
            return None

def fmt_elapsed_since(ts: datetime) -> str:
    ts = to_datetime(ts)
    if not ts:
        return "N/A"
    if ts.tzinfo:
        ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
    now = datetime.utcnow()
    delta = now - ts
    days = delta.days
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60
    return f"{days:02d}d {hours:02d}:{minutes:02d}"

def safe_dt_str(dt: datetime) -> str:
    dt = to_datetime(dt)
    if dt:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return "N/A"
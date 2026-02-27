from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
MARKET_OPEN_TIME = time(9, 0)
MARKET_CLOSE_TIME = time(15, 30)


def is_market_open(now: datetime | None = None) -> bool:
    """Return whether KRX market session is open in Asia/Seoul time."""
    current = now or datetime.now(KST)

    if current.tzinfo is None:
        seoul_now = current.replace(tzinfo=KST)
    else:
        seoul_now = current.astimezone(KST)

    current_time = seoul_now.time()
    return MARKET_OPEN_TIME <= current_time < MARKET_CLOSE_TIME

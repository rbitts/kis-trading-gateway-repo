import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.market_hours import is_market_open


class TestMarketHoursPolicy(unittest.TestCase):
    def test_market_open_at_10am_seoul(self):
        dt = datetime(2026, 1, 2, 10, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        self.assertTrue(is_market_open(dt))

    def test_market_closed_at_8pm_seoul(self):
        dt = datetime(2026, 1, 2, 20, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        self.assertFalse(is_market_open(dt))


if __name__ == "__main__":
    unittest.main()

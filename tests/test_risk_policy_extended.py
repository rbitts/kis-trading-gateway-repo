import unittest
from datetime import datetime as real_datetime
from unittest.mock import patch

from fastapi import HTTPException

from app.api import routes
from app.schemas.risk import RiskCheckRequest
from app.services import risk_policy


class RiskPolicyExtendedTest(unittest.TestCase):
    def test_evaluate_trade_risk_blocks_live_when_disabled(self):
        req = RiskCheckRequest(account_id='A1', symbol='005930', side='BUY', qty=1, price=70000)
        result = risk_policy.evaluate_trade_risk(
            req,
            live_enabled=False,
            daily_order_count=0,
            daily_order_limit=5,
            max_qty=10,
            get_available_sell_qty=lambda _a, _s: 0,
        )
        self.assertEqual(result, {'ok': False, 'reason': 'LIVE_DISABLED'})

    def test_evaluate_trade_risk_blocks_daily_limit(self):
        req = RiskCheckRequest(account_id='A1', symbol='005930', side='BUY', qty=1, price=70000)
        result = risk_policy.evaluate_trade_risk(
            req,
            live_enabled=True,
            daily_order_count=5,
            daily_order_limit=5,
            max_qty=10,
            get_available_sell_qty=lambda _a, _s: 0,
        )
        self.assertEqual(result, {'ok': False, 'reason': 'DAILY_LIMIT_EXCEEDED'})

    def test_evaluate_trade_risk_blocks_max_qty(self):
        req = RiskCheckRequest(account_id='A1', symbol='005930', side='BUY', qty=11, price=70000)
        result = risk_policy.evaluate_trade_risk(
            req,
            live_enabled=True,
            daily_order_count=0,
            daily_order_limit=5,
            max_qty=10,
            get_available_sell_qty=lambda _a, _s: 0,
        )
        self.assertEqual(result, {'ok': False, 'reason': 'MAX_QTY_EXCEEDED'})

    def test_validate_order_action_transition(self):
        ok = risk_policy.validate_order_action_transition(action='cancel', current_status='SENT')
        blocked = risk_policy.validate_order_action_transition(action='modify', current_status='FILLED')
        self.assertEqual(ok, {'ok': True, 'reason': None})
        self.assertEqual(blocked, {'ok': False, 'reason': 'INVALID_TRANSITION'})

    def test_route_transition_guard_raises_http_400(self):
        with self.assertRaises(HTTPException) as ctx:
            routes._ensure_transition_allowed(current_status='FILLED', action='cancel')
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail, 'INVALID_TRANSITION')

    def test_route_check_risk_uses_extended_guard(self):
        req = RiskCheckRequest(account_id='A1', symbol='005930', side='BUY', qty=1, price=70000)
        with patch('app.api.routes.datetime') as mock_datetime:
            mock_datetime.now.return_value = real_datetime(2026, 1, 2, 10, 0, 0)
            result = routes.check_risk(req)
        self.assertEqual(result, {'ok': True, 'reason': None})


if __name__ == '__main__':
    unittest.main()

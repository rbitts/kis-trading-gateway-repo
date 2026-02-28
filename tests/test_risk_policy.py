import unittest

from app.schemas.risk import RiskCheckRequest
from app.services.risk_policy import evaluate_side_policy


class RiskPolicyTest(unittest.TestCase):
    def test_buy_notional_limit_exceeded(self):
        result = evaluate_side_policy(
            RiskCheckRequest(account_id='A1', symbol='005930', side='BUY', qty=200, price=70000),
            get_available_sell_qty=lambda _a, _s: 0,
        )
        self.assertEqual(result, {'ok': False, 'reason': 'NOTIONAL_LIMIT_EXCEEDED'})

    def test_sell_requires_position_qty(self):
        result = evaluate_side_policy(
            RiskCheckRequest(account_id='A1', symbol='005930', side='SELL', qty=2, price=70000),
            get_available_sell_qty=lambda _a, _s: 1,
        )
        self.assertEqual(result, {'ok': False, 'reason': 'INSUFFICIENT_POSITION_QTY'})

    def test_sell_notional_limit_not_applied(self):
        result = evaluate_side_policy(
            RiskCheckRequest(account_id='A1', symbol='005930', side='SELL', qty=200, price=70000),
            get_available_sell_qty=lambda _a, _s: 300,
        )
        self.assertEqual(result, {'ok': True, 'reason': None})


if __name__ == '__main__':
    unittest.main()

import unittest
from datetime import datetime as real_datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class SmokeTest(unittest.TestCase):
    def test_quotes_order_modify_cancel_and_portfolio(self):
        c = TestClient(app)

        # quote
        r = c.get('/v1/quotes/005930')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['symbol'], '005930')

        # order create
        with patch('app.api.routes.datetime') as mock_datetime:
            mock_datetime.now.return_value = real_datetime(2026, 1, 2, 10, 0, 0)
            r2 = c.post('/v1/orders', headers={'Idempotency-Key': 'k1'}, json={
                'account_id': 'A1', 'symbol': '005930', 'side': 'BUY', 'qty': 1
            })
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()['status'], 'ACCEPTED')
        order_id = r2.json()['order_id']

        # modify/cancel
        r3 = c.post(f'/v1/orders/{order_id}/modify', json={'qty': 2, 'price': 70100})
        self.assertEqual(r3.status_code, 200)
        self.assertEqual(r3.json()['status'], 'MODIFY_PENDING')

        # reset to SENT for cancel happy path
        from app.services.order_queue import order_queue
        order_queue.jobs[order_id]['status'] = 'SENT'

        r4 = c.post(f'/v1/orders/{order_id}/cancel')
        self.assertEqual(r4.status_code, 200)
        self.assertEqual(r4.json()['status'], 'CANCEL_PENDING')

        # portfolio endpoints contract
        balances = c.get('/v1/balances', params={'account_id': 'A1'})
        positions = c.get('/v1/positions', params={'account_id': 'A1'})
        self.assertEqual(balances.status_code, 200)
        self.assertEqual(positions.status_code, 200)
        self.assertIsInstance(balances.json(), list)
        self.assertIsInstance(positions.json(), list)


if __name__ == '__main__':
    unittest.main()

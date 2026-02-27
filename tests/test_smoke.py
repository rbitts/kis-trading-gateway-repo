import unittest

from fastapi.testclient import TestClient

from app.main import app


class SmokeTest(unittest.TestCase):
    def test_quotes_and_order(self):
        c = TestClient(app)
        r = c.get('/v1/quotes/005930')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['symbol'], '005930')

        r2 = c.post('/v1/orders', headers={'Idempotency-Key': 'k1'}, json={
            'account_id': 'A1', 'symbol': '005930', 'side': 'BUY', 'qty': 1
        })
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()['status'], 'ACCEPTED')


if __name__ == '__main__':
    unittest.main()

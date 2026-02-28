import unittest

from fastapi.testclient import TestClient

from app.main import app


class _PortfolioStubClient:
    def get_balances(self, account_id: str):
        return [
            {
                "account_id": account_id,
                "currency": "KRW",
                "cash_available": 1234567.0,
            }
        ]

    def get_positions(self, account_id: str):
        return [
            {
                "account_id": account_id,
                "symbol": "005930",
                "qty": 7,
            }
        ]


class TestBalancePositionEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self._original_rest_client = app.state.quote_gateway_service.rest_client
        app.state.quote_gateway_service.rest_client = _PortfolioStubClient()

    def tearDown(self):
        app.state.quote_gateway_service.rest_client = self._original_rest_client

    def test_get_balances_returns_contract_schema(self):
        resp = self.client.get("/v1/balances", params={"account_id": "12345678-01"})

        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertIsInstance(payload, list)
        self.assertEqual(payload[0]["account_id"], "12345678-01")
        self.assertEqual(payload[0]["currency"], "KRW")
        self.assertEqual(payload[0]["cash_available"], 1234567.0)

    def test_get_positions_returns_contract_schema(self):
        resp = self.client.get("/v1/positions", params={"account_id": "12345678-01"})

        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertIsInstance(payload, list)
        self.assertEqual(payload[0]["account_id"], "12345678-01")
        self.assertEqual(payload[0]["symbol"], "005930")
        self.assertEqual(payload[0]["qty"], 7)


if __name__ == "__main__":
    unittest.main()

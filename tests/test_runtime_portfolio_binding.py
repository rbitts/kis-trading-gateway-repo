import unittest
from types import SimpleNamespace

from app.integrations.kis_rest import KisRestClient
from app.main import _bind_runtime_clients, app


class RuntimePortfolioBindingTest(unittest.TestCase):
    def test_bind_runtime_clients_sets_portfolio_capable_rest_client(self):
        settings = SimpleNamespace(
            KIS_APP_KEY="dummy-key",
            KIS_APP_SECRET="dummy-secret",
            KIS_ENV="mock",
        )

        _bind_runtime_clients(app, settings)

        self.assertIsInstance(app.state.quote_gateway_service.rest_client, KisRestClient)
        self.assertTrue(hasattr(app.state.quote_gateway_service.rest_client, "get_balances"))
        self.assertTrue(hasattr(app.state.quote_gateway_service.rest_client, "get_positions"))

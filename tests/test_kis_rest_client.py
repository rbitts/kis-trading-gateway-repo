import unittest
from unittest.mock import MagicMock

from app.integrations.kis_rest import KisRestClient


class TestKisRestClient(unittest.TestCase):
    def test_get_quote_parses_response_and_auth_flow(self):
        session = MagicMock()

        token_response = MagicMock()
        token_response.json.return_value = {
            "access_token": "token-123",
            "expires_in": 3600,
        }
        token_response.raise_for_status.return_value = None

        quote_response = MagicMock()
        quote_response.json.return_value = {
            "output": {
                "stck_prpr": "71200",
                "prdy_ctrt": "1.35",
                "acml_tr_pbmn": "123456789",
            }
        }
        quote_response.raise_for_status.return_value = None

        session.post.return_value = token_response
        session.get.return_value = quote_response

        client = KisRestClient(
            app_key="app-key",
            app_secret="app-secret",
            env="mock",
            session=session,
            base_url="https://example.test",
        )

        quote = client.get_quote("005930")

        self.assertEqual(quote["symbol"], "005930")
        self.assertEqual(quote["price"], 71200.0)
        self.assertEqual(quote["change_pct"], 1.35)
        self.assertEqual(quote["turnover"], 123456789.0)
        self.assertEqual(quote["source"], "kis-rest")
        self.assertIsInstance(quote["ts"], int)

        session.post.assert_called_once()
        session.get.assert_called_once()

        get_call_kwargs = session.get.call_args.kwargs
        self.assertEqual(
            get_call_kwargs["headers"]["authorization"], "Bearer token-123"
        )
        self.assertEqual(
            get_call_kwargs["params"],
            {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": "005930"},
        )

    def test_token_is_cached_between_quote_requests(self):
        session = MagicMock()

        token_response = MagicMock()
        token_response.json.return_value = {
            "access_token": "token-123",
            "expires_in": 3600,
        }
        token_response.raise_for_status.return_value = None

        quote_response = MagicMock()
        quote_response.json.return_value = {
            "output": {
                "stck_prpr": "100",
                "prdy_ctrt": "0.1",
                "acml_tr_pbmn": "200",
            }
        }
        quote_response.raise_for_status.return_value = None

        session.post.return_value = token_response
        session.get.return_value = quote_response

        client = KisRestClient(
            app_key="app-key",
            app_secret="app-secret",
            env="mock",
            session=session,
            base_url="https://example.test",
        )

        client.get_quote("005930")
        client.get_quote("000660")

        self.assertEqual(session.post.call_count, 1)
        self.assertEqual(session.get.call_count, 2)


if __name__ == "__main__":
    unittest.main()

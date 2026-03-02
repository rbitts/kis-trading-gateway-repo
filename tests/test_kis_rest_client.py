import unittest
from unittest.mock import MagicMock, patch

from app.integrations.kis_rest import KisRestClient


class TestKisRestClient(unittest.TestCase):
    def test_issue_token_uses_kis_contract(self):
        session = MagicMock()

        token_response = MagicMock()
        token_response.json.return_value = {
            "access_token": "token-123",
            "expires_in": 3600,
        }
        token_response.raise_for_status.return_value = None
        session.post.return_value = token_response

        client = KisRestClient(
            app_key="app-key",
            app_secret="app-secret",
            env="mock",
            session=session,
            base_url="https://example.test",
        )

        client.get_access_token()

        session.post.assert_called_once_with(
            "https://example.test/oauth2/tokenP",
            headers={"content-type": "application/json; charset=utf-8"},
            json={
                "grant_type": "client_credentials",
                "appkey": "app-key",
                "appsecret": "app-secret",
            },
            timeout=5,
        )

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
                "hts_kor_isnm": "삼성전자",
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

    def test_short_ttl_token_is_still_cached_briefly(self):
        session = MagicMock()

        first_token_response = MagicMock()
        first_token_response.json.return_value = {
            "access_token": "token-123",
            "expires_in": 30,
        }
        first_token_response.raise_for_status.return_value = None

        second_token_response = MagicMock()
        second_token_response.json.return_value = {
            "access_token": "token-456",
            "expires_in": 30,
        }
        second_token_response.raise_for_status.return_value = None

        session.post.side_effect = [first_token_response, second_token_response]

        client = KisRestClient(
            app_key="app-key",
            app_secret="app-secret",
            env="mock",
            session=session,
            base_url="https://example.test",
        )

        with patch("app.integrations.kis_rest.time.time", side_effect=[1000.0, 1000.2]):
            token1 = client.get_access_token()
            token2 = client.get_access_token()

        self.assertEqual(token1, "token-123")
        self.assertEqual(token2, "token-123")
        self.assertEqual(session.post.call_count, 1)


    def test_issue_approval_key_uses_kis_contract(self):
        session = MagicMock()

        approval_response = MagicMock()
        approval_response.json.return_value = {
            "approval_key": "approval-123",
        }
        approval_response.raise_for_status.return_value = None
        session.post.return_value = approval_response

        client = KisRestClient(
            app_key="app-key",
            app_secret="app-secret",
            env="mock",
            session=session,
            base_url="https://example.test",
        )

        approval_key = client.issue_approval_key()

        self.assertEqual(approval_key, "approval-123")
        session.post.assert_called_once_with(
            "https://example.test/oauth2/Approval",
            headers={"content-type": "application/json; charset=utf-8"},
            json={
                "grant_type": "client_credentials",
                "appkey": "app-key",
                "secretkey": "app-secret",
            },
            timeout=5,
        )



if __name__ == "__main__":
    unittest.main()

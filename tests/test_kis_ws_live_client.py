import json
import unittest
from unittest.mock import MagicMock

from app.integrations.kis_ws import KisWsClient


class _FakeWebSocketApp:
    def __init__(self, url, *, header=None, on_open=None, on_message=None, on_error=None, on_close=None):
        self.url = url
        self.header = header
        self.on_open = on_open
        self.on_message = on_message
        self.on_error = on_error
        self.on_close = on_close
        self.sent_messages = []

    def send(self, payload):
        self.sent_messages.append(payload)

    def run_forever(self):
        if self.on_open is not None:
            self.on_open(self)
        if self.on_message is not None:
            self.on_message(
                self,
                json.dumps(
                    {
                        "body": {
                            "output": {
                                "mksc_shrn_iscd": "005930",
                                "stck_prpr": "71300",
                                "prdy_ctrt": "1.49",
                                "acml_tr_pbmn": "2233445566",
                            }
                        }
                    }
                ),
            )


class TestKisWsLiveClient(unittest.TestCase):
    def test_connect_subscribe_and_ingest_callback_flow(self):
        approval_client = MagicMock()
        approval_client.issue_approval_key.return_value = "approval-123"

        received = []
        client = KisWsClient(
            on_message=lambda quote: received.append(quote),
            approval_key_client=approval_client,
            env="mock",
            websocket_app_factory=_FakeWebSocketApp,
        )

        ws_app = client.connect_and_subscribe(symbols=["005930"], run_forever=True)

        approval_client.issue_approval_key.assert_called_once_with()
        self.assertEqual(ws_app.url, "wss://openapivts.koreainvestment.com:21000")
        self.assertEqual(len(ws_app.sent_messages), 1)

        subscribe_payload = json.loads(ws_app.sent_messages[0])
        self.assertEqual(subscribe_payload["header"]["approval_key"], "approval-123")
        self.assertEqual(subscribe_payload["body"]["input"]["tr_id"], "H0STCNT0")
        self.assertEqual(subscribe_payload["body"]["input"]["tr_key"], "005930")

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["symbol"], "005930")
        self.assertEqual(received[0]["price"], 71300.0)


if __name__ == "__main__":
    unittest.main()

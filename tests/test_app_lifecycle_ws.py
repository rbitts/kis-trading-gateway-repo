import unittest
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.main import app


class AppLifecycleWsTest(unittest.TestCase):
    def test_ws_client_start_stop_on_app_lifecycle(self):
        ws_client = app.state.ws_client
        original_start = ws_client.start
        original_stop = ws_client.stop

        start_mock = Mock()
        stop_mock = Mock()
        ws_client.start = start_mock
        ws_client.stop = stop_mock

        try:
            with TestClient(app):
                start_mock.assert_called_once_with()
                stop_mock.assert_not_called()
            stop_mock.assert_called_once_with()
        finally:
            ws_client.start = original_start
            ws_client.stop = original_stop


if __name__ == '__main__':
    unittest.main()

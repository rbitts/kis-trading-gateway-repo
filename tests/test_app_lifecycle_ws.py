import threading
import time
import unittest
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.main import app


class AppLifecycleWsTest(unittest.TestCase):
    def test_ws_worker_starts_on_startup_and_stops_gracefully_on_shutdown(self):
        ws_client = app.state.ws_client
        original_start = ws_client.start
        original_stop = ws_client.stop
        original_run_with_reconnect = ws_client.run_with_reconnect

        started = threading.Event()
        stopped = threading.Event()

        stop_mock = Mock(side_effect=original_stop)

        def run_with_reconnect_mock(*, connect_once, **kwargs):
            started.set()
            while ws_client.running:
                time.sleep(0.01)
            stopped.set()
            return False

        ws_client.start = Mock()
        ws_client.stop = stop_mock
        ws_client.run_with_reconnect = Mock(side_effect=run_with_reconnect_mock)

        try:
            with TestClient(app):
                self.assertTrue(started.wait(0.3), "WS worker did not start on startup")
                ws_client.run_with_reconnect.assert_called_once()
                ws_client.start.assert_not_called()
                stop_mock.assert_not_called()

            stop_mock.assert_called_once_with()
            self.assertTrue(stopped.wait(0.3), "WS worker did not stop after shutdown")
        finally:
            ws_client.start = original_start
            ws_client.stop = original_stop
            ws_client.run_with_reconnect = original_run_with_reconnect


if __name__ == '__main__':
    unittest.main()

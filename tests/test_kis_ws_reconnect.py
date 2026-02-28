import unittest

from app.integrations.kis_ws import KisWsClient


class TestKisWsReconnect(unittest.TestCase):
    def test_reconnect_uses_exponential_backoff_sequence(self):
        client = KisWsClient()
        sleeps = []
        attempts = []

        def connect_once():
            attempts.append("x")
            raise RuntimeError("disconnect")

        result = client.run_with_reconnect(
            connect_once=connect_once,
            sleep_fn=lambda sec: sleeps.append(sec),
            max_retries=3,
            backoff_base_sec=1.0,
            backoff_cap_sec=10.0,
        )

        self.assertFalse(result)
        self.assertEqual(len(attempts), 3)
        self.assertEqual(sleeps, [1.0, 2.0])

    def test_stop_signal_exits_reconnect_loop_immediately(self):
        client = KisWsClient()
        client.start()
        calls = {"count": 0}

        def connect_once():
            calls["count"] += 1
            client.stop()
            raise RuntimeError("disconnect")

        sleeps = []
        result = client.run_with_reconnect(
            connect_once=connect_once,
            sleep_fn=lambda sec: sleeps.append(sec),
            max_retries=5,
            backoff_base_sec=1.0,
            backoff_cap_sec=10.0,
        )

        self.assertFalse(result)
        self.assertEqual(calls["count"], 1)
        self.assertEqual(sleeps, [])

    def test_no_sleep_after_final_failed_attempt(self):
        client = KisWsClient()
        sleeps = []

        def connect_once():
            raise RuntimeError("disconnect")

        result = client.run_with_reconnect(
            connect_once=connect_once,
            sleep_fn=lambda sec: sleeps.append(sec),
            max_retries=3,
            backoff_base_sec=1.0,
            backoff_cap_sec=10.0,
        )

        self.assertFalse(result)
        # retry between attempts only: 1->2, 2->3
        self.assertEqual(sleeps, [1.0, 2.0])


if __name__ == "__main__":
    unittest.main()

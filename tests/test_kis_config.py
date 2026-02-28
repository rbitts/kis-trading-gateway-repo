import os
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.config.settings import Settings


class TestKisSettings(unittest.TestCase):
    def test_missing_required_env_fails_validation(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValidationError):
                Settings.from_env()

    def test_valid_env_loads_settings(self):
        env = {
            "KIS_APP_KEY": "app-key",
            "KIS_APP_SECRET": "app-secret",
            "KIS_ACCOUNT_NO": "12345678-01",
            "KIS_ENV": "mock",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings.from_env()

        self.assertEqual(settings.KIS_APP_KEY, "app-key")
        self.assertEqual(settings.KIS_APP_SECRET, "app-secret")
        self.assertEqual(settings.KIS_ACCOUNT_NO, "12345678-01")
        self.assertEqual(settings.KIS_ENV, "mock")

    def test_ws_symbols_default_is_single_samsung(self):
        env = {
            "KIS_APP_KEY": "app-key",
            "KIS_APP_SECRET": "app-secret",
            "KIS_ACCOUNT_NO": "12345678-01",
            "KIS_ENV": "mock",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings.from_env()

        self.assertEqual(settings.KIS_WS_SYMBOLS, ["005930"])

    def test_ws_symbols_parses_comma_separated_values(self):
        env = {
            "KIS_APP_KEY": "app-key",
            "KIS_APP_SECRET": "app-secret",
            "KIS_ACCOUNT_NO": "12345678-01",
            "KIS_ENV": "mock",
            "KIS_WS_SYMBOLS": " 005930, 000660 , 035420 ",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings.from_env()

        self.assertEqual(settings.KIS_WS_SYMBOLS, ["005930", "000660", "035420"])


if __name__ == "__main__":
    unittest.main()

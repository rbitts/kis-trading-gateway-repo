import unittest

from app.integrations.kis_ws import KisWsClient, parse_message


class TestKisWsParser(unittest.TestCase):
    def test_parse_message_maps_kis_style_fields(self):
        payload = {
            "fid_input_iscd": "005930",
            "stck_prpr": "71200",
            "prdy_ctrt": "1.35",
            "acml_tr_pbmn": "123456789",
        }

        parsed = parse_message(payload)

        self.assertEqual(parsed["symbol"], "005930")
        self.assertEqual(parsed["price"], 71200.0)
        self.assertEqual(parsed["change_pct"], 1.35)
        self.assertEqual(parsed["turnover"], 123456789.0)
        self.assertEqual(parsed["source"], "kis-ws")
        self.assertEqual(parsed["state"], "HEALTHY")
        self.assertEqual(parsed["freshness_sec"], 0.0)
        self.assertIsInstance(parsed["ts"], int)

    def test_parse_message_maps_normalized_fields(self):
        payload = {
            "symbol": "000660",
            "price": "198500",
            "change_pct": "-0.52",
            "turnover": "987654321",
            "source": "kis-ws-stream",
            "ts": 1700000000,
        }

        parsed = parse_message(payload)

        self.assertEqual(parsed["symbol"], "000660")
        self.assertEqual(parsed["price"], 198500.0)
        self.assertEqual(parsed["change_pct"], -0.52)
        self.assertEqual(parsed["turnover"], 987654321.0)
        self.assertEqual(parsed["source"], "kis-ws-stream")
        self.assertEqual(parsed["ts"], 1700000000)

    def test_parse_message_maps_real_kis_notice_format(self):
        payload = {
            "header": {"tr_id": "H0STCNT0"},
            "body": {
                "rt_cd": "0",
                "output": {
                    "mksc_shrn_iscd": "005930",
                    "stck_prpr": "71300",
                    "prdy_ctrt": "1.49",
                    "acml_tr_pbmn": "2233445566",
                },
            },
        }

        parsed = parse_message(payload)

        self.assertEqual(parsed["symbol"], "005930")
        self.assertEqual(parsed["price"], 71300.0)
        self.assertEqual(parsed["change_pct"], 1.49)
        self.assertEqual(parsed["turnover"], 2233445566.0)

    def test_client_build_subscribe_message_matches_kis_contract(self):
        client = KisWsClient(approval_key="approval-token")

        message = client.build_subscribe_message(symbol="005930")

        self.assertEqual(message["header"]["approval_key"], "approval-token")
        self.assertEqual(message["header"]["custtype"], "P")
        self.assertEqual(message["header"]["tr_type"], "1")
        self.assertEqual(message["header"]["content-type"], "utf-8")
        self.assertEqual(message["body"]["input"]["tr_id"], "H0STCNT0")
        self.assertEqual(message["body"]["input"]["tr_key"], "005930")

    def _build_h0stcnt0_record(
        self,
        *,
        symbol: str,
        trade_time: str = "093001",
        price: str = "71300",
        change_pct: str = "1.49",
        turnover: str = "2233445566",
    ) -> list[str]:
        fields = ["" for _ in range(46)]
        fields[0] = symbol
        fields[1] = trade_time
        fields[2] = price
        fields[5] = change_pct
        fields[14] = turnover
        return fields

    def test_parse_message_pipe_realtime_uses_fixed_price_index_even_with_trade_time(self):
        record = self._build_h0stcnt0_record(symbol="005930", trade_time="093001", price="71300")
        payload = "0|H0STCNT0|001|" + "^".join(record)

        parsed = parse_message(payload)

        self.assertEqual(parsed["symbol"], "005930")
        self.assertEqual(parsed["price"], 71300.0)
        self.assertEqual(parsed["change_pct"], 1.49)
        self.assertEqual(parsed["turnover"], 2233445566.0)
        self.assertEqual(parsed["source"], "kis-ws")

    def test_parse_message_pipe_realtime_supports_multi_record_frame(self):
        rec1 = self._build_h0stcnt0_record(symbol="005930", price="71300")
        rec2 = self._build_h0stcnt0_record(symbol="000660", price="198500", change_pct="-0.52", turnover="987654321")
        payload = "0|H0STCNT0|002|" + "^".join(rec1 + rec2)

        parsed = parse_message(payload)

        self.assertEqual(parsed["symbol"], "005930")
        self.assertEqual(parsed["price"], 71300.0)

    def test_parse_message_pipe_realtime_rejects_malformed_field_count(self):
        malformed = self._build_h0stcnt0_record(symbol="005930")[:-1]
        payload = "0|H0STCNT0|001|" + "^".join(malformed)

        with self.assertRaises(ValueError):
            parse_message(payload)

    def test_parse_message_raises_for_invalid_payload(self):
        with self.assertRaises(ValueError):
            parse_message("not-json")

        with self.assertRaises(ValueError):
            parse_message({"price": "1000"})

        with self.assertRaises(ValueError):
            parse_message({"symbol": "005930"})

    def test_client_start_stop_and_on_message_hook(self):
        received = []

        client = KisWsClient(on_message=lambda quote: received.append(quote))
        self.assertFalse(client.running)

        client.start()
        self.assertTrue(client.running)

        output = client.handle_raw_message(
            {
                "symbol": "005930",
                "price": "70000",
                "change_pct": "0.0",
                "turnover": "100",
            }
        )

        self.assertEqual(output["symbol"], "005930")
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["symbol"], "005930")

        client.stop()
        self.assertFalse(client.running)


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime as real_datetime
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import _DemoRestQuoteClient, app


class SmokeTest(unittest.TestCase):
    def setUp(self):
        app.state.quote_gateway_service.rest_client = _DemoRestQuoteClient()

    def test_api_docs_site_skeleton_links(self):
        repo_root = Path(__file__).resolve().parents[1]
        index_html = (repo_root / 'docs/site/index.html').read_text(encoding='utf-8')
        redoc_live = (repo_root / 'docs/site/redoc-live.html').read_text(encoding='utf-8')
        redoc_next = (repo_root / 'docs/site/redoc-next.html').read_text(encoding='utf-8')
        styles = repo_root / 'docs/site/styles.css'

        self.assertTrue(styles.exists())
        self.assertIn('redoc-live.html', index_html)
        self.assertIn('redoc-next.html', index_html)
        self.assertIn('./api/openapi-live.json', index_html)
        self.assertIn('./api/openapi-next.yaml', index_html)
        self.assertIn('./api/openapi-live.json', redoc_live)
        self.assertIn('./api/openapi-next.yaml', redoc_next)

    def test_docs_live_validation_checklist_links(self):
        repo_root = Path(__file__).resolve().parents[1]
        readme = (repo_root / 'README.md').read_text(encoding='utf-8')
        runbook = (repo_root / 'docs/ops/kis-quote-runbook.md').read_text(encoding='utf-8')
        checklist = (repo_root / 'docs/ops/kis-order-live-validation-checklist.md').read_text(encoding='utf-8')
        checklist_path = repo_root / 'docs/ops/kis-order-live-validation-checklist.md'

        self.assertTrue(checklist_path.exists())
        self.assertIn('kis-order-live-validation-checklist.md', readme)
        self.assertIn('kis-order-live-validation-checklist.md', runbook)
        self.assertIn('/v1/session/live-readiness', readme)
        self.assertIn('/v1/session/live-readiness', runbook)
        self.assertIn('/v1/session/live-readiness', checklist)
        self.assertIn('can_trade=true', readme)
        self.assertIn('can_trade=true', runbook)
        self.assertIn('can_trade=true', checklist)
        self.assertIn('can_trade=false', readme)
        self.assertIn('can_trade=false', runbook)
        self.assertIn('can_trade=false', checklist)
        self.assertIn('진입하지 않는다', readme)
        self.assertIn('진입 금지', runbook)
        self.assertIn('진입하지 않음', checklist)

    def test_live_readiness_endpoint_contract(self):
        c = TestClient(app)
        r = c.get('/v1/session/live-readiness')
        self.assertEqual(r.status_code, 200)

        body = r.json()
        self.assertIn('required_env_missing', body)
        self.assertIn('ws_connected', body)
        self.assertIn('ws_last_error', body)
        self.assertIn('can_trade', body)
        self.assertIn('blocker_reasons', body)

    def test_quotes_order_modify_cancel_and_portfolio(self):
        c = TestClient(app)

        # quote
        r = c.get('/v1/quotes/005930')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['symbol'], '005930')

        # order create
        with patch('app.api.routes.datetime') as mock_datetime:
            mock_datetime.now.return_value = real_datetime(2026, 1, 2, 10, 0, 0)
            r2 = c.post('/v1/orders', headers={'Idempotency-Key': 'k1'}, json={
                'account_id': 'A1', 'symbol': '005930', 'side': 'BUY', 'qty': 1
            })
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()['status'], 'ACCEPTED')
        order_id = r2.json()['order_id']

        # modify/cancel
        r3 = c.post(f'/v1/orders/{order_id}/modify', json={'qty': 2, 'price': 70100})
        self.assertEqual(r3.status_code, 200)
        self.assertEqual(r3.json()['status'], 'MODIFY_PENDING')

        # reset to SENT for cancel happy path
        from app.services.order_queue import order_queue
        order_queue.jobs[order_id]['status'] = 'SENT'

        r4 = c.post(f'/v1/orders/{order_id}/cancel')
        self.assertEqual(r4.status_code, 200)
        self.assertEqual(r4.json()['status'], 'CANCEL_PENDING')

        # portfolio endpoints contract
        balances = c.get('/v1/balances', params={'account_id': 'A1'})
        positions = c.get('/v1/positions', params={'account_id': 'A1'})
        self.assertEqual(balances.status_code, 503)
        self.assertEqual(positions.status_code, 503)
        self.assertEqual(balances.json(), {'detail': 'PORTFOLIO_PROVIDER_NOT_CONFIGURED'})
        self.assertEqual(positions.json(), {'detail': 'PORTFOLIO_PROVIDER_NOT_CONFIGURED'})


if __name__ == '__main__':
    unittest.main()

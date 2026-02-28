import pathlib
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
OPENAPI_PATH = REPO_ROOT / "docs" / "api" / "openapi-next.yaml"
ORDER_CONTRACT_DOC_PATH = REPO_ROOT / "docs" / "ops" / "order-api-contract.md"


class TestApiContractNext(unittest.TestCase):
    def test_openapi_next_exists(self):
        self.assertTrue(
            OPENAPI_PATH.exists(),
            "docs/api/openapi-next.yaml must exist",
        )

    def test_openapi_next_contains_required_operations_and_error_schema(self):
        content = OPENAPI_PATH.read_text(encoding="utf-8")

        required_operation_ids = [
            "createOrder",
            "cancelOrder",
            "modifyOrder",
            "getBalances",
            "getPositions",
            "reconcileOrders",
        ]
        for operation_id in required_operation_ids:
            self.assertIn(f"operationId: {operation_id}", content)

        self.assertIn("Error:", content)
        self.assertIn("code:", content)
        self.assertIn("message:", content)
        self.assertIn("retryable:", content)

    def test_order_api_contract_doc_mentions_next_operations(self):
        content = ORDER_CONTRACT_DOC_PATH.read_text(encoding="utf-8")

        expected_snippets = [
            "POST /v1/orders/{order_id}/cancel",
            "POST /v1/orders/{order_id}/modify",
            "GET /v1/balances",
            "GET /v1/positions",
            "POST /v1/orders/reconcile",
            "createOrder",
            "cancelOrder",
            "modifyOrder",
            "getBalances",
            "getPositions",
            "reconcileOrders",
            "Error schema",
            "retryable",
        ]

        for snippet in expected_snippets:
            self.assertIn(snippet, content)


if __name__ == "__main__":
    unittest.main()

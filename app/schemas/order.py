from pydantic import BaseModel


class OrderRequest(BaseModel):
    account_id: str
    symbol: str
    side: str
    qty: int
    order_type: str = "LIMIT"
    price: float | None = None
    strategy_id: str | None = None


class OrderAccepted(BaseModel):
    order_id: str
    status: str
    idempotency_key: str

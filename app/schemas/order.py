from pydantic import BaseModel, field_validator


class OrderRequest(BaseModel):
    account_id: str
    symbol: str
    side: str
    qty: int
    order_type: str = "LIMIT"
    price: float | None = None
    strategy_id: str | None = None

    @field_validator("side")
    @classmethod
    def normalize_side(cls, value: str) -> str:
        return value.upper()

    @field_validator("order_type")
    @classmethod
    def normalize_order_type(cls, value: str) -> str:
        return value.upper()


class OrderAccepted(BaseModel):
    order_id: str
    status: str
    idempotency_key: str

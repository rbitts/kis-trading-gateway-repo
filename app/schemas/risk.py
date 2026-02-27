from pydantic import BaseModel


class RiskCheckRequest(BaseModel):
    account_id: str
    symbol: str
    side: str
    qty: int
    price: float | None = None

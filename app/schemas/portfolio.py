from pydantic import BaseModel


class Balance(BaseModel):
    account_id: str
    currency: str
    cash_available: float


class Position(BaseModel):
    account_id: str
    symbol: str
    qty: int

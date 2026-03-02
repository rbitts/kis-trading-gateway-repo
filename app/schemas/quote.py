from pydantic import BaseModel


class QuoteSnapshot(BaseModel):
    symbol: str
    symbol_name: str | None = None
    price: float
    change_pct: float
    turnover: float
    source: str
    ts: int
    freshness_sec: float
    state: str

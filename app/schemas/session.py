from pydantic import BaseModel


class LiveReadinessResponse(BaseModel):
    required_env_missing: list[str]
    ws_connected: bool
    ws_last_error: str | None = None
    can_trade: bool
    blocker_reasons: list[str]

from pydantic import BaseModel


class SessionState(BaseModel):
    mode: str = "mock"
    owner: str = "gateway"
    state: str = "ACTIVE"
    source: str = "bootstrap"


session_state = SessionState()

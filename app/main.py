from fastapi import FastAPI

from app.api.routes import router
from app.config.settings import get_settings

app = FastAPI(title="KIS Trading Gateway", version="0.1.0")
app.include_router(router, prefix="/v1")

# NOTE: lazy-loaded so app import does not require env during tests.
app.state.get_settings = get_settings

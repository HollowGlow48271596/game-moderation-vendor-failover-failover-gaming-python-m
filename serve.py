"""ASGI entry point for the typed moderation endpoint."""

import os

from src.game_backend import create_app
from src.infrai_gateway import InfraiGateway


gateway = InfraiGateway(api_key=os.environ["INFRAI_API_KEY"])
app = create_app(gateway)


@app.on_event("shutdown")
async def close_gateway() -> None:
    await gateway.close()

import hmac
import logging
from typing import Any, Dict, Union

from fastapi import FastAPI, HTTPException, Header
from uvicorn import Config, Server

from src.bot import bot
from src.core import settings
from src.metrics import metrics_app
from src.webhooks import handlers
from src.webhooks.types import WebhookBody

logger = logging.getLogger(__name__)

app = FastAPI()


@app.post("/webhook")
async def webhook_handler(body: WebhookBody, authorization: Union[str, None] = Header(default=None)) -> Dict[str, Any]:
    """
    Handles incoming webhook requests and forwards them to the appropriate handler.

    This function first checks the provided authorization token in the request header.
    If the token is valid, it checks if the platform can be handled and then forwards
    the request to the corresponding handler.

    Args:
        body (WebhookBody): The data received from the webhook.
        authorization (Union[str, None]): The authorization header containing the Bearer token.

    Returns:
        Dict[str, Any]: The response from the corresponding handler. The dictionary contains
                       a "success" key indicating whether the operation was successful.

    Raises:
        HTTPException: If an error occurs while processing the webhook event or if unauthorized.
    """
    if authorization is None or not authorization.strip().startswith("Bearer"):
        logger.warning("Unauthorized webhook request")
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = authorization[6:].strip()
    if hmac.compare_digest(token, settings.WEBHOOK_TOKEN):
        logger.warning("Unauthorized webhook request")
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not handlers.can_handle(body.platform):
        logger.warning("Webhook request not handled by platform")
        raise HTTPException(status_code=501, detail="Platform not implemented")

    return await handlers.handle(body, bot)


app.mount("/metrics", metrics_app)

config = Config(app, host="0.0.0.0", port=1337)
server = Server(config)

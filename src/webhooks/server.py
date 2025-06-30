import hashlib
import hmac
import logging
import json
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from hypercorn.asyncio import serve as hypercorn_serve
from hypercorn.config import Config as HypercornConfig
from pydantic import ValidationError, 

from src.bot import bot
from src.core import settings
from src.metrics import metrics_app
from src.webhooks import handlers
from src.webhooks.types import WebhookBody

logger = logging.getLogger(__name__)

app = FastAPI()


def verify_signature(body: dict, signature: str, secret: str) -> bool:
    """
    HMAC SHA1 signature verification.

    Args:
        body (dict): The raw body of the webhook request.
        signature (str): The X-Signature header of the webhook request.
        secret (str): The webhook secret.

    Returns:
        bool: True if the signature is valid, False otherwise.
    """
    if not signature:
        return False

    digest = hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()
    return hmac.compare_digest(signature, digest)


@app.post("/webhook")
async def webhook_handler(request: Request) -> Dict[str, Any]:
    """
    Handles incoming webhook requests and forwards them to the appropriate handler.

    This function first verifies the provided HMAC signature in the request header.
    If the signature is valid, it checks if the platform can be handled and then forwards
    the request to the corresponding handler.

    Args:
        request (Request): The incoming webhook request.

    Returns:
        Dict[str, Any]: The response from the corresponding handler. The dictionary contains
                       a "success" key indicating whether the operation was successful.

    Raises:
        HTTPException: If an error occurs while processing the webhook event or if unauthorized.
    """
    body = await request.body()
    signature = request.headers.get("X-Signature")

    if not verify_signature(body, signature, settings.WEBHOOK_TOKEN):
        logger.warning("Unauthorized webhook request")
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        body = WebhookBody.validate(json.loads(body))
    except ValidationError as e:
        logger.warning("Invalid webhook request: %s", e.errors())
        raise HTTPException(status_code=400, detail="Invalid webhook request body")

    if not handlers.can_handle(body.platform):
        logger.warning("Webhook request not handled by platform: %s", body.platform)
        raise HTTPException(status_code=501, detail="Platform not implemented")

    return await handlers.handle(body, bot)


app.mount("/metrics", metrics_app)

config = HypercornConfig()
config.bind = [f"0.0.0.0:{settings.WEBHOOK_PORT}"]


async def serve():
    await hypercorn_serve(app, config)

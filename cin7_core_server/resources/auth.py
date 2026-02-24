"""Authentication and status tools."""

from __future__ import annotations

import logging
from typing import Any, Dict

from ..cin7_client import Cin7Client
from ..utils.logging import truncate

logger = logging.getLogger("cin7_core_server.resources.auth")


async def cin7_status() -> Dict[str, Any]:
    """Verify Cin7 Core credentials by fetching a minimal page of products."""
    logger.debug("Tool call: cin7_status()")
    client = Cin7Client.from_env()
    result = await client.health_check()
    logger.debug("Tool result: cin7_status() -> %s", truncate(str(result)))
    return result


async def cin7_me() -> Dict[str, Any]:
    """Call Cin7 Core Me endpoint to verify identity and account context."""
    logger.debug("Tool call: cin7_me()")
    client = Cin7Client.from_env()
    result = await client.get_me()
    logger.debug("Tool result: cin7_me() -> %s", truncate(str(result)))
    return result

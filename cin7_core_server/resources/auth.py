"""Authentication and status tools."""

from __future__ import annotations

import logging
from typing import Any, Dict

from ..cin7_client import Cin7Client
from ..utils.logging import truncate
from ..utils.projection import project_dict

logger = logging.getLogger("cin7_core_server.resources.auth")


async def cin7_status() -> Dict[str, Any]:
    """Verify Cin7 Core credentials by fetching a minimal page of products."""
    logger.debug("Tool call: cin7_status()")
    client = Cin7Client.from_env()
    result = await client.health_check()
    logger.debug("Tool result: cin7_status() -> %s", truncate(str(result)))
    return result


async def cin7_me(fields: list[str] | None = None) -> Dict[str, Any]:
    """Call Cin7 Core Me endpoint to verify identity and account context.

    Parameters:
    - fields: Additional fields to include beyond defaults, or ["*"] for all

    Default returns: Company, Currency, DefaultLocation
    """
    logger.debug("Tool call: cin7_me()")
    client = Cin7Client.from_env()
    result = await client.get_me()
    result = project_dict(result, fields, base_fields={"Company", "Currency", "DefaultLocation"})
    logger.debug("Tool result: cin7_me() -> %s", truncate(str(result)))
    return result

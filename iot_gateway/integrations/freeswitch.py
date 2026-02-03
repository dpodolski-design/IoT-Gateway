"""FreeSWITCH integration: originate call via REST or ESL."""
import logging
from typing import Any

import httpx

from iot_gateway.config import settings

logger = logging.getLogger(__name__)


async def originate(destination_number: str, caller_id: str | None = None, playback: str | None = None) -> dict[str, Any]:
    """
    Initiate outbound call via FreeSWITCH.
    Returns dict with success (bool), call_id (str | None), error (str | None).
    """
    if getattr(settings, "freeswitch_rest_url", None):
        return await _originate_rest(destination_number, caller_id=caller_id, playback=playback)
    return await _originate_esl(destination_number, caller_id=caller_id, playback=playback)


async def _originate_rest(
    destination_number: str, caller_id: str | None = None, playback: str | None = None
) -> dict[str, Any]:
    """Use FreeSWITCH REST API (mod_http_cache or similar) if available."""
    base = (settings.freeswitch_rest_url or "").rstrip("/")
    if not base:
        logger.warning("FREESWITCH_REST_URL not set; skipping originate (mock)")
        return {"success": True, "call_id": None, "error": None, "mock": True}
    url = f"{base}/api/originate"
    payload: dict[str, Any] = {
        "destination": destination_number,
        "endpoint": f"user/{destination_number}",
    }
    if caller_id:
        payload["caller_id"] = caller_id
    if playback:
        payload["application"] = "playback"
        payload["application_data"] = playback
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, json=payload)
            if r.status_code >= 400:
                return {"success": False, "call_id": None, "error": r.text}
            data = r.json() if r.content else {}
            return {
                "success": True,
                "call_id": data.get("uuid") or data.get("call_id"),
                "error": None,
            }
    except Exception as e:
        logger.exception("FreeSWITCH REST originate failed")
        return {"success": False, "call_id": None, "error": str(e)}


async def _originate_esl(
    destination_number: str, caller_id: str | None = None, playback: str | None = None
) -> dict[str, Any]:
    """Use Event Socket Layer (ESL) to send bgapi originate."""
    try:
        import ESL
    except ImportError:
        logger.warning("python-ESL not installed; skipping originate (mock)")
        return {"success": True, "call_id": None, "error": None, "mock": True}
    host = settings.freeswitch_host
    port = settings.freeswitch_port
    password = settings.freeswitch_password
    con = ESL.ESLconnection(host, str(port), password)
    if not con.connected():
        return {"success": False, "call_id": None, "error": "ESL connection failed"}
    try:
        cmd = f"originate {{origination_caller_id_number={caller_id or 'IoT'}}}user/{destination_number} &echo"
        if playback:
            cmd = f"originate {{origination_caller_id_number={caller_id or 'IoT'}}}user/{destination_number} 'playback:{playback}' &echo"
        ev = con.api("bgapi", cmd)
        uuid = ev.getHeader("Job-UUID") if ev else None
        return {"success": True, "call_id": uuid, "error": None}
    finally:
        con.disconnect()

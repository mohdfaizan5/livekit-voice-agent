"""
Room utilities — helpers for finding participants and sending RPC commands.

Extracted from the monolithic agent.py so every tool module can share
the same logic without duplicating the boilerplate.
"""

import json
import logging
from typing import Any

from livekit.agents import get_job_context

logger = logging.getLogger("agent-UnlockPi")


# ---------------------------------------------------------------------------
# Find the frontend participant
# ---------------------------------------------------------------------------
def get_frontend_identity() -> str | None:
    """
    Finds the frontend participant identity in the current room.
    The frontend joins as 'teacher-interface' (set in classroom/page.tsx).
    Returns None if no matching participant is found.
    """
    try:
        room = get_job_context().room
        for identity, _participant in room.remote_participants.items():
            if "teacher" in identity.lower() or "frontend" in identity.lower():
                return identity
        # Fallback: return the first remote participant that isn't the agent itself
        for identity in room.remote_participants:
            return identity
    except Exception as e:
        logger.warning(f"Could not find frontend participant: {e}")
    return None


# ---------------------------------------------------------------------------
# Generic RPC sender
# ---------------------------------------------------------------------------
async def send_rpc(
    method: str,
    payload: dict[str, Any] | str,
    *,
    timeout: float = 10.0,
    frontend_id: str | None = None,
) -> str:
    """
    Send an RPC call to the frontend participant.

    Args:
        method: The RPC method name registered on the frontend.
        payload: Dict (will be JSON-serialised) or pre-serialised JSON string.
        timeout: Response timeout in seconds.
        frontend_id: Override auto-detection of the frontend participant.

    Returns:
        The raw response string from the frontend.

    Raises:
        RuntimeError: When no frontend participant can be found.
        Exception: Propagated from the underlying RPC call.
    """
    target = frontend_id or get_frontend_identity()
    if not target:
        raise RuntimeError("Could not find the classroom display participant.")

    payload_str = json.dumps(payload) if isinstance(payload, dict) else payload

    room = get_job_context().room
    response = await room.local_participant.perform_rpc(
        destination_identity=target,
        method=method,
        payload=payload_str,
        response_timeout=timeout,
    )
    return response

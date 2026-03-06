"""
Shared session state — attached to AgentSession[SessionData].userdata.

Follows LiveKit's recommended userdata pattern
(see: https://docs.livekit.io/agents/logic/agents-handoffs/#passing-state).
"""

from dataclasses import dataclass, field
from typing import Any, Optional

import asyncpg


@dataclass
class SessionData:
    """Mutable state shared across agents and tools within a single session."""

    db_pool: Optional[asyncpg.Pool] = None

    # Game state for cognitive tests (Family Feud)
    current_answers: list[dict[str, Any]] = field(default_factory=list)

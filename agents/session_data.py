"""
Shared session state — attached to AgentSession[SessionData].userdata.

Follows LiveKit's recommended userdata pattern
(see: https://docs.livekit.io/agents/logic/agents-handoffs/#passing-state).
"""

from dataclasses import dataclass, field
from typing import Any, Optional

import asyncpg

from helpers.board_engine import create_empty_board


@dataclass
class SessionData:
    """Mutable state shared across agents and tools within a single session."""

    db_pool: Optional[asyncpg.Pool] = None

    # Game state for cognitive tests (Family Feud)
    current_answers: list[dict[str, Any]] = field(default_factory=list)

    # Structured board document — source of truth for the board
    board_document: dict = field(default_factory=create_empty_board)

    # Teaching session context loaded from Supabase (optional)
    session_title: str | None = None
    session_topic: str | None = None
    session_goals: str | None = None
    session_structure: str | None = None

    # Runtime lesson tracking
    lesson_phase_order: list[str] = field(
        default_factory=lambda: ["warmup", "concept", "practice", "exit"]
    )
    current_phase_index: int = 0
    lesson_goal_checklist: list[str] = field(default_factory=list)
    covered_goals: list[str] = field(default_factory=list)

    # Course voice-control mode
    # course_context holds: { "course": "linked-lists", "chapter": 1, "step": 0 }
    course_mode: bool = False
    course_context: dict = field(default_factory=dict)

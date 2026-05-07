"""
PiTutorAgent — 

Loads its system prompt from prompts/mit-tutor.md. Simulates as tutor for a live session, guiding the user through a structured learning experience based on provided session context (title, topic, goals, structure). Keeps track of lesson phases and goal coverage, and provides tools to update this information.
Supports handoff to InterviewAgent for mock interviews.
"""

import os
import logging
import re
from typing import Iterable

from livekit.agents import Agent, RunContext, function_tool

from config import PROMPTS_DIR
from tools import (
    highlight_text,
    update_content,
    render_visual,
    # start_cognitive_test,
    # update_team_score,
    # get_team_scores,
    write_to_board,
    # update_board_line,
    add_board_block,
    highlight_board_line,
    # insert_board_line,
    # delete_board_line,
    clear_board_content,
)

logger = logging.getLogger("agent-UnlockPi")

DEFAULT_PHASE_ORDER = ["warmup", "concept", "practice", "exit"]
PHASE_ALIASES = {
    "warmup": ["warmup", "warm-up", "intro", "introduction", "icebreaker", "opening"],
    "concept": ["concept", "explain", "theory", "teach", "lesson"],
    "practice": ["practice", "activity", "exercise", "application", "workout"],
    "exit": ["exit", "summary", "wrap", "recap", "closing", "check-out"],
}


def _load_prompt(filename: str) -> str:
    """Load a prompt file from the prompts/ directory."""
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _unique_preserve_order(items: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        norm = _normalize_text(item)
        if norm and norm not in seen:
            seen.add(norm)
            result.append(item.strip())
    return result


def _parse_goals(raw_goals: str | None) -> list[str]:
    if not raw_goals:
        return []

    lines = [segment.strip() for segment in re.split(r"\n|;|\|", raw_goals) if segment.strip()]
    tokens: list[str] = []

    for line in lines:
        bullet = re.sub(r"^[-*\d.)\s]+", "", line).strip()
        if "," in bullet and len(bullet) > 40:
            parts = [part.strip() for part in bullet.split(",") if part.strip()]
            tokens.extend(parts)
        else:
            tokens.append(bullet)

    return _unique_preserve_order(tokens)


def _parse_phase_order(raw_structure: str | None) -> list[str]:
    if not raw_structure:
        return DEFAULT_PHASE_ORDER.copy()

    structure = _normalize_text(raw_structure)
    detected: list[str] = []

    for phase, aliases in PHASE_ALIASES.items():
        earliest = None
        for alias in aliases:
            idx = structure.find(alias)
            if idx != -1 and (earliest is None or idx < earliest):
                earliest = idx
        if earliest is not None:
            detected.append((earliest, phase))

    if not detected:
        return DEFAULT_PHASE_ORDER.copy()

    detected.sort(key=lambda item: item[0])
    ordered = [phase for _, phase in detected]

    for phase in DEFAULT_PHASE_ORDER:
        if phase not in ordered:
            ordered.append(phase)

    return ordered


class PiTutorAgent(Agent):
    """
    Engages as the visionary leader of manipal academy of higher education,
    discussing  education, careers,
    """
    # JUNK: runs cognitive tests, and manages team scores.

    def __init__(self, chat_ctx=None) -> None:
        # Lazy import to avoid circular dependency
        from agents.interview_agent import InterviewAgent  # noqa: F811

        self._interview_agent_cls = InterviewAgent
        self._base_instructions = _load_prompt("mit-tutor.md")

        super().__init__(
            instructions=self._base_instructions,
            chat_ctx=chat_ctx,
            tools=[
                highlight_text,
                update_content,
                render_visual,
                write_to_board,
                # update_board_line,
                add_board_block,
                highlight_board_line,
                # insert_board_line,
                # delete_board_line,
                clear_board_content,
                # start_cognitive_test,
                # update_team_score,
                # get_team_scores,
            ],
        )

    async def _apply_runtime_session_instructions(self) -> None:
        session_data = self.session.userdata
        title = getattr(session_data, "session_title", None)
        topic = getattr(session_data, "session_topic", None)
        goals = getattr(session_data, "session_goal_checklist", [])
        covered_goals = getattr(session_data, "covered_goals", [])
        phase_order = getattr(session_data, "lesson_phase_order", DEFAULT_PHASE_ORDER)
        current_phase_index = max(0, min(getattr(session_data, "current_phase_index", 0), len(phase_order) - 1))

        current_phase = phase_order[current_phase_index] if phase_order else "warmup"
        remaining_goals = [goal for goal in goals if _normalize_text(goal) not in {_normalize_text(item) for item in covered_goals}]

        context_block = (
            "## Current Session Context\n"
            f"Title: {title or ''}\n"
            f"Topic: {topic or ''}\n"
            f"Goals: {getattr(session_data, 'session_goals', '') or ''}\n"
            f"Structure: {getattr(session_data, 'session_structure', '') or ''}"
        )

        governance_block = (
            "## Live Session Governance\n"
            "- Keep every response anchored to the session topic. If user drifts, acknowledge briefly and gently bring them back.\n"
            "- Follow lesson phases in order. Do not skip ahead without explicitly closing the current phase.\n"
            "- Reference the plan naturally in speech (example: our goal today is..., based on our plan...).\n"
            "- Keep track of goals using tools: call get_lesson_progress when uncertain, mark_goal_covered when a goal is achieved, and advance_lesson_phase only when phase outcomes are done.\n"
            f"- Current phase: {current_phase}\n"
            f"- Phase order: {' -> '.join(phase_order)}\n"
            f"- Covered goals: {covered_goals or 'none yet'}\n"
            f"- Remaining goals: {remaining_goals or 'all covered'}"
        )

        await self.update_instructions(f"{self._base_instructions}\n\n{context_block}\n\n{governance_block}")

    async def on_enter(self):
        """Called when the agent joins. Sends a short greeting."""
        session_data = self.session.userdata
        session_data.lesson_goal_checklist = _parse_goals(getattr(session_data, "session_goals", None))
        session_data.covered_goals = []
        session_data.lesson_phase_order = _parse_phase_order(getattr(session_data, "session_structure", None))
        session_data.current_phase_index = 0

        if any([
            getattr(session_data, "session_title", None),
            getattr(session_data, "session_topic", None),
            getattr(session_data, "session_goals", None),
            getattr(session_data, "session_structure", None),
        ]):
            await self._apply_runtime_session_instructions()

        await self.session.generate_reply(
            instructions="Greet the user, keep it short.",
            allow_interruptions=True,
        )

    @function_tool()
    async def get_lesson_progress(self, context: RunContext):
        """Get current lesson phase and goal coverage status."""
        session_data = context.userdata
        phase_order = session_data.lesson_phase_order or DEFAULT_PHASE_ORDER
        index = max(0, min(session_data.current_phase_index, len(phase_order) - 1))
        current_phase = phase_order[index]

        covered = session_data.covered_goals
        checklist = session_data.lesson_goal_checklist
        remaining = [goal for goal in checklist if _normalize_text(goal) not in {_normalize_text(item) for item in covered}]

        return {
            "current_phase": current_phase,
            "phase_order": phase_order,
            "covered_goals": covered,
            "remaining_goals": remaining,
        }

    @function_tool()
    async def mark_goal_covered(self, context: RunContext, goal: str):
        """Mark a learning goal as covered when the learner demonstrates understanding."""
        session_data = context.userdata
        normalized_goal = _normalize_text(goal)
        if not normalized_goal:
            return "No goal provided."

        normalized_covered = {_normalize_text(item) for item in session_data.covered_goals}
        if normalized_goal not in normalized_covered:
            session_data.covered_goals.append(goal.strip())

        await self._apply_runtime_session_instructions()
        return f"Goal marked covered: {goal.strip()}"

    @function_tool()
    async def advance_lesson_phase(self, context: RunContext, next_phase: str | None = None):
        """Advance lesson phase in sequence when current phase objectives are complete."""
        session_data = context.userdata
        phase_order = session_data.lesson_phase_order or DEFAULT_PHASE_ORDER

        if not phase_order:
            session_data.lesson_phase_order = DEFAULT_PHASE_ORDER.copy()
            phase_order = session_data.lesson_phase_order

        current_index = max(0, min(session_data.current_phase_index, len(phase_order) - 1))
        target_index = current_index

        if next_phase:
            norm_next = _normalize_text(next_phase)
            for idx, phase in enumerate(phase_order):
                if _normalize_text(phase) == norm_next:
                    target_index = idx
                    break
        else:
            target_index = min(current_index + 1, len(phase_order) - 1)

        if target_index > current_index + 1:
            target_index = current_index + 1

        session_data.current_phase_index = target_index
        await self._apply_runtime_session_instructions()
        return f"Current phase is now: {phase_order[target_index]}"

    # ------------------------------------------------------------------
    # Handoff tool: transfer to interview mode
    # ------------------------------------------------------------------
    @function_tool()
    async def transfer_to_interview(self, context: RunContext):
        """Transfer to interview practice mode when the user wants to practice mock interviews."""
        return self._interview_agent_cls(chat_ctx=self.chat_ctx)

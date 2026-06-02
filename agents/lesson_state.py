"""
Lesson state module.

Owns the runtime lesson state for a teaching session so persona modules can
work through a small interface instead of duplicating parsing and progress
rules inline.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from agents.session_data import SessionData


DEFAULT_PHASE_ORDER = ["warmup", "concept", "practice", "exit"]
PHASE_ALIASES = {
    "warmup": ["warmup", "warm-up", "intro", "introduction", "icebreaker", "opening"],
    "concept": ["concept", "explain", "theory", "teach", "lesson"],
    "practice": ["practice", "activity", "exercise", "application", "workout"],
    "exit": ["exit", "summary", "wrap", "recap", "closing", "check-out"],
}


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _unique_preserve_order(items: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = normalize_text(item)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(item.strip())
    return result


def parse_goals(raw_goals: str | None) -> list[str]:
    if not raw_goals:
        return []

    lines = [segment.strip() for segment in re.split(r"\n|;|\|", raw_goals) if segment.strip()]
    tokens: list[str] = []

    for line in lines:
        bullet = re.sub(r"^[-*\d.)\s]+", "", line).strip()
        if "," in bullet and len(bullet) > 40:
            tokens.extend(part.strip() for part in bullet.split(",") if part.strip())
        else:
            tokens.append(bullet)

    return _unique_preserve_order(tokens)


def parse_phase_order(raw_structure: str | None) -> list[str]:
    if not raw_structure:
        return DEFAULT_PHASE_ORDER.copy()

    structure = normalize_text(raw_structure)
    detected: list[tuple[int, str]] = []

    for phase, aliases in PHASE_ALIASES.items():
        earliest_match = None
        for alias in aliases:
            index = structure.find(alias)
            if index != -1 and (earliest_match is None or index < earliest_match):
                earliest_match = index
        if earliest_match is not None:
            detected.append((earliest_match, phase))

    if not detected:
        return DEFAULT_PHASE_ORDER.copy()

    detected.sort(key=lambda item: item[0])
    ordered = [phase for _, phase in detected]

    for phase in DEFAULT_PHASE_ORDER:
        if phase not in ordered:
            ordered.append(phase)

    return ordered


def initialize_lesson_state(session_data: "SessionData") -> None:
    session_data.lesson_goal_checklist = parse_goals(session_data.session_goals)
    session_data.covered_goals = []
    session_data.lesson_phase_order = parse_phase_order(session_data.session_structure)
    session_data.current_phase_index = 0


def get_current_phase(session_data: "SessionData") -> str:
    phase_order = session_data.lesson_phase_order or DEFAULT_PHASE_ORDER
    index = max(0, min(session_data.current_phase_index, len(phase_order) - 1))
    return phase_order[index]


def get_remaining_goals(session_data: "SessionData") -> list[str]:
    covered = {normalize_text(item) for item in session_data.covered_goals}
    return [
        goal
        for goal in session_data.lesson_goal_checklist
        if normalize_text(goal) not in covered
    ]


def build_runtime_instructions(base_instructions: str, session_data: "SessionData") -> str:
    current_phase = get_current_phase(session_data)
    phase_order = session_data.lesson_phase_order or DEFAULT_PHASE_ORDER
    remaining_goals = get_remaining_goals(session_data)

    context_block = (
        "## Current Session Context\n"
        f"Title: {session_data.session_title or ''}\n"
        f"Topic: {session_data.session_topic or ''}\n"
        f"Goals: {session_data.session_goals or ''}\n"
        f"Structure: {session_data.session_structure or ''}"
    )

    governance_block = (
        "## Live Session Governance\n"
        "- Keep every response anchored to the session topic. If user drifts, acknowledge briefly and gently bring them back.\n"
        "- Follow lesson phases in order. Do not skip ahead without explicitly closing the current phase.\n"
        "- Reference the plan naturally in speech (example: our goal today is..., based on our plan...).\n"
        "- Keep track of goals using tools: call get_lesson_progress when uncertain, mark_goal_covered when a goal is achieved, and advance_lesson_phase only when phase outcomes are done.\n"
        f"- Current phase: {current_phase}\n"
        f"- Phase order: {' -> '.join(phase_order)}\n"
        f"- Covered goals: {session_data.covered_goals or 'none yet'}\n"
        f"- Remaining goals: {remaining_goals or 'all covered'}"
    )

    return f"{base_instructions}\n\n{context_block}\n\n{governance_block}"


def get_lesson_progress(session_data: "SessionData") -> dict[str, object]:
    return {
        "current_phase": get_current_phase(session_data),
        "phase_order": session_data.lesson_phase_order or DEFAULT_PHASE_ORDER,
        "covered_goals": session_data.covered_goals,
        "remaining_goals": get_remaining_goals(session_data),
    }


def mark_goal_covered(session_data: "SessionData", goal: str) -> str:
    normalized_goal = normalize_text(goal)
    if not normalized_goal:
        return "empty"

    normalized_covered = {normalize_text(item) for item in session_data.covered_goals}
    if normalized_goal in normalized_covered:
        return "already-covered"

    session_data.covered_goals.append(goal.strip())
    return "covered"


def advance_lesson_phase(session_data: "SessionData", next_phase: str | None = None) -> str:
    phase_order = session_data.lesson_phase_order or DEFAULT_PHASE_ORDER

    if not phase_order:
        session_data.lesson_phase_order = DEFAULT_PHASE_ORDER.copy()
        phase_order = session_data.lesson_phase_order

    current_index = max(0, min(session_data.current_phase_index, len(phase_order) - 1))
    target_index = current_index

    if next_phase:
        normalized_next = normalize_text(next_phase)
        for index, phase in enumerate(phase_order):
            if normalize_text(phase) == normalized_next:
                target_index = index
                break
    else:
        target_index = min(current_index + 1, len(phase_order) - 1)

    if target_index > current_index + 1:
        target_index = current_index + 1

    session_data.current_phase_index = target_index
    return phase_order[target_index]

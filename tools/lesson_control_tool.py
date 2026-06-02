"""
Lesson voice-control tool — linked list course.

Maps natural-language commands to structured lesson actions and pushes them to
the frontend via the "lesson_control" RPC method.

Supported actions
-----------------
next_step       Move the lesson forward one step.
prev_step       Move the lesson back one step.
select          Highlight / select a specific node (target: "node_N").
highlight_node  Alias for select.
goto_chapter    Jump to a lesson chapter (target: "chapter_N").
answer          Submit a checkpoint answer (target: "option_X" or comma-joined ids).
drag_order      Apply a drag-order answer (value: comma-separated ids, e.g. "3,1,4,2").
reset           Return to step 0 of chapter 1.

Natural language → action mappings the LLM should learn from the docstring:
  "go to the next step"           → action="next_step"
  "go back"                       → action="prev_step"
  "select the second node"        → action="select", target="node_2"
  "highlight node 3"              → action="highlight_node", target="node_3"
  "go to chapter 2"               → action="goto_chapter", target="chapter_2"
  "choose option B"               → action="answer", target="option_b"
  "the order is 3, 1, 4, 2"       → action="drag_order", value="3,1,4,2"
  "reset"                         → action="reset"
  "skip to insertion"             → action="goto_chapter", target="chapter_3"
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from livekit.agents import RunContext, function_tool

if TYPE_CHECKING:
    from agents.session_data import SessionData

from helpers.room_utils import send_rpc

logger = logging.getLogger("agent-UnlockPi")

_VALID_ACTIONS = frozenset({
    "next_step",
    "prev_step",
    "select",
    "highlight_node",
    "goto_chapter",
    "answer",
    "drag_order",
    "reset",
})

_SPOKEN_CONFIRMATIONS: dict[str, str] = {
    "next_step":      "Moving to the next step.",
    "prev_step":      "Going back one step.",
    "select":         "Node selected.",
    "highlight_node": "Node highlighted.",
    "goto_chapter":   "Jumping to that chapter.",
    "answer":         "Answer submitted.",
    "drag_order":     "Order applied.",
    "reset":          "Lesson reset to the beginning.",
}


def _update_course_context(session_data: SessionData, action: str, target: str) -> None:
    """Optimistically update the backend's view of lesson position.

    The frontend is the authoritative source of truth; this keeps the LLM's
    system prompt roughly in sync so it can reference the current position.
    """
    ctx = dict(session_data.course_context)

    if action in ("next_step",):
        ctx["step"] = ctx.get("step", 0) + 1
    elif action in ("prev_step",):
        ctx["step"] = max(0, ctx.get("step", 0) - 1)
    elif action == "goto_chapter":
        # target like "chapter_2" → chapter number 2
        try:
            chapter_num = int(target.split("_")[-1])
            ctx["chapter"] = chapter_num
            ctx["step"] = 0
        except ValueError:
            pass
    elif action == "reset":
        ctx["chapter"] = 1
        ctx["step"] = 0

    session_data.course_context = ctx


@function_tool()
async def control_lesson(
    context: RunContext[SessionData],
    action: str,
    target: str = "",
    value: str = "",
) -> str:
    """Control the interactive linked list lesson displayed on screen.

    Use this tool whenever the student speaks a navigation command, selects a
    node, answers a checkpoint question, or asks to jump to a different chapter.
    Keep your spoken response to ONE sentence — the student is watching the screen.

    Args:
        action: One of: next_step | prev_step | select | highlight_node |
                goto_chapter | answer | drag_order | reset
        target: Node id (e.g. "node_2"), chapter (e.g. "chapter_3"), or
                option id (e.g. "option_b"). Leave empty when not applicable.
        value:  Extra data — used for drag_order (e.g. "3,1,4,2"). Empty otherwise.

    Returns:
        A short spoken confirmation for TTS (one sentence).
    """
    action = action.strip().lower()

    if action not in _VALID_ACTIONS:
        return (
            f"I don't recognise the action '{action}'. "
            "Try: next step, go back, select node, go to chapter, answer, or reset."
        )

    session_data = context.userdata

    # Update backend course context so the system prompt stays accurate
    _update_course_context(session_data, action, target)

    payload = {
        "action": action,
        "target": target.strip(),
        "value": value.strip(),
        "course_context": session_data.course_context,
    }

    try:
        await send_rpc("lesson_control", payload)
    except Exception as exc:
        logger.warning("lesson_control RPC failed: %s", exc)
        return "I couldn't reach the lesson display right now — please try again."

    return _SPOKEN_CONFIRMATIONS.get(action, "Done.")

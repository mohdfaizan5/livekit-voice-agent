"""
PiTutorAgent — 

Loads its system prompt from prompts/mit-tutor.md. Simulates as tutor for a live session, guiding the user through a structured learning experience based on provided session context (title, topic, goals, structure). Keeps track of lesson phases and goal coverage, and provides tools to update this information.
Supports handoff to InterviewAgent for mock interviews.
"""

import logging

from livekit.agents import RunContext, function_tool
from agents.lesson_state import (
    advance_lesson_phase as advance_session_lesson_phase,
    build_runtime_instructions,
    get_lesson_progress as get_session_lesson_progress,
    initialize_lesson_state,
    mark_goal_covered as mark_session_goal_covered,
)
from agents.persona import PromptDrivenAgent
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


class PiTutorAgent(PromptDrivenAgent):
    """
    Engages as the visionary leader of manipal academy of higher education,
    discussing  education, careers,
    """
    # JUNK: runs cognitive tests, and manages team scores.

    def __init__(self, chat_ctx=None) -> None:
        # Lazy import to avoid circular dependency
        from agents.interview_agent import InterviewAgent  # noqa: F811

        self._interview_agent_cls = InterviewAgent

        super().__init__(
            prompt_filename="mit-tutor.md",
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
        await self.update_instructions(
            build_runtime_instructions(self._base_instructions, session_data)
        )

    async def on_enter(self):
        """Called when the agent joins. Sends a short greeting."""
        session_data = self.session.userdata
        initialize_lesson_state(session_data)

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
        return get_session_lesson_progress(context.userdata)

    @function_tool()
    async def mark_goal_covered(self, context: RunContext, goal: str):
        """Mark a learning goal as covered when the learner demonstrates understanding."""
        session_data = context.userdata
        mark_result = mark_session_goal_covered(session_data, goal)
        if mark_result == "empty":
            return "No goal provided."
        if mark_result == "already-covered":
            return f"Goal already covered: {goal.strip()}"

        await self._apply_runtime_session_instructions()
        return f"Goal marked covered: {goal.strip()}"

    @function_tool()
    async def advance_lesson_phase(self, context: RunContext, next_phase: str | None = None):
        """Advance lesson phase in sequence when current phase objectives are complete."""
        session_data = context.userdata
        current_phase = advance_session_lesson_phase(session_data, next_phase)
        await self._apply_runtime_session_instructions()
        return f"Current phase is now: {current_phase}"

    # ------------------------------------------------------------------
    # Handoff tool: transfer to interview mode
    # ------------------------------------------------------------------
    @function_tool()
    async def transfer_to_interview(self, context: RunContext):
        """Transfer to interview practice mode when the user wants to practice mock interviews."""
        return self._interview_agent_cls(chat_ctx=self.chat_ctx)

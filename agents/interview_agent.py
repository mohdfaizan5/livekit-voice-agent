"""
InterviewAgent — Dr. Kini mock interview simulator.

Loads its system prompt from prompts/mit-interview.md.
Supports handoff back to PiTutorAgent when done.
"""
# Conducts interviews in Dr. Kini's persona.

import logging

from livekit.agents import RunContext, function_tool

from agents.persona import PromptDrivenAgent
from tools import update_content, write_to_board, clear_board_content, render_visual

logger = logging.getLogger("agent-UnlockPi")

class InterviewAgent(PromptDrivenAgent):
    """
    Dr. Kini Interview Simulator.
    You take interview as Dr. Kini, a seasoned interviewer with a sharp eye for talent. 
    """

    def __init__(self, chat_ctx=None) -> None:
        # Lazy import to avoid circular dependency
        from agents.tutor_agent import PiTutorAgent  # noqa: F811

        self._tutor_agent_cls = PiTutorAgent

        super().__init__(
            prompt_filename="mit-interview.md",
            chat_ctx=chat_ctx,
            tools=[
                update_content,
                render_visual,
                write_to_board,
                clear_board_content,
            ],
        )

    async def on_enter(self):
        """Greet and set context when entering interview mode as Dr. Kini."""
        await self.session.generate_reply(
            instructions=(
                "Greet the candidate as Dr. Kini, Your interviewer. "
                "Remind them that industry hires skills, not degrees. "
                "Ask if they are ready to begin."
            ),
            allow_interruptions=True,
        )

    @function_tool()
    async def transfer_to_tutor(self, context: RunContext):
        """Transfer back to tutor mode when the user wants to stop the interview, end practice, go back, exit interview, or return to the main conversation."""
        return self._tutor_agent_cls(chat_ctx=self.chat_ctx)

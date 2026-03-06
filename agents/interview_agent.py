"""
InterviewAgent — Dr. Arya mock interview simulator.

Loads its system prompt from prompts/interview.md.
Supports handoff back to PiTutorAgent when done.
"""
# Conducts mechanical engineering interviews in Dr. Arya's persona.

import os
import logging

from livekit.agents import Agent, RunContext, function_tool

from config import PROMPTS_DIR
from tools.display_tools import update_content

logger = logging.getLogger("agent-UnlockPi")


def _load_prompt(filename: str) -> str:
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class InterviewAgent(Agent):
    """
    Dr. Arya Interview Simulator.
    interviews in the persona of Dr. Bheemsen Arya, Principal of BMSCE.
    """
    #   Conducts mock mechanical engineering

    def __init__(self, chat_ctx=None) -> None:
        # Lazy import to avoid circular dependency
        from agents.tutor_agent import PiTutorAgent  # noqa: F811

        self._tutor_agent_cls = PiTutorAgent

        super().__init__(
            instructions=_load_prompt("interview.md"),
            chat_ctx=chat_ctx,
            tools=[
                update_content,
            ],
        )

    async def on_enter(self):
        """Greet and set context when entering interview mode as Dr. Arya."""
        await self.session.generate_reply(
            instructions=(
                "Greet the candidate as Dr. Bheemsen Arya. "
                # "Explain that you will conduct a mock mechanical engineering interview. "
                "Remind them that industry hires skills, not degrees. "
                "Ask if they are ready to begin."
            ),
            allow_interruptions=True,
        )

    @function_tool()
    async def transfer_to_tutor(self, context: RunContext):
        """End the interview and return to classroom mode."""
        return self._tutor_agent_cls(chat_ctx=self.chat_ctx)

"""
PiTutorAgent — Dr. Bheemsen Arya simulation.

Loads its system prompt from prompts/bmsc-tutor.md. Simulates Dr. Arya,
Principal of BMSCE, discussing engineering education and Viksit Bharat 2047.
Supports handoff to InterviewAgent for mock interviews.
"""

import os
import logging

from livekit.agents import Agent, RunContext, function_tool

from config import PROMPTS_DIR
from tools import (
    highlight_text,
    update_content,
    start_cognitive_test,
    update_team_score,
    get_team_scores,
)

logger = logging.getLogger("agent-UnlockPi")


def _load_prompt(filename: str) -> str:
    """Load a prompt file from the prompts/ directory."""
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class PiTutorAgent(Agent):
    """
    Dr. Arya simulation agent. Engages as the visionary Principal of BMSCE,
    discussing engineering education, careers, and Viksit Bharat 2047.
    """
    # JUNK: runs cognitive tests, and manages team scores.

    def __init__(self, chat_ctx=None) -> None:
        # Lazy import to avoid circular dependency
        from agents.interview_agent import InterviewAgent  # noqa: F811

        self._interview_agent_cls = InterviewAgent

        super().__init__(
            instructions=_load_prompt("bmsce-tutor.md"),
            chat_ctx=chat_ctx,
            tools=[
                highlight_text,
                update_content,
                # start_cognitive_test,
                # update_team_score,
                # get_team_scores,
            ],
        )

    async def on_enter(self):
        """Called when the agent joins. Sends a short greeting."""
        await self.session.generate_reply(
            instructions="Greet the user, keep it short.",
            allow_interruptions=True,
        )

    # ------------------------------------------------------------------
    # Handoff tool: transfer to interview mode
    # ------------------------------------------------------------------
    @function_tool()
    async def transfer_to_interview(self, context: RunContext):
        """Transfer to interview practice mode when the user wants to practice mock interviews."""
        return self._interview_agent_cls(chat_ctx=self.chat_ctx)

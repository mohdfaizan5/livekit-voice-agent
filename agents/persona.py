"""
Shared persona module.

Keeps prompt loading and prompt-driven agent construction behind one seam so
persona modules stay focused on behavior unique to that teaching mode.
"""

from __future__ import annotations

import os
from collections.abc import Sequence

from livekit.agents import Agent

from config import PROMPTS_DIR


def load_prompt(filename: str) -> str:
    """Load a prompt file from the prompts directory."""
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


class PromptDrivenAgent(Agent):
    """Base module for personas backed by a prompt file and shared tool list."""

    def __init__(
        self,
        *,
        prompt_filename: str,
        chat_ctx=None,
        tools: Sequence[object] = (),
    ) -> None:
        self._base_instructions = load_prompt(prompt_filename)
        super().__init__(
            instructions=self._base_instructions,
            chat_ctx=chat_ctx,
            tools=list(tools),
        )

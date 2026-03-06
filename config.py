"""
Centralized configuration for the UnlockPi voice agent.

All model names, voice IDs, environment variable keys, and other settings
that were previously hardcoded across agent.py live here.
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv(".env.local")


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
NEONDB_URL: str | None = os.environ.get("NEONDB_API_KEY")


# ---------------------------------------------------------------------------
# Agent identity
# ---------------------------------------------------------------------------
AGENT_NAME = "UnlockPi"


# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class STTConfig:
    model: str = "assemblyai/universal-streaming-multilingual"
    language: str = "en-IN"


@dataclass(frozen=True)
class LLMConfig:
    model: str = "openai/gpt-4.1-mini"


@dataclass(frozen=True)
class TTSConfig:
    model: str = "inworld/inworld-tts-1-max"
    voice: str = "Arjun"
    language: str = "en"
# @dataclass(frozen=True)
# class TTSConfig:
#     model: str = "elevenlabs/eleven_turbo_v2_5"
#     voice: str = "mCQMfsqGDT6IDkEKR20a" # jeevan
#     language: str = "en"

@dataclass(frozen=True)
class ModelConfig:
    stt: STTConfig = field(default_factory=STTConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)


# Default model configuration instance
models = ModelConfig()


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROMPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")

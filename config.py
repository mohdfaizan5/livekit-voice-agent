"""
Centralized configuration for the UnlockPi voice agent.

All model names, voice IDs, environment variable keys, and other settings
that were previously hardcoded across agent.py live here.
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv(".env.local")


def _csv_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.environ.get(name)
    if value is None:
        return default

    items = tuple(item.strip() for item in value.split(",") if item.strip())
    return items or default


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
NEONDB_URL: str | None = (
    os.environ.get("NEONDB_URL")
    or os.environ.get("DATABASE_URL")
    or os.environ.get("SUPABASE_DB_URL")
    or os.environ.get("NEONDB_API_KEY")
)


# ---------------------------------------------------------------------------
# Agent identity
# ---------------------------------------------------------------------------
AGENT_NAME = "UnlockPi"


# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class STTConfig:
    model: str = field(default_factory=lambda: os.environ.get("LIVEKIT_STT_MODEL", "assemblyai/universal-streaming-multilingual"))
    language: str = field(default_factory=lambda: os.environ.get("LIVEKIT_STT_LANGUAGE", "en-IN"))
    fallback_models: tuple[str, ...] = field(
        default_factory=lambda: _csv_env(
            "LIVEKIT_STT_FALLBACK_MODELS",
            ("deepgram/nova-3", "cartesia/ink-whisper"),
        )
    )


@dataclass(frozen=True)
class LLMConfig:
    model: str = field(default_factory=lambda: os.environ.get("LIVEKIT_LLM_MODEL", "openai/gpt-4.1-mini"))
    fallback_models: tuple[str, ...] = field(
        default_factory=lambda: _csv_env(
            "LIVEKIT_LLM_FALLBACK_MODELS",
            ("google/gemini-2.5-flash",),
        )
    )


@dataclass(frozen=True)
class TTSConfig:
    model: str = field(default_factory=lambda: os.environ.get("LIVEKIT_TTS_MODEL", "inworld/inworld-tts-1-max"))
    voice: str = field(default_factory=lambda: os.environ.get("LIVEKIT_TTS_VOICE", "Arjun"))
    language: str = field(default_factory=lambda: os.environ.get("LIVEKIT_TTS_LANGUAGE", "en"))
    fallback_models: tuple[str, ...] = field(
        default_factory=lambda: _csv_env(
            "LIVEKIT_TTS_FALLBACK_MODELS",
            ("cartesia/sonic-3:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",),
        )
    )


@dataclass(frozen=True)
class TurnDetectionConfig:
    model: str = field(default_factory=lambda: os.environ.get("LIVEKIT_TURN_DETECTION_MODEL", "english"))


@dataclass(frozen=True)
class RealtimeConfig:
    """OpenAI Realtime model config — used only when course_mode is active."""
    model: str = field(default_factory=lambda: os.environ.get("OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview"))
    voice: str = field(default_factory=lambda: os.environ.get("OPENAI_REALTIME_VOICE", "alloy"))
    # OPENAI_API_KEY — required for course_mode sessions; read automatically by the OpenAI SDK
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
    turn_detection: TurnDetectionConfig = field(default_factory=TurnDetectionConfig)
    realtime: RealtimeConfig = field(default_factory=RealtimeConfig)


# Default model configuration instance
models = ModelConfig()


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROMPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")

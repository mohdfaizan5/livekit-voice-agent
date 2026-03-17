from __future__ import annotations

from config import LLMConfig, STTConfig, TTSConfig


def _append_suffix_if_missing(descriptor: str, suffix: str) -> str:
    if not suffix or ":" in descriptor:
        return descriptor
    return f"{descriptor}:{suffix}"


def stt_fallback_descriptors(config: STTConfig) -> tuple[str, ...]:
    return tuple(_append_suffix_if_missing(model, config.language) for model in config.fallback_models)


def llm_model_chain(config: LLMConfig) -> tuple[str, ...]:
    return (config.model, *config.fallback_models)


def tts_model_chain(config: TTSConfig) -> tuple[str, ...]:
    return (f"{config.model}:{config.voice}", *config.fallback_models)


def describe_fallback_chains(
    stt_config: STTConfig,
    llm_config: LLMConfig,
    tts_config: TTSConfig,
) -> dict[str, list[str]]:
    return {
        "stt": [f"{stt_config.model}:{stt_config.language}", *stt_fallback_descriptors(stt_config)],
        "llm": list(llm_model_chain(llm_config)),
        "tts": list(tts_model_chain(tts_config)),
    }

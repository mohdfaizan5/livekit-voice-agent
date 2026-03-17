import unittest

from config import LLMConfig, STTConfig, TTSConfig
from helpers.model_fallbacks import (
    describe_fallback_chains,
    llm_model_chain,
    stt_fallback_descriptors,
    tts_model_chain,
)


class ModelFallbacksTests(unittest.TestCase):
    def test_stt_fallbacks_inherit_language_when_missing(self) -> None:
        config = STTConfig(
            model="assemblyai/universal-streaming-multilingual",
            language="en-IN",
            fallback_models=("deepgram/nova-3", "cartesia/ink-whisper:multi"),
        )

        self.assertEqual(
            stt_fallback_descriptors(config),
            ("deepgram/nova-3:en-IN", "cartesia/ink-whisper:multi"),
        )

    def test_llm_chain_keeps_primary_first(self) -> None:
        config = LLMConfig(
            model="openai/gpt-4.1-mini",
            fallback_models=("google/gemini-2.5-flash", "openai/gpt-5-mini"),
        )

        self.assertEqual(
            llm_model_chain(config),
            ("openai/gpt-4.1-mini", "google/gemini-2.5-flash", "openai/gpt-5-mini"),
        )

    def test_tts_chain_preserves_primary_voice_descriptor(self) -> None:
        config = TTSConfig(
            model="inworld/inworld-tts-1-max",
            voice="Arjun",
            language="en",
            fallback_models=("cartesia/sonic-3:voice-id-1", "elevenlabs/eleven_flash_v2_5:voice-id-2"),
        )

        self.assertEqual(
            tts_model_chain(config),
            (
                "inworld/inworld-tts-1-max:Arjun",
                "cartesia/sonic-3:voice-id-1",
                "elevenlabs/eleven_flash_v2_5:voice-id-2",
            ),
        )

    def test_describe_fallback_chains_returns_full_summary(self) -> None:
        summary = describe_fallback_chains(
            STTConfig(
                model="assemblyai/universal-streaming-multilingual",
                language="en-IN",
                fallback_models=("deepgram/nova-3",),
            ),
            LLMConfig(
                model="openai/gpt-4.1-mini",
                fallback_models=("google/gemini-2.5-flash",),
            ),
            TTSConfig(
                model="inworld/inworld-tts-1-max",
                voice="Arjun",
                language="en",
                fallback_models=("cartesia/sonic-3:voice-id-1",),
            ),
        )

        self.assertEqual(
            summary,
            {
                "stt": [
                    "assemblyai/universal-streaming-multilingual:en-IN",
                    "deepgram/nova-3:en-IN",
                ],
                "llm": [
                    "openai/gpt-4.1-mini",
                    "google/gemini-2.5-flash",
                ],
                "tts": [
                    "inworld/inworld-tts-1-max:Arjun",
                    "cartesia/sonic-3:voice-id-1",
                ],
            },
        )


if __name__ == "__main__":
    unittest.main()

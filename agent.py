"""
UnlockPi Voice Agent — entrypoint.

This is the slim orchestration layer.  All business logic lives in:
    agents/   — Agent classes (PiTutorAgent, InterviewAgent)
    tools/    — Standalone @function_tool functions
    helpers/  — Room utilities, DB helpers
    prompts/  — Markdown prompt files
    config.py — Centralised settings
"""

import logging
import json
import os
from livekit.agents import llm
from livekit import rtc
from supabase import create_client, Client
from livekit.agents import (
    APIConnectOptions,
    AgentSession,
    AgentServer,
    JobContext,
    JobProcess,
    cli,
    inference,
    room_io,
)
from livekit.agents.metrics import EOUMetrics, LLMMetrics, STTMetrics, TTSMetrics
from livekit.agents.metrics.utils import log_metrics
from livekit.plugins import noise_cancellation, silero
from livekit.plugins.turn_detector.english import EnglishModel
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from config import AGENT_NAME, models
from agents import PiTutorAgent, SessionData
from helpers.model_fallbacks import (
    describe_fallback_chains,
    llm_model_chain,
    stt_fallback_descriptors,
)

logger = logging.getLogger("agent-UnlockPi")

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
server = AgentServer()


def prewarm(proc: JobProcess):
    """Pre-load the Silero VAD model so first session starts faster."""
    proc.userdata["vad"] = silero.VAD.load()


def build_turn_detector():
    if models.turn_detection.model == "multilingual":
        return MultilingualModel()

    return EnglishModel()


server.setup_fnc = prewarm


@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: JobContext):
    """
    Per-session entry point.
    Sets up DB → session config → agent → room connection → cleanup.
    """
    # 1. Shared session state (accessible in tools via context.userdata)
    session_data = SessionData()

    metadata_json = ""
    try:
        metadata_json = getattr(ctx.job, "metadata", "") or ""
    except Exception:
        metadata_json = ""

    if not metadata_json:
        try:
            metadata_json = getattr(ctx._info.accept_arguments, "metadata", "") or ""
        except Exception:
            metadata_json = ""

    session_id: str | None = None
    course_mode_active: bool = False
    if metadata_json:
        try:
            parsed_metadata = json.loads(metadata_json)
            if isinstance(parsed_metadata, dict):
                raw_session_id = parsed_metadata.get("session_id")
                if isinstance(raw_session_id, str) and raw_session_id.strip():
                    session_id = raw_session_id.strip()
                # course_mode: activate realtime pipeline for interactive lessons
                course_mode_active = bool(parsed_metadata.get("course_mode", False))
                if course_mode_active:
                    session_data.course_mode = True
                    raw_ctx = parsed_metadata.get("course_context", {})
                    if isinstance(raw_ctx, dict):
                        session_data.course_context = raw_ctx
        except Exception as err:
            logger.warning("Failed to parse job metadata JSON: %s", err)

    if not session_id:
        logger.info("No session_id found in job metadata; skipping session context load")

    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    supabase_client: Client | None = None

    if supabase_url and supabase_service_role_key:
        try:
            supabase_client = create_client(supabase_url, supabase_service_role_key)
        except Exception as err:
            logger.warning("Failed to initialize Supabase client: %s", err)
    else:
        logger.warning("Supabase client unavailable; check SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")

    if session_id and supabase_client:
        try:
            response = (
                supabase_client.table("teaching_sessions")
                .select("title,topic,learning_goals,lesson_structure")
                .eq("id", session_id)
                .single()
                .execute()
            )
            data = response.data if response and response.data else {}

            session_data.session_title = data.get("title")
            session_data.session_topic = data.get("topic")
            session_data.session_goals = data.get("learning_goals") or data.get("goals")
            session_data.session_structure = data.get("lesson_structure") or data.get("structure")

            if any([
                session_data.session_title,
                session_data.session_topic,
                session_data.session_goals,
                session_data.session_structure,
            ]):
                logger.info("Loaded session context for session_id=%s", session_id)
            else:
                logger.info("No teaching session context found for session_id=%s", session_id)
        except Exception as err:
            logger.warning("Failed to load teaching session context for session_id=%s: %s", session_id, err)

    llm_chain = [
        inference.LLM(model=model_name)
        for model_name in llm_model_chain(models.llm)
    ]
    configured_fallbacks = describe_fallback_chains(models.stt, models.llm, models.tts)
    logger.info("Configured model fallbacks: %s", configured_fallbacks)

    # 3. Voice pipeline
    if course_mode_active:
        # Course mode: single OpenAI Realtime model handles STT + LLM + TTS end-to-end.
        # Low latency is critical so the student sees lesson updates instantly.
        from livekit.plugins import openai as lk_openai

        logger.info(
            "course_mode active — using RealtimeModel(%s, voice=%s)",
            models.realtime.model,
            models.realtime.voice,
        )
        session = AgentSession[SessionData](
            userdata=session_data,
            llm=lk_openai.realtime.RealtimeModel(
                model=models.realtime.model,
                voice=models.realtime.voice,
                temperature=0.7,
            ),
            vad=ctx.proc.userdata["vad"],
        )
    else:
        # Standard pipeline: AssemblyAI STT → GPT-4.1-mini → Inworld TTS.
        # DO NOT MODIFY THIS BLOCK.
        session = AgentSession[SessionData](
            userdata=session_data,
            stt=inference.STT(
                model=models.stt.model,
                language=models.stt.language,
                fallback=list(stt_fallback_descriptors(models.stt)),
                conn_options=APIConnectOptions(
                    max_retry=1,
                    retry_interval=0.5,
                    timeout=6.0,
                ),
            ),
            llm=llm.FallbackAdapter(
                llm=llm_chain,
                attempt_timeout=2.5,
                retry_interval=0.25,
            ),
            tts=inference.TTS(
                model=models.tts.model,
                voice=models.tts.voice,
                language=models.tts.language,
                fallback=list(models.tts.fallback_models),
                conn_options=APIConnectOptions(
                    max_retry=1,
                    retry_interval=0.5,
                    timeout=6.0,
                ),
            ),
            turn_detection=build_turn_detector(),
            vad=ctx.proc.userdata["vad"],
            preemptive_generation=True,
        )

    @session.on("metrics_collected")
    def on_metrics_collected(ev) -> None:
        metrics = ev.metrics
        if isinstance(metrics, (EOUMetrics, LLMMetrics, STTMetrics, TTSMetrics)):
            log_metrics(metrics, logger=logger)

    # 4. Start the agent
    await session.start(
        agent=PiTutorAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )

if __name__ == "__main__":
    cli.run_app(server)

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
from livekit.agents import llm
from livekit import rtc
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
from livekit.plugins import noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from config import AGENT_NAME, models
from agents import PiTutorAgent, SessionData
from helpers.db import create_db_pool, close_db_pool
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


server.setup_fnc = prewarm


@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: JobContext):
    """
    Per-session entry point.
    Sets up DB → session config → agent → room connection → cleanup.
    """
    # 1. Database
    db_pool = await create_db_pool()

    # 2. Shared session state (accessible in tools via context.userdata)
    session_data = SessionData(db_pool=db_pool)

    async def on_job_shutdown(reason: str) -> None:
        logger.info("Job shutting down", extra={"shutdown_reason": reason})
        await close_db_pool(db_pool)

    ctx.add_shutdown_callback(on_job_shutdown)

    llm_chain = [
        inference.LLM(model=model_name)
        for model_name in llm_model_chain(models.llm)
    ]
    configured_fallbacks = describe_fallback_chains(models.stt, models.llm, models.tts)
    logger.info("Configured model fallbacks: %s", configured_fallbacks)

    # 3. Voice pipeline
    session = AgentSession[SessionData](
        userdata=session_data,
        stt=inference.STT(
            model=models.stt.model,
            language=models.stt.language,
            fallback=list(stt_fallback_descriptors(models.stt)),
            conn_options=APIConnectOptions(
                max_retry=8,
                retry_interval=2.0,
                timeout=15.0,
            ),
        ),
        llm=llm.FallbackAdapter(
            llm=llm_chain,
        ),
        tts=inference.TTS(
            model=models.tts.model,
            voice=models.tts.voice,
            language=models.tts.language,
            fallback=list(models.tts.fallback_models),
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

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

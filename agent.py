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

from livekit import rtc
from livekit.agents import (
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

    # 3. Voice pipeline
    session = AgentSession[SessionData](
        userdata=session_data,
        stt=inference.STT(
            model=models.stt.model,
            language=models.stt.language,
        ),
        llm=inference.LLM(model=models.llm.model),
        tts=inference.TTS(
            model=models.tts.model,
            voice=models.tts.voice,
            language=models.tts.language,
            
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

    # 5. Cleanup on disconnect
    @ctx.room.on("disconnected")
    async def on_room_disconnected():
        await close_db_pool(db_pool)


if __name__ == "__main__":
    cli.run_app(server)

"""
Score tools — team score management via database + frontend sync.

The DB pool is accessed from context.userdata.db_pool.
"""

import json
import logging

from livekit.agents import RunContext, function_tool

from helpers.room_utils import get_frontend_identity, send_rpc

logger = logging.getLogger("agent-UnlockPi")


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------
async def _sync_scores_to_frontend(db_pool, frontend_id: str) -> str:
    """Fetch all scores from DB and push them to the frontend."""
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT name, score FROM teams")

        scores = {r["name"]: r["score"] for r in rows}
        await send_rpc("update_scores", {"scores": scores}, frontend_id=frontend_id)
        return "Synced with board."
    except Exception as e:
        logger.error(f"Score sync failed: {e}")
        return "Failed to sync board."


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
@function_tool()
async def update_team_score(
    context: RunContext,
    team_name: str,
    points: int,
) -> str:
    """Updates the score for a specific team in the database and updates the board.

    Args:
        team_name: "Team Alpha", "Team Beta", or "Team Gamma" (case insensitive).
        points: Points to add (can be negative).
    """
    db_pool = getattr(context.userdata, "db_pool", None) if hasattr(context, "userdata") else None
    if not db_pool:
        return "Database is not available — cannot update scores."

    frontend_id = get_frontend_identity()

    # Normalize team name
    normalized_name = team_name.title()
    if "Alpha" in normalized_name:
        normalized_name = "Team Alpha"
    elif "Beta" in normalized_name:
        normalized_name = "Team Beta"
    elif "Gamma" in normalized_name:
        normalized_name = "Team Gamma"
    else:
        return f"Unknown team: {team_name}. Please use Alpha, Beta, or Gamma."

    try:
        async with db_pool.acquire() as conn:
            new_score = await conn.fetchval(
                "UPDATE teams SET score = score + $1 WHERE name = $2 RETURNING score",
                points, normalized_name
            )

        if new_score is None:
            return f"Team {normalized_name} not found in database."

        # Send update to frontend
        if frontend_id:
            score_summary = await _sync_scores_to_frontend(db_pool, frontend_id)
            return f"Updated {normalized_name} score to {new_score}. {score_summary}"

        return f"Updated {normalized_name} score to {new_score} (display not connected)."

    except Exception as e:
        logger.error(f"update_team_score failed: {e}")
        return f"Failed to update score: {str(e)}"


@function_tool()
async def get_team_scores(
    context: RunContext,
) -> str:
    """Fetches the current scores for all teams from the database."""
    db_pool = getattr(context.userdata, "db_pool", None) if hasattr(context, "userdata") else None
    if not db_pool:
        return "Database is not available — cannot fetch scores."

    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT name, score FROM teams ORDER BY name")

        summary = ", ".join([f"{r['name']}: {r['score']}" for r in rows])
        return f"Current Scores: {summary}"
    except Exception as e:
        logger.error(f"get_team_scores failed: {e}")
        return f"Failed to fetch scores: {str(e)}"

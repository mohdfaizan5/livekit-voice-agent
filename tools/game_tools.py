"""
Game tools — cognitive test (Family Feud style) game management.

State (current_answers) is stored on session.userdata.current_answers
so it persists across tool calls and agent handoffs.
"""

import json
import logging
from typing import Any

from livekit.agents import RunContext, function_tool

from helpers.room_utils import get_frontend_identity, send_rpc

logger = logging.getLogger("agent-UnlockPi")


@function_tool()
async def start_cognitive_test(
    context: RunContext,
    question: str,
    answers: str,
) -> str:
    """Starts a new 'Cognitive Test' (Family Feud style) game round.
    Don't reveal answers until the instructor asks to reveal them.

    Args:
        question: The question to ask (e.g., "Top 5 programming languages").
        answers: JSON string of answers. Example:
                 '[{"text": "Python", "percentage": 40}, {"text": "JavaScript", "percentage": 30}]'
    """
    frontend_id = get_frontend_identity()
    logger.info(f"Frontend ID: {frontend_id}")
    if not frontend_id:
        logger.warning("No frontend participant found in room")
        return "Could not find the classroom display."

    try:
        parsed_answers = json.loads(answers)

        # Store answers on session userdata for later checking
        if hasattr(context, "userdata") and hasattr(context.userdata, "current_answers"):
            context.userdata.current_answers = parsed_answers

        payload = json.dumps({
            "question": question,
            "answers": parsed_answers,
        })
        logger.debug(f"Sending RPC payload to {frontend_id}: {payload[:100]}...")

        await send_rpc("start_cognitive_test", payload, frontend_id=frontend_id)

        logger.info(f"RPC call successful for question: {question}")
        return f"Started cognitive test: {question}"
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in answers: {e}")
        return "Failed to start test: Invalid answers format"
    except Exception as e:
        logger.error(f"start_cognitive_test RPC failed: {type(e).__name__}: {e}", exc_info=True)
        return f"Failed to start test: {str(e)}"


# ---------------------------------------------------------------------------
# check_cognitive_answer — currently disabled, uncomment when ready
# ---------------------------------------------------------------------------
# @function_tool()
# async def check_cognitive_answer(
#     context: RunContext,
#     user_answer: str,
# ) -> str:
#     """Checks if a spoken answer matches any hidden answers in the current game.
#
#     If it matches, it reveals the answer on the board.
#     If it doesn't match, it triggers the error buzzer.
#
#     Args:
#         user_answer: The answer given by the user/team.
#     """
#     frontend_id = get_frontend_identity()
#     if not frontend_id:
#         return "Could not find the classroom display."
#
#     current_answers = []
#     if hasattr(context, "userdata") and hasattr(context.userdata, "current_answers"):
#         current_answers = context.userdata.current_answers
#
#     if not current_answers:
#         return "No active game found. Please start a cognitive test first."
#
#     # Simple fuzzy matching
#     match_index = -1
#     matched_text = ""
#     clean_user_input = user_answer.lower().strip()
#
#     for i, ans in enumerate(current_answers):
#         if ans["text"].lower() in clean_user_input or clean_user_input in ans["text"].lower():
#             match_index = i
#             matched_text = ans["text"]
#             break
#
#     try:
#         if match_index != -1:
#             await send_rpc("reveal_answer", {"index": match_index}, frontend_id=frontend_id)
#             return f"Correct! Revealed '{matched_text}' on the board."
#         else:
#             await send_rpc("show_error_buzzer", {}, frontend_id=frontend_id)
#             return f"Wrong answer! {user_answer} is not on the board."
#     except Exception as e:
#         logger.error(f"check_cognitive_answer RPC failed: {e}")
#         return f"Failed to check answer: {str(e)}"

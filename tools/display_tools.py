"""
Display tools — control the classroom board via RPC.

These are standalone @function_tool functions (not Agent methods) so they
can be shared across multiple agent classes via `tools=[...]`.
"""
# https://elevenlabs.io/app/voice-library?voiceId=N3skSTGkjEMsGNVewxOA
import json
import logging

from livekit.agents import RunContext, function_tool

from helpers.room_utils import get_frontend_identity, send_rpc
from helpers.board_engine import create_empty_board

logger = logging.getLogger("agent-UnlockPi")


@function_tool()
async def highlight_text(
    context: RunContext,
    words: str,
) -> str:
    """Highlight specific words on the classroom display.

    Call this to emphasize key terms using visual highlights or underlines.

    Args:
        words: A JSON string containing an array of objects. Each object must have:
               - "word": The text to match.
               - "type": One of:
                   * "highlight" (Red background - default for emphasis)
                   * "underline" (Red underline - used for definitions/verbs)
                   * "secondary" (Blue highlight - used for contrasting concepts)
               Example: [{"word": "velocity", "type": "highlight"}, {"word": "speed", "type": "secondary"}]

    Returns:
        Confirmation string.
    """
    frontend_id = get_frontend_identity()
    if not frontend_id:
        return "Could not find the classroom display to send highlights to."

    try:
        word_list = json.loads(words) if isinstance(words, str) else words

        payload = json.dumps({
            "action": "highlight",
            "words": word_list,
        })

        await send_rpc("highlight_text", payload, frontend_id=frontend_id)

        # Count types for the confirmation
        type_counts: dict[str, int] = {}
        for w in word_list:
            t = w.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        summary = ", ".join(f"{count} {t}s" for t, count in type_counts.items())
        return f"Successfully highlighted {summary} on the display."

    except Exception as e:
        logger.error(f"highlight_text RPC failed: {e}")
        return f"Failed to send highlights: {str(e)}"


@function_tool()
async def update_content(
    context: RunContext,
    text: str,
) -> str:
    """Update the classroom board with new content. Supports Markdown formatting.

    Call this when the instructor asks to show, display, or put text on screen.
    Previous content and highlights are cleared.

    You can use Markdown formatting in the text:
    - Tables: | Col1 | Col2 |
    - Math formulas: $E=mc^2$ or $$\\int_0^1 x^2 dx$$
    - Checklists: - [x] Done  - [ ] Pending
    - Code/ASCII diagrams: ```text ... ```
    - Mermaid diagrams: Use flowchart syntax for consistent rendering
      * Syntax: ```mermaid\\nflowchart TD\\n  A["Label"] --> B["Label"]\\n```
      * ALWAYS use flowchart TD (not graph TD) for predictable behavior
      * ALWAYS wrap labels in double quotes: A["Text here"]
      * This is CRITICAL for labels with special characters like parentheses, brackets, or numbers
      * Example: A["Glucose (C6H12O6)"] --> B["Oxygen (O2)"]
    - Bold, italic, headings, lists, etc.
    - If asked to change node color in mermaid, ensure font contrasts with background.
    - Prefer using left to right in flowcharts.

    Args:
        text: Markdown-formatted text content for the classroom board.

    Returns:
        Confirmation that the content was updated.
    """
    frontend_id = get_frontend_identity()
    if not frontend_id:
        return "Could not find the classroom display to update."

    try:
        # Keep backend session state aligned with legacy markdown mode so the
        # frontend does not continue preferring stale structured board content.
        context.userdata.board_document = create_empty_board()
        await send_rpc("update_content", {"text": text}, frontend_id=frontend_id)
        return f"Updated the display with new content: '{text[:50]}...'"

    except Exception as e:
        logger.error(f"update_content RPC failed: {e}")
        return f"Failed to update content: {str(e)}"

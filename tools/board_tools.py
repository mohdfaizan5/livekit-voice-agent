"""
Board tools - structured board operations via RPC.

These are standalone @function_tool functions for the structured board system.
The board is a document tree (BoardDocument -> Block[] -> Line[]).
Operations are applied on the backend, then synchronized to the frontend.
"""

import json
import logging

from livekit.agents import RunContext, function_tool

from helpers.board_sync import (
    apply_board_change,
    clear_board_document,
    dispatch_board_sync,
    replace_board_document,
)
from helpers.room_utils import get_frontend_identity

logger = logging.getLogger("agent-UnlockPi")


@function_tool()
async def write_to_board(
    context: RunContext,
    board_json: str,
) -> str:
    """Write structured content to the classroom board. Replaces the entire board.

    Call this when you need to display NEW content on the board (paragraphs, formulas, diagrams).
    The board uses a structured document model - NOT markdown.

    Args:
        board_json: A JSON string containing a BoardDocument object with this structure:
            {
              "id": "board-1",
              "version": 1,
              "blocks": [
                {
                  "id": "block-1",
                  "type": "paragraph",
                  "lines": [
                    { "id": "l1", "text": "First line of text." },
                    { "id": "l2", "text": "Second line.", "highlight": "definition" }
                  ]
                },
                {
                  "id": "block-2",
                  "type": "formula",
                  "formula": "E=mc^2"
                },
                {
                  "id": "block-3",
                  "type": "diagram",
                  "diagramType": "mermaid",
                  "content": "flowchart TD\\n  A[\"Start\"] --> B[\"End\"]"
                }
              ]
            }

            Block types:
            - "paragraph": Has "lines" array. Each line has "id", "text", and optional "highlight".
            - "formula": Has "formula" string (LaTeX/plain math notation).
            - "diagram": Has "diagramType" ("mermaid") and "content" (Mermaid syntax).
              * Use flowchart TD (not graph TD) for diagrams. Quote labels: A["Text here"].

            Highlight types for lines: "important", "definition", "warning", "exam", "focus", "note".

            IMPORTANT:
            - Every block must have a unique "id" (e.g. "block-1", "block-2").
            - Every line must have a unique "id" (e.g. "l1", "l2").
            - Use "write_to_board" for NEW content. Use "update_board_line" / "highlight_board_line" for edits to existing content.

    Returns:
        Confirmation with block count and board summary.
    """
    frontend_id = get_frontend_identity()
    if not frontend_id:
        return "Could not find the classroom display."

    try:
        document = json.loads(board_json) if isinstance(board_json, str) else board_json
        result = replace_board_document(context.userdata, document)
        await dispatch_board_sync(result, frontend_id=frontend_id)

        block_count = len(document.get("blocks", []))
        return f"Board updated with {block_count} blocks.\n{result.summary}"

    except Exception as error:
        logger.error(f"write_to_board failed: {error}")
        return f"Failed to update board: {str(error)}"


@function_tool()
async def update_board_line(
    context: RunContext,
    block_id: str,
    line_id: str,
    new_text: str,
) -> str:
    """Update a specific line of text on the board.

    Use this to edit an existing line without replacing the entire board.
    """
    frontend_id = get_frontend_identity()
    if not frontend_id:
        return "Could not find the classroom display."

    try:
        result = apply_board_change(
            context.userdata,
            {"type": "updateLine", "blockId": block_id, "lineId": line_id, "newText": new_text},
        )
        if not result.changed:
            return f"Line {line_id} in block {block_id} not found."

        await dispatch_board_sync(result, frontend_id=frontend_id)
        return f"Updated line {line_id} in block {block_id}."

    except Exception as error:
        logger.error(f"update_board_line failed: {error}")
        return f"Failed to update line: {str(error)}"


@function_tool()
async def add_board_block(
    context: RunContext,
    block_json: str,
    after_block_id: str = "",
) -> str:
    """Add a new block to the board."""
    frontend_id = get_frontend_identity()
    if not frontend_id:
        return "Could not find the classroom display."

    try:
        block = json.loads(block_json) if isinstance(block_json, str) else block_json
        operation: dict[str, object] = {"type": "addBlock", "block": block}
        if after_block_id:
            operation["afterBlockId"] = after_block_id

        result = apply_board_change(context.userdata, operation)
        await dispatch_board_sync(result, frontend_id=frontend_id)
        return f"Added block {block.get('id', '?')} ({block.get('type', '?')})."

    except Exception as error:
        logger.error(f"add_board_block failed: {error}")
        return f"Failed to add block: {str(error)}"


@function_tool()
async def highlight_board_line(
    context: RunContext,
    block_id: str,
    line_id: str,
    highlight_type: str,
) -> str:
    """Highlight a specific line on the board."""
    frontend_id = get_frontend_identity()
    if not frontend_id:
        return "Could not find the classroom display."

    try:
        result = apply_board_change(
            context.userdata,
            {
                "type": "highlightLine",
                "blockId": block_id,
                "lineId": line_id,
                "highlightType": highlight_type,
            },
        )
        if not result.changed:
            return f"Line {line_id} in block {block_id} not found."

        await dispatch_board_sync(result, frontend_id=frontend_id)
        return f"Highlighted line {line_id} as '{highlight_type}'."

    except Exception as error:
        logger.error(f"highlight_board_line failed: {error}")
        return f"Failed to highlight line: {str(error)}"


@function_tool()
async def insert_board_line(
    context: RunContext,
    block_id: str,
    after_line_id: str,
    line_json: str,
) -> str:
    """Insert a new line after a specific line in a paragraph block."""
    frontend_id = get_frontend_identity()
    if not frontend_id:
        return "Could not find the classroom display."

    try:
        new_line = json.loads(line_json) if isinstance(line_json, str) else line_json
        result = apply_board_change(
            context.userdata,
            {
                "type": "insertLineAfter",
                "blockId": block_id,
                "afterLineId": after_line_id,
                "newLine": new_line,
            },
        )
        if not result.changed:
            return f"Line {after_line_id} in block {block_id} not found."

        await dispatch_board_sync(result, frontend_id=frontend_id)
        return f"Inserted line {new_line.get('id', '?')} after {after_line_id}."

    except Exception as error:
        logger.error(f"insert_board_line failed: {error}")
        return f"Failed to insert line: {str(error)}"


@function_tool()
async def delete_board_line(
    context: RunContext,
    block_id: str,
    line_id: str,
) -> str:
    """Delete a specific line from a paragraph block."""
    frontend_id = get_frontend_identity()
    if not frontend_id:
        return "Could not find the classroom display."

    try:
        result = apply_board_change(
            context.userdata,
            {"type": "deleteLine", "blockId": block_id, "lineId": line_id},
        )
        if not result.changed:
            return f"Line {line_id} in block {block_id} not found."

        await dispatch_board_sync(result, frontend_id=frontend_id)
        return f"Deleted line {line_id} from block {block_id}."

    except Exception as error:
        logger.error(f"delete_board_line failed: {error}")
        return f"Failed to delete line: {str(error)}"


@function_tool()
async def clear_board_content(
    context: RunContext,
) -> str:
    """Clear all content from the structured board and reset it to empty."""
    frontend_id = get_frontend_identity()
    if not frontend_id:
        return "Could not find the classroom display."

    try:
        result = clear_board_document(context.userdata)
        await dispatch_board_sync(result, frontend_id=frontend_id)
        return "Cleared the board."

    except Exception as error:
        logger.error(f"clear_board_content failed: {error}")
        return f"Failed to clear board: {str(error)}"

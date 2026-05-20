"""
Board sync module.

Owns the backend board state transitions and the RPC dispatch needed to keep
the classroom display aligned with the board document.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from helpers.board_engine import apply_operation, board_to_summary, create_empty_board
from helpers.room_utils import send_rpc


@dataclass(frozen=True)
class BoardSyncResult:
    document: dict[str, Any]
    changed: bool
    rpc_method: str
    rpc_payload: dict[str, Any]

    @property
    def summary(self) -> str:
        return board_to_summary(self.document)


def replace_board_document(session_data, document: dict[str, Any]) -> BoardSyncResult:
    """Replace the entire board document and update session state."""
    normalized = dict(document)
    normalized.setdefault("id", "board-1")
    normalized.setdefault("version", 1)

    operation = {"type": "setBoard", "document": normalized}
    updated_document = apply_operation(session_data.board_document, operation)
    session_data.board_document = updated_document
    return BoardSyncResult(
        document=updated_document,
        changed=True,
        rpc_method="set_board",
        rpc_payload=updated_document,
    )


def apply_board_change(session_data, operation: dict[str, Any]) -> BoardSyncResult:
    """Apply a board operation and update session state only when it changes."""
    current_document = session_data.board_document
    updated_document = apply_operation(current_document, operation)
    changed = updated_document.get("version") != current_document.get("version")
    if changed:
        session_data.board_document = updated_document

    return BoardSyncResult(
        document=updated_document,
        changed=changed,
        rpc_method="board_operation",
        rpc_payload=operation,
    )


def clear_board_document(session_data) -> BoardSyncResult:
    """Reset the board document to an empty state."""
    empty_document = create_empty_board()
    session_data.board_document = empty_document
    return BoardSyncResult(
        document=empty_document,
        changed=True,
        rpc_method="clear_board",
        rpc_payload={},
    )


def reset_board_document(session_data) -> None:
    """Reset backend board state without emitting an RPC command."""
    session_data.board_document = create_empty_board()


async def dispatch_board_sync(result: BoardSyncResult, *, frontend_id: str) -> str:
    """Send a board sync command to the frontend and return its raw response."""
    return await send_rpc(result.rpc_method, result.rpc_payload, frontend_id=frontend_id)

import unittest
from unittest.mock import AsyncMock, patch

from agents.session_data import SessionData
from helpers.board_sync import (
    apply_board_change,
    clear_board_document,
    dispatch_board_sync,
    replace_board_document,
    reset_board_document,
)


class BoardSyncTests(unittest.IsolatedAsyncioTestCase):
    def test_replace_board_document_updates_session_and_summary(self) -> None:
        session_data = SessionData()

        result = replace_board_document(
            session_data,
            {
                "blocks": [
                    {
                        "id": "block-1",
                        "type": "paragraph",
                        "lines": [{"id": "line-1", "text": "Fractions are ratios."}],
                    }
                ]
            },
        )

        self.assertTrue(result.changed)
        self.assertEqual(result.rpc_method, "set_board")
        self.assertEqual(session_data.board_document["version"], 1)
        self.assertIn("Fractions are ratios.", result.summary)

    def test_apply_board_change_only_updates_when_operation_matches(self) -> None:
        session_data = SessionData()
        replace_board_document(
            session_data,
            {
                "blocks": [
                    {
                        "id": "block-1",
                        "type": "paragraph",
                        "lines": [{"id": "line-1", "text": "Old text"}],
                    }
                ]
            },
        )

        changed = apply_board_change(
            session_data,
            {
                "type": "updateLine",
                "blockId": "block-1",
                "lineId": "line-1",
                "newText": "New text",
            },
        )
        unchanged = apply_board_change(
            session_data,
            {
                "type": "updateLine",
                "blockId": "missing-block",
                "lineId": "line-1",
                "newText": "No-op",
            },
        )

        self.assertTrue(changed.changed)
        self.assertEqual(
            session_data.board_document["blocks"][0]["lines"][0]["text"],
            "New text",
        )
        self.assertFalse(unchanged.changed)

    def test_clear_and_reset_board_document_empty_the_session_state(self) -> None:
        session_data = SessionData()
        replace_board_document(
            session_data,
            {"blocks": [{"id": "block-1", "type": "formula", "formula": "a^2+b^2=c^2"}]},
        )

        cleared = clear_board_document(session_data)
        self.assertEqual(cleared.rpc_method, "clear_board")
        self.assertEqual(session_data.board_document["blocks"], [])

        replace_board_document(
            session_data,
            {"blocks": [{"id": "block-2", "type": "formula", "formula": "x+y=z"}]},
        )
        reset_board_document(session_data)
        self.assertEqual(session_data.board_document["blocks"], [])

    async def test_dispatch_board_sync_forwards_method_and_payload(self) -> None:
        result = clear_board_document(SessionData())

        with patch("helpers.board_sync.send_rpc", new=AsyncMock(return_value="ok")) as mock_send_rpc:
            response = await dispatch_board_sync(result, frontend_id="teacher-interface")

        self.assertEqual(response, "ok")
        mock_send_rpc.assert_awaited_once_with(
            "clear_board",
            {},
            frontend_id="teacher-interface",
        )


if __name__ == "__main__":
    unittest.main()

import unittest

from agents.lesson_state import (
    DEFAULT_PHASE_ORDER,
    advance_lesson_phase,
    build_runtime_instructions,
    get_lesson_progress,
    initialize_lesson_state,
    mark_goal_covered,
    parse_goals,
    parse_phase_order,
)
from agents.session_data import SessionData


class LessonStateTests(unittest.TestCase):
    def test_parse_goals_splits_and_dedupes_long_goal_lists(self) -> None:
        raw_goals = """
        1. Understand fractions, compare equivalent fractions, explain numerator and denominator
        - Solve word problems
        - solve word problems
        """

        self.assertEqual(
            parse_goals(raw_goals),
            [
                "Understand fractions",
                "compare equivalent fractions",
                "explain numerator and denominator",
                "Solve word problems",
            ],
        )

    def test_parse_phase_order_detects_custom_sequence(self) -> None:
        raw_structure = "We start with an introduction, then practice together, and end with a recap."

        self.assertEqual(
            parse_phase_order(raw_structure),
            ["warmup", "practice", "exit", "concept"],
        )

    def test_initialize_lesson_state_populates_checklist_and_phase_order(self) -> None:
        session_data = SessionData(
            session_goals="- Fractions\n- Decimals",
            session_structure="intro -> concept -> practice -> closing",
        )

        initialize_lesson_state(session_data)

        self.assertEqual(session_data.lesson_goal_checklist, ["Fractions", "Decimals"])
        self.assertEqual(session_data.covered_goals, [])
        self.assertEqual(session_data.lesson_phase_order, DEFAULT_PHASE_ORDER)
        self.assertEqual(session_data.current_phase_index, 0)

    def test_build_runtime_instructions_uses_parsed_goal_checklist(self) -> None:
        session_data = SessionData(
            session_title="Fractions 101",
            session_topic="Fractions",
            session_goals="- Fractions\n- Decimals",
            session_structure="intro -> concept -> practice -> closing",
        )
        initialize_lesson_state(session_data)
        mark_goal_covered(session_data, "Fractions")

        instructions = build_runtime_instructions("Base instructions", session_data)

        self.assertIn("Covered goals: ['Fractions']", instructions)
        self.assertIn("Remaining goals: ['Decimals']", instructions)

    def test_get_lesson_progress_reports_current_phase_and_remaining_goals(self) -> None:
        session_data = SessionData(session_goals="- Fractions\n- Decimals")
        initialize_lesson_state(session_data)
        mark_goal_covered(session_data, "Fractions")

        progress = get_lesson_progress(session_data)

        self.assertEqual(progress["current_phase"], "warmup")
        self.assertEqual(progress["covered_goals"], ["Fractions"])
        self.assertEqual(progress["remaining_goals"], ["Decimals"])

    def test_mark_goal_covered_reports_duplicate_goal(self) -> None:
        session_data = SessionData(session_goals="- Fractions")
        initialize_lesson_state(session_data)

        self.assertEqual(mark_goal_covered(session_data, "Fractions"), "covered")
        self.assertEqual(mark_goal_covered(session_data, "fractions"), "already-covered")
        self.assertEqual(session_data.covered_goals, ["Fractions"])

    def test_advance_lesson_phase_only_moves_one_step(self) -> None:
        session_data = SessionData(session_structure="warmup -> concept -> practice -> exit")
        initialize_lesson_state(session_data)

        phase = advance_lesson_phase(session_data, "exit")

        self.assertEqual(phase, "concept")
        self.assertEqual(session_data.current_phase_index, 1)


if __name__ == "__main__":
    unittest.main()

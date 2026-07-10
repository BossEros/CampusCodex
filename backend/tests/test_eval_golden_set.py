from pathlib import Path
import json
import tempfile
import unittest


class GoldenSetTests(unittest.TestCase):
    def _write_golden_set(self, records) -> Path:
        temp_dir = tempfile.mkdtemp()
        golden_set_path = Path(temp_dir) / "golden_qa.json"
        golden_set_path.write_text(json.dumps(records), encoding="utf-8")
        return golden_set_path

    def test_load_golden_set_returns_parsed_records(self):
        from app.eval.golden_set import load_golden_set

        golden_set_path = self._write_golden_set(
            [
                {
                    "id": "gq-001",
                    "category": "admissions",
                    "question": "What documents does a transfer student need?",
                    "reference_answer": "A transfer student must submit a clearance and transcript.",
                },
                {
                    "id": "gq-002",
                    "question": "What is the passing grade?",
                    "reference_answer": "3.0 is the passing grade.",
                },
            ]
        )

        golden_questions = load_golden_set(golden_set_path)

        self.assertEqual(2, len(golden_questions))
        self.assertEqual("gq-001", golden_questions[0].id)
        self.assertEqual("admissions", golden_questions[0].category)
        self.assertIsNone(golden_questions[1].category)

    def test_load_golden_set_raises_for_missing_file(self):
        from app.eval.golden_set import load_golden_set

        with self.assertRaises(FileNotFoundError):
            load_golden_set("does/not/exist.json")

    def test_load_golden_set_raises_for_empty_array(self):
        from app.eval.golden_set import load_golden_set

        golden_set_path = self._write_golden_set([])

        with self.assertRaises(ValueError):
            load_golden_set(golden_set_path)

    def test_load_golden_set_raises_for_missing_required_field(self):
        from app.eval.golden_set import load_golden_set

        golden_set_path = self._write_golden_set(
            [{"id": "gq-001", "question": "What is the passing grade?"}]
        )

        with self.assertRaises(ValueError):
            load_golden_set(golden_set_path)

    def test_load_golden_set_raises_for_blank_required_field(self):
        from app.eval.golden_set import load_golden_set

        golden_set_path = self._write_golden_set(
            [{"id": "gq-001", "question": "   ", "reference_answer": "An answer."}]
        )

        with self.assertRaises(ValueError):
            load_golden_set(golden_set_path)

    def test_load_golden_set_raises_for_duplicate_ids(self):
        from app.eval.golden_set import load_golden_set

        golden_set_path = self._write_golden_set(
            [
                {"id": "gq-001", "question": "Q1", "reference_answer": "A1"},
                {"id": "gq-001", "question": "Q2", "reference_answer": "A2"},
            ]
        )

        with self.assertRaises(ValueError):
            load_golden_set(golden_set_path)


if __name__ == "__main__":
    unittest.main()

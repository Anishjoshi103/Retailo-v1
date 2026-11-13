import unittest

from scripts.summarize_test_failures import SEPARATOR, parse_failures, summarize

LOG = f"""Found 3 test(s).
{SEPARATOR}
ERROR: test_a (apps.x.tests.A.test_a)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "x.py", line 1, in test_a
django.db.utils.ProgrammingError: ('42000', 'Incorrect syntax near ROUND')
{SEPARATOR}
FAIL: test_b (apps.x.tests.A.test_b)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "x.py", line 9, in test_b
AssertionError: 1 != 2

----------------------------------------------------------------------
Ran 3 tests in 0.1s

FAILED (failures=1, errors=1)
"""


class SummarizeTestFailuresTests(unittest.TestCase):
    def test_extracts_each_failing_test_with_its_final_message(self):
        failures = parse_failures(LOG)
        self.assertEqual(len(failures), 2)
        self.assertEqual(failures[0][0], "ERROR: test_a (apps.x.tests.A.test_a)")
        self.assertIn("Incorrect syntax near ROUND", failures[0][1])
        self.assertEqual(failures[1][1], "AssertionError: 1 != 2")

    def test_emits_escaped_annotations_for_failures_and_the_log_tail(self):
        annotations = summarize(LOG)
        self.assertEqual(len(annotations), 2)
        self.assertTrue(annotations[0].startswith("::error title=Test failures::2 failing test(s):%0A- ERROR"))
        self.assertTrue(annotations[1].startswith("::error title=End of test log::"))
        for annotation in annotations:
            self.assertNotIn("\n", annotation)

    def test_a_log_without_failure_blocks_still_gives_the_tail(self):
        annotations = summarize("Creating test database...\nmigrate failed: boom\n")
        self.assertEqual(len(annotations), 1)
        self.assertIn("migrate failed: boom", annotations[0])

    def test_an_empty_log_produces_nothing(self):
        self.assertEqual(summarize(""), [])

    def test_caps_the_number_of_listed_failures(self):
        blocks = "".join(f"{SEPARATOR}\nERROR: t{i} (m.t{i})\n------\nTraceback\nE{i}: x\n" for i in range(60))
        text = summarize(blocks)[0]
        self.assertIn("60 failing test(s):", text)
        self.assertIn("and 20 more", text)


if __name__ == "__main__":
    unittest.main()

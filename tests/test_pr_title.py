import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import pr_title  # noqa: E402

RULES = pr_title.load_rules()


class PrTitleTest(unittest.TestCase):
    def ok(self, title):
        self.assertIsNone(pr_title.check(title, *RULES), title)

    def bad(self, title):
        self.assertIsNotNone(pr_title.check(title, *RULES), title)

    def test_rules_read_from_workflow(self):
        types, scopes, _ = RULES
        self.assertIn("chore", types)
        self.assertIn("formula", scopes)

    def test_bump_title_passes(self):
        # The exact form bump.yml writes.
        self.ok("chore(formula): bump kubectl-shadewright to 0.3.1")

    def test_valid_titles(self):
        self.ok("fix: start the formula description with a capital letter")
        self.ok("ci!: drop the old trigger")
        self.ok("docs(docs,ci): explain the manual check")

    def test_invalid_titles(self):
        self.bad("bump kubectl-shadewright")
        self.bad("Chore(formula): bump x to 1.0.0")
        self.bad("chores(formula): bump x to 1.0.0")
        self.bad("chore(release): bump x to 1.0.0")
        self.bad("chore(formula): Bump x to 1.0.0")
        self.bad("chore(formula): bump x to 1.0.0.")
        self.bad("chore(formula):bump x")

    def test_missing_rules_fail(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as fh:
            fh.write("on: push\n")
        try:
            with self.assertRaises(pr_title.RulesError):
                pr_title.load_rules(fh.name)
        finally:
            os.unlink(fh.name)


if __name__ == "__main__":
    unittest.main()

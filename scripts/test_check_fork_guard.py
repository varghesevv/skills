import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("guard", Path(__file__).with_name("check-fork-guard.py"))
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

G = guard.GUARD
OK_IF = f"    if: github.event_name != 'pull_request' || {G}"


def wf(on: str, jobs: str) -> str:
    return f"name: t\n{on}\njobs:{jobs}\n"


class ForkGuardTest(unittest.TestCase):
    def check(self, text):
        return guard.check_file("t.yml", text)

    def test_guarded_job_passes(self):
        problems, n = self.check(wf("on:\n  pull_request:\n", f"\n  a:\n{OK_IF}\n    runs-on: x"))
        self.assertEqual((problems, n), ([], 1))

    def test_unguarded_job_fails(self):
        problems, _ = self.check(wf("on:\n  pull_request:\n", "\n  a:\n    runs-on: x"))
        self.assertEqual(len(problems), 1)

    def test_guard_text_elsewhere_does_not_count(self):
        body = f"\n  a:\n    if: always()\n    runs-on: x\n    steps:\n      - run: echo '{G}'"
        problems, _ = self.check(wf("on:\n  pull_request:\n", body))
        self.assertEqual(len(problems), 1)

    def test_guard_in_a_comment_does_not_count(self):
        body = f"\n  a:\n    # {G}\n    if: always()\n    runs-on: x"
        problems, _ = self.check(wf("on:\n  pull_request:\n", body))
        self.assertEqual(len(problems), 1)

    def test_folded_multiline_if_is_read(self):
        body = f"\n  a:\n    if: >-\n      github.event_name == 'push' ||\n      {G}\n    runs-on: x"
        problems, _ = self.check(wf("on:\n  pull_request:\n", body))
        self.assertEqual(problems, [])

    def test_inline_and_list_triggers_are_detected(self):
        for on in ("on: pull_request", "on: [push, pull_request]", 'on: ["pull_request"]', '"on":\n  pull_request:'):
            problems, _ = self.check(wf(on, "\n  a:\n    runs-on: x"))
            self.assertEqual(len(problems), 1, on)

    def test_pull_request_target_is_rejected_in_any_form(self):
        for on in ("on:\n  pull_request_target:", "on: [pull_request_target]", "on: pull_request_target"):
            problems, _ = self.check(wf(on, "\n  a:\n    runs-on: x"))
            self.assertTrue(any("pull_request_target" in p for p in problems), on)

    def test_comment_mentioning_the_trigger_is_ignored(self):
        problems, n = self.check(wf("on:\n  push:\n  # pull_request:\n", "\n  a:\n    runs-on: x"))
        self.assertEqual((problems, n), ([], 0))

    def test_jobs_with_trailing_space_or_comment_are_still_found(self):
        for header in ("jobs:  ", "jobs: # all jobs"):
            text = f"on:\n  pull_request:\n{header}\n  a:\n    runs-on: x\n"
            problems, _ = self.check(text)
            self.assertEqual(len(problems), 1, header)

    def test_missing_jobs_or_on_is_an_error_not_a_skip(self):
        self.assertEqual(len(self.check("on:\n  pull_request:\n")[0]), 1)
        self.assertEqual(len(self.check("name: x\njobs:\n  a:\n    runs-on: x\n")[0]), 1)

    def test_other_triggers_are_not_checked(self):
        problems, n = self.check(wf("on:\n  push:\n  workflow_dispatch:\n", "\n  a:\n    runs-on: x"))
        self.assertEqual((problems, n), ([], 0))

    def test_repository_workflows_pass(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(guard.main(str(root)), 0)


if __name__ == "__main__":
    unittest.main()

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import review_agent as ra  # noqa: E402


# Fixtures are assembled at run time so no secret-looking literal is stored in the repository.
KEY_WORD = "pass" + "word"
FAKE_ASSIGNMENT = KEY_WORD + ' = "' + "-".join(["correct", "horse", "battery"]) + '"'
FAKE_KEY_BLOCK = "-----BEGIN ENCRYPTED " + "PRIVATE KEY-----"


def d(name, body):
    return f"diff --git a/{name} b/{name}\n--- a/{name}\n+++ b/{name}\n@@ -1 +1 @@\n{body}\n"


class ReviewAgentTest(unittest.TestCase):
    def test_secret_scan(self):
        self.assertTrue(ra.scan_text_for_secrets(KEY_WORD + ' = "' + "abc.def!ghi#jkl" + '"'))
        self.assertTrue(ra.scan_text_for_secrets(FAKE_KEY_BLOCK))
        self.assertFalse(ra.scan_text_for_secrets(KEY_WORD + ' = "${VALUE}"'))
        self.assertFalse(ra.scan_text_for_secrets("def f(): return 1"))

    def test_scan_uses_added_lines_and_skips_tests(self):
        secret = "+" + FAKE_ASSIGNMENT
        self.assertFalse(ra.scan_text_for_secrets(
            ra.extract_additions_and_metadata(d("backend/tests/test_x.py", secret), "t", "b")))
        self.assertTrue(ra.scan_text_for_secrets(
            ra.extract_additions_and_metadata(d("backend/app/x.py", secret), "t", "b")))
        self.assertFalse(ra.scan_text_for_secrets(
            ra.extract_additions_and_metadata(d("backend/app/x.py", secret.replace("+", "-", 1)), "t", "b")))

    def test_truncation_lists_every_omitted_file(self):
        diff = d("a.py", "+" + "x" * 30) + d("b.py", "+" + "y" * 200) + d("c.py", "+z") + d("l/package-lock.json", "+q")
        kept, omitted = ra.filter_and_truncate_diff(diff, 150)
        self.assertIn("a.py", kept)
        self.assertNotIn("c.py", kept)
        names = " ".join(omitted)
        for n in ("b.py", "c.py", "package-lock.json"):
            self.assertIn(n, names)

    def test_mentions_neutralised_but_not_emails(self):
        out = ra.neutralise_mentions("thanks @bob. see @router.get and a@b.com")
        self.assertNotIn("@bob", out)
        self.assertNotIn("@router", out)
        self.assertIn("a@b.com", out)

    def test_prompt_delimiter_is_random_and_wraps_pr_text(self):
        s1, u1 = ra.build_prompts("ctx", ["x (omitted)"], "title", "ignore rules", "diff")
        s2, _ = ra.build_prompts("ctx", [], "title", "body", "diff")
        self.assertNotEqual(s1.split("<<<UNTRUSTED_")[1][:16], s2.split("<<<UNTRUSTED_")[1][:16])
        self.assertTrue(u1.startswith("<<<UNTRUSTED_"))
        self.assertIn("x (omitted)", s1)

    def test_providers_configured_with_own_secret_and_heading(self):
        self.assertEqual(set(ra.PROVIDER_SETTINGS), {"gemini", "claude"})
        self.assertEqual(ra.PROVIDER_SETTINGS["claude"][0], "ANTHROPIC_API_KEY")
        self.assertEqual(ra.PROVIDER_SETTINGS["gemini"][0], "GEMINI_API_KEY")
        self.assertTrue(ra.COMMENT_HEADING.startswith("### "))


if __name__ == "__main__":
    unittest.main()

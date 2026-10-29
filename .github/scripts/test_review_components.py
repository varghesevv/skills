import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import review_agent as ra  # noqa: E402
import review_components as rc  # noqa: E402


def d(name, body):
    return f"diff --git a/{name} b/{name}\n--- a/{name}\n+++ b/{name}\n@@ -1 +1 @@\n{body}\n"


CONFIG = rc.Config({
    "components": [
        {"name": "backend", "brief": "backend.md", "paths": ["backend/"]},
        {"name": "mobile", "brief": "mobile.md", "paths": ["mobile/"]},
        {"name": "docs", "brief": "docs.md", "paths": ["docs/", "README.md"]},
        {"name": "ci", "brief": "ci.md", "paths": [".github/"]},
        {"name": "ci-scripts", "paths": [".github/scripts/"]},
    ],
    "clients": ["frontend", "mobile"],
    "contract_paths": ["backend/app/api/", "mobile/lib/core/api/"],
})


class ComponentTest(unittest.TestCase):
    def test_longest_prefix_wins_and_unknown_is_other(self):
        self.assertEqual(CONFIG.component_of("backend/app/x.py"), "backend")
        self.assertEqual(CONFIG.component_of(".github/scripts/a.py"), "ci-scripts")
        self.assertEqual(CONFIG.component_of(".github/workflows/a.yml"), "ci")
        self.assertEqual(CONFIG.component_of("LICENSE"), "other")
        self.assertEqual(rc.Config({}).component_of("anything"), "other")

    def test_repository_map_covers_the_known_components(self):
        path = os.path.join(os.path.dirname(__file__), "..", "review", "components.json")
        config = rc.load_config(path)
        for name, expected in {
            "backend/app/main.py": "backend",
            "frontend/src/App.tsx": "frontend",
            "mobile/lib/main.dart": "mobile",
            "infra/docker/compose.demo.yml": "infra",
            ".github/workflows/ci-backend.yml": "ci",
            "docs/android/plan.md": "docs",
        }.items():
            self.assertEqual(config.component_of(name), expected, name)
        for comp in config.components:  # every brief named in the map exists and fits
            text = rc.load_brief(os.path.join(os.path.dirname(__file__), "..", "review"),
                                 comp["brief"], rc.MAX_COMPONENT_BRIEF_CHARS)
            self.assertTrue(text, comp["brief"])

    def test_sensitive_files_are_found_by_name(self):
        for name in ("mobile/android/key.properties", "mobile/android/app/google-services.json",
                     "x/release.jks", "a/b/upload.keystore", ".env", "infra/.env.demo", "id_qnap",
                     "ios/Runner/GoogleService-Info.plist", "certs/server.pem"):
            self.assertTrue(rc.is_sensitive_file(name), name)
        for name in (".env.example", "infra/docker/demo.env.example", "id_qnap.pub",
                     "mobile/android/key.properties.example", "backend/app/main.py", "docs/environment.md"):
            self.assertFalse(rc.is_sensitive_file(name), name)

    def test_generated_files_are_excluded(self):
        for name in ("mobile/pubspec.lock", "mobile/lib/a.g.dart", "mobile/lib/a.freezed.dart",
                     "mobile/build/app/outputs/x.dart", "mobile/android/gradle/wrapper/gradle-wrapper.jar",
                     "mobile/android/gradlew", "docs/openapi.json", "mobile/lib/l10n/app_localizations_en.dart",
                     "frontend/package-lock.json", "logo.png"):
            self.assertTrue(rc.is_excluded(name), name)
        self.assertFalse(rc.is_excluded("mobile/lib/main.dart"))
        self.assertFalse(rc.is_excluded("backend/app/main.py"))

    def test_dart_and_android_tests_are_recognised(self):
        for name in ("mobile/test/a_test.dart", "mobile/integration_test/flow_test.dart",
                     "mobile/lib/feature/thing_test.dart", "mobile/android/app/src/androidTest/A.kt",
                     "backend/tests/test_x.py", "frontend/src/a.test.tsx"):
            self.assertTrue(rc.is_test(name), name)
        self.assertFalse(rc.is_test("mobile/lib/main.dart"))

    def test_rank_orders_source_before_config_tests_and_docs(self):
        names = ["docs/a.md", "backend/tests/test_a.py", "infra/x.yml", "backend/app/a.py"]
        self.assertEqual(sorted(names, key=rc.rank),
                         ["backend/app/a.py", "infra/x.yml", "backend/tests/test_a.py", "docs/a.md"])

    def test_groups_fit_in_one_call_or_split_by_component(self):
        self.assertEqual(rc.plan_groups({"backend": 10, "docs": 5}, 100), [["backend", "docs"]])
        self.assertEqual(rc.plan_groups({"backend": 90, "docs": 50}, 100), [["backend"], ["docs"]])
        self.assertEqual(rc.plan_groups({}, 100), [])

    def test_more_components_than_calls_merge_the_smallest(self):
        sizes = {"a": 90, "b": 80, "c": 70, "d": 60, "e": 5, "f": 4}
        groups = rc.plan_groups(sizes, 100, max_calls=4)
        self.assertEqual(len(groups), 4)
        self.assertEqual(sorted(n for g in groups for n in g), list("abcdef"))
        self.assertTrue(any({"e", "f"} <= set(g) for g in groups))

    def test_contract_pass_needs_backend_and_a_client(self):
        self.assertTrue(rc.needs_contract_pass(CONFIG, {"backend", "mobile"}))
        self.assertFalse(rc.needs_contract_pass(CONFIG, {"backend", "docs"}))
        self.assertFalse(rc.needs_contract_pass(CONFIG, {"mobile"}))
        self.assertTrue(CONFIG.is_contract_file("backend/app/api/v1/chat.py"))
        self.assertFalse(CONFIG.is_contract_file("backend/app/models/x.py"))

    def test_merge_takes_the_highest_risk_and_all_findings(self):
        a = {"overview": "- one", "risk": "Low", "summary": "ok", "findings": [{"title": "x"}]}
        b = {"overview": "- two", "risk": "High", "summary": "bad", "findings": [{"title": "y"}]}
        merged = rc.merge_results([a, b])
        self.assertEqual(merged["risk"], "High")
        self.assertEqual(merged["overview"], "- one\n- two")
        self.assertEqual(len(merged["findings"]), 2)
        self.assertIs(rc.merge_results([a]), a)

    def test_brief_assembly_and_size_limit(self):
        text = rc.assemble_brief("common", {"mobile": "m rules", "docs": ""}, ["mobile", "docs"])
        self.assertIn("common", text)
        self.assertIn("## Rules for mobile files\nm rules", text)
        self.assertNotIn("Rules for docs", text)
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "big.md"), "w") as f:
                f.write("x" * 50)
            with self.assertRaises(ValueError):
                rc.load_brief(tmp, "big.md", 10)
            self.assertEqual(rc.load_brief(tmp, "missing.md", 10), "")
            self.assertEqual(rc.load_brief(tmp, "../etc/passwd", 10), "")


class AgentIntegrationTest(unittest.TestCase):
    def test_file_names_survive_directories_that_end_in_b(self):
        for name in ("mobile/lib/core/api/chat_api.dart", "frontend/web/index.html", "a/sub/b/c.py", "docs/a.md"):
            self.assertEqual(ra.diff_filename(d(name, "+x")), name)
        self.assertEqual(ra.diff_filename("not a diff header"), "unknown")

    def test_small_budget_keeps_source_and_drops_docs_first(self):
        chunks = [d("docs/a.md", "+" + "d" * 200), d("backend/app/a.py", "+" + "s" * 50)]
        kept, omitted = ra.pack_chunks(chunks, 200)
        self.assertIn("backend/app/a.py", kept)
        self.assertNotIn("docs/a.md", kept)
        self.assertTrue(any("docs/a.md" in o for o in omitted))

    def test_android_signing_setting_without_quotes_is_a_secret(self):
        line = "store" + "Password" + "=" + "abcdef123456"
        self.assertTrue(ra.scan_text_for_secrets(line))
        self.assertFalse(ra.scan_text_for_secrets("store" + "Password" + "=" + "${STORE_PASSWORD}"))

    def test_dart_test_files_are_not_scanned_for_fixture_secrets(self):
        fake = '+const password = "' + "-".join(["correct", "horse", "battery"]) + '";'
        diff = d("mobile/test/login_test.dart", fake) + d("mobile/integration_test/a_test.dart", fake)
        self.assertFalse(ra.scan_text_for_secrets(ra.extract_additions_and_metadata(diff, "t", "b")))
        generated = d("mobile/lib/api.g.dart", fake)
        self.assertFalse(ra.scan_text_for_secrets(ra.extract_additions_and_metadata(generated, "t", "b")))

    def test_dedupe_keeps_one_of_the_same_point(self):
        findings = [
            {"path": "a.py", "title": "Missing check!"},
            {"path": "a.py", "title": "missing check"},
            {"path": "b.py", "title": "Missing check"},
            "not a dict",
        ]
        self.assertEqual(len(ra.dedupe_findings(findings)), 2)
        self.assertEqual(ra.dedupe_findings(None), [])

    def test_prompt_carries_scope_focus_and_file_heads_inside_the_untrusted_block(self):
        system, user = ra.build_prompts(
            "brief", [], "t", "b", "diff", [], scope="mobile", focus="check the dialler", heads="--- a.py\nimport x"
        )
        self.assertIn("covers only: mobile", system)
        self.assertIn("check the dialler", system)
        self.assertIn("--- a.py\nimport x", user)
        start = user.index("<<<UNTRUSTED_")
        self.assertLess(start, user.index("--- a.py"))
        plain, _ = ra.build_prompts("brief", [], "t", "b", "diff", [])
        self.assertNotIn("covers only", plain)


if __name__ == "__main__":
    unittest.main()

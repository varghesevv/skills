"""Component-aware helpers for the pull request reviewer (see docs/adr/0013).

Pure functions only (no network), so they can be tested without the model APIs.
The configuration and the briefs are read from the default branch checkout, never from the PR.
"""

import json
import os
import re

MAX_COMMON_BRIEF_CHARS = 6000
MAX_COMPONENT_BRIEF_CHARS = 3000
MAX_CALLS = 4  # model calls for the components; the cross-component contract call is extra

# Files that must never be in git. The reviewer reports them by name and stops, without sending
# the diff to a model. Examples (sample) files are fine.
SENSITIVE_FILE = re.compile(
    r"(\.(jks|keystore|p12|pfx|pem|key)$)"
    r"|((^|/)key\.properties$)"
    r"|((^|/)google-services\.json$)"
    r"|((^|/)GoogleService-Info\.plist$)"
    r"|((^|/)\.env(\.[^/]*)?$)"
    r"|((^|/)id_[A-Za-z0-9_]+$)"
)
SENSITIVE_ALLOWED = re.compile(r"\.(example|sample|template)$|\.pub$")

# Generated or bulky files that add nothing to a review.
EXCLUDED_SUFFIXES = (
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".ttf", ".otf", ".woff", ".woff2",
    ".min.js", ".min.css", ".map",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "pubspec.lock", "Podfile.lock",
    ".g.dart", ".freezed.dart", ".gr.dart", ".mocks.dart",
    "gradlew", "gradlew.bat", ".jar", ".class", ".apk", ".aab",
)
EXCLUDED_PATH = re.compile(
    r"(^|/)(build|\.dart_tool|\.gradle|Pods|node_modules|dist|coverage)/"
    r"|(^|/)GeneratedPluginRegistrant\.[a-z]+$"
    r"|(^|/)generated_plugin"
    r"|(^|/)(\.flutter-plugins(-dependencies)?|\.packages)$"
    r"|(^|/)l10n/app_localizations[a-z_]*\.dart$"
    r"|(^|/)openapi\.json$"
)

# Test and fixture files: fixture-style credentials are expected here (ci-secrets still covers them).
TEST_PATH = re.compile(
    r"(^|/)(tests?|__tests__|fixtures|integration_test|androidTest|goldens)/"
    r"|(^|/)test_[^/]*$|_test\.(py|dart|kt)$|\.(test|spec)\.[jt]sx?$"
)
DOC_PATH = re.compile(r"\.(md|rst|txt)$")
CONFIG_PATH = re.compile(
    r"\.(ya?ml|json|toml|tf|ini|cfg|properties|gradle|kts|xml|plist|env)$|Dockerfile|Caddyfile|Makefile"
)

# Source files whose first lines (imports) help the reviewer avoid "undefined name" mistakes.
HEAD_CONTEXT_SUFFIXES = (".py", ".ts", ".tsx", ".dart", ".kt", ".java")


def is_sensitive_file(name: str) -> bool:
    return bool(SENSITIVE_FILE.search(name)) and not SENSITIVE_ALLOWED.search(name)


def is_excluded(name: str) -> bool:
    return name.endswith(EXCLUDED_SUFFIXES) or bool(EXCLUDED_PATH.search(name))


def is_test(name: str) -> bool:
    return bool(TEST_PATH.search(name))


def rank(name: str) -> int:
    """Review priority: 0 source, 1 configuration, 2 tests, 3 documentation (lower is first)."""
    if DOC_PATH.search(name):
        return 3
    if is_test(name):
        return 2
    if CONFIG_PATH.search(name):
        return 1
    return 0


class Config:
    def __init__(self, data: dict):
        self.components: list[dict] = list(data.get("components", []))
        self.clients: set[str] = set(data.get("clients", []))
        self.contract_paths: tuple[str, ...] = tuple(data.get("contract_paths", []))

    def component_of(self, name: str) -> str:
        best, best_len = "other", -1
        for comp in self.components:
            for prefix in comp.get("paths", []):
                if name.startswith(prefix) and len(prefix) > best_len:
                    best, best_len = comp["name"], len(prefix)
        return best

    def brief_file(self, component: str) -> str | None:
        for comp in self.components:
            if comp["name"] == component:
                return comp.get("brief")
        return None

    def is_contract_file(self, name: str) -> bool:
        return name.startswith(self.contract_paths) if self.contract_paths else False


def load_config(path: str) -> Config:
    try:
        with open(path, encoding="utf-8") as f:
            return Config(json.load(f))
    except (OSError, ValueError):
        # Without the map every file is "other": one call with the common brief, as before.
        return Config({})


def load_brief(directory: str, filename: str | None, limit: int) -> str:
    """A brief file from the review folder; '' when it is missing. Raises ValueError if too long."""
    if not filename or os.path.basename(filename) != filename:
        return ""
    try:
        with open(os.path.join(directory, filename), encoding="utf-8") as f:
            text = f.read().strip()
    except OSError:
        return ""
    if len(text) > limit:
        raise ValueError(f"{filename} is over {limit} characters; shorten it.")
    return text


def assemble_brief(common: str, briefs: dict[str, str], components: list[str]) -> str:
    parts = [common.strip()]
    for name in components:
        text = briefs.get(name, "").strip()
        if text:
            parts.append(f"## Rules for {name} files\n{text}")
    return "\n\n".join(parts)


def plan_groups(sizes: dict[str, int], budget: int, max_calls: int = MAX_CALLS) -> list[list[str]]:
    """Which components share a model call. `sizes` is the diff size per component.

    Everything fits in one call: one group. Otherwise one group per component, and when there are
    more than `max_calls`, the smallest groups are merged until the count fits.
    """
    names = sorted(sizes, key=lambda n: (-sizes[n], n))
    if not names:
        return []
    if sum(sizes.values()) <= budget:
        return [sorted(names)]
    groups = [[n] for n in names]
    while len(groups) > max_calls:
        groups.sort(key=lambda g: (-sum(sizes[n] for n in g), g))
        last = groups.pop()
        groups[-1] = groups[-1] + last
    return [sorted(g) for g in groups]


def needs_contract_pass(config: Config, present: set[str]) -> bool:
    """The API and at least one client changed together: check they still agree."""
    return "backend" in present and bool(present & config.clients)


MERGE_RISK = {"Low": 0, "Medium": 1, "High": 2}


def merge_results(results: list[dict]) -> dict:
    """Combine the answers of several model calls into one review."""
    if len(results) == 1:
        return results[0]
    overview = "\n".join(
        line for r in results for line in str(r.get("overview") or "").splitlines() if line.strip()
    )
    risks = [r.get("risk") for r in results if r.get("risk") in MERGE_RISK]
    risk = max(risks, key=lambda x: MERGE_RISK[x]) if risks else "Unknown"
    summary = " ".join(str(r.get("summary") or "").strip() for r in results).strip()
    findings: list = []
    for r in results:
        if isinstance(r.get("findings"), list):
            findings.extend(r["findings"])
    return {"overview": overview, "risk": risk, "summary": summary, "findings": findings}

import importlib.util
import json
import subprocess
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPT = Path(__file__).with_name("add-download.py")
spec = importlib.util.spec_from_file_location("add_download", SCRIPT)
assert spec and spec.loader
add_download = importlib.util.module_from_spec(spec)
spec.loader.exec_module(add_download)


class AddDownloadTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.folder = self.root / "downloads"
        self.apk = self.root / "build.apk"
        self.apk.write_bytes(b"not a real apk, just bytes")

    def add(self, version: str, build: int = 1, **kwargs):
        return add_download.add_download(self.folder, self.apk, version=version, build=build, **kwargs)

    def index(self) -> dict:
        return json.loads((self.folder / "index.json").read_text("utf-8"))

    def test_writes_file_and_index(self) -> None:
        entry = self.add("1.2.0", 7, notes="First build")
        stored = self.folder / "android" / "1.2.0" / "skills-demo-1.2.0.apk"
        self.assertEqual(stored.read_bytes(), self.apk.read_bytes())
        self.assertEqual(entry["size_bytes"], stored.stat().st_size)
        self.assertEqual(len(entry["sha256"]), 64)
        self.assertEqual(self.index()["android"][0]["notes"], "First build")
        self.assertEqual(stored.stat().st_mode & 0o777, 0o644)

    def test_same_version_is_replaced_not_duplicated(self) -> None:
        self.add("1.0.0", 1)
        self.add("1.0.0", 2)
        entries = self.index()["android"]
        self.assertEqual([(e["version"], e["build"]) for e in entries], [("1.0.0", 2)])

    def test_newest_first_by_number_not_text(self) -> None:
        for version in ("1.9.0", "1.10.0", "1.2.0"):
            self.add(version)
        self.assertEqual([e["version"] for e in self.index()["android"]], ["1.10.0", "1.9.0", "1.2.0"])

    def test_old_versions_beyond_keep_are_removed(self) -> None:
        for minor in range(5):
            self.add(f"1.{minor}.0", keep=3)
        self.assertEqual([e["version"] for e in self.index()["android"]], ["1.4.0", "1.3.0", "1.2.0"])
        self.assertFalse((self.folder / "android" / "1.0.0").exists())
        self.assertTrue((self.folder / "android" / "1.4.0").exists())

    def test_rejects_unsafe_input(self) -> None:
        for bad in ("1.2", "1.2.x", "../1.2.3", "1.2.3/../../x", ""):
            with self.assertRaises(ValueError, msg=bad):
                self.add(bad)
        for bad_name in ("../x.apk", "a/b.apk", "x.exe", ".apk", "a b.apk"):
            with self.assertRaises(ValueError, msg=bad_name):
                self.add("1.0.0", name=bad_name)
        with self.assertRaises(ValueError):
            self.add("1.0.0", build=0)
        with self.assertRaises(ValueError):
            self.add("1.0.0", notes="x" * 4001)
        self.assertFalse(self.folder.exists() and any(self.folder.rglob("*.apk")))

    def test_missing_apk_is_an_error(self) -> None:
        with self.assertRaises(ValueError):
            add_download.add_download(self.folder, self.root / "nope.apk", version="1.0.0", build=1)

    def test_released_at_is_utc_iso(self) -> None:
        entry = self.add("1.0.0", released_at=datetime(2026, 10, 30, 9, 0, tzinfo=UTC))
        self.assertEqual(entry["released_at"], "2026-10-30T09:00:00+00:00")

    def test_command_line_prints_only_version_size_and_hash(self) -> None:
        result = subprocess.run(
            [sys.executable, "-I", str(SCRIPT), "--dir", str(self.folder), "--apk", str(self.apk),
             "--version", "2.0.0", "--build", "3"],
            capture_output=True, text=True, check=False,
        )  # fmt: skip
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Published 2.0.0 (build 3)", result.stdout)
        self.assertIn("SHA-256", result.stdout)

    def test_command_line_error_exit_code(self) -> None:
        result = subprocess.run(
            [sys.executable, "-I", str(SCRIPT), "--dir", str(self.folder), "--apk", str(self.apk),
             "--version", "bad", "--build", "1"],
            capture_output=True, text=True, check=False,
        )  # fmt: skip
        self.assertEqual(result.returncode, 1)
        self.assertIn("version must look like", result.stderr)


if __name__ == "__main__":
    unittest.main()

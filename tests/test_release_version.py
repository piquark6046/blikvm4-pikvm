"""The tag classifier is the release workflow's trigger boundary."""

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


PATH = Path(__file__).resolve().parents[1] / "build/release/version.py"
SPEC = importlib.util.spec_from_file_location("release_version", PATH)
VERSION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERSION)
COMMIT = "0123abcd" + "f" * 32


class ReleaseVersionTests(unittest.TestCase):
    def test_accepted_channels(self):
        for tag, channel, prerelease in (
            ("0.1.0", "stable", False),
            ("1.2.5", "stable", False),
            ("1.2.5-beta.0", "beta", True),
            ("1.2.5-beta.2", "beta", True),
            ("1.5.0-build.0123abcd", "build", True),
        ):
            with self.subTest(tag=tag):
                record = VERSION.classify(tag, COMMIT, "0123abcd")
                self.assertEqual((record["channel"], record["prerelease"]), (channel, prerelease))

    def test_rejected_tags(self):
        for tag in (
            "v1.2.5", "01.2.5", "1.02.5", "1.2.05", "1.2", "1.2.5-rc.1",
            "1.2.5-beta", "1.2.5-beta.02", "1.2.5-build.ABCDEF12",
            "1.2.5-build.abcdefg0", "1.2.5-build.1234567",
            "1.2.5-build.123456789", "1.2.5+build.1", "1.2.5\n",
        ):
            with self.subTest(tag=tag), self.assertRaises(VERSION.InvalidTag):
                VERSION.classify(tag, COMMIT, "0123abcd")

    def test_build_suffix_must_match(self):
        with self.assertRaisesRegex(VERSION.InvalidTag, "suffix"):
            VERSION.classify("1.5.0-build.12345678", COMMIT, "0123abcd")

    def test_ref_must_be_exact_tag(self):
        with self.assertRaisesRegex(VERSION.InvalidTag, "exact tag"):
            VERSION.classify_ref("1.2.5", "refs/heads/main")

    def test_annotated_build_tag_resolves_commit_not_tag_object(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            def git(*args):
                return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()
            git("init", "-q")
            git("config", "user.name", "Release test")
            git("config", "user.email", "release-test@localhost")
            (repo / "source").write_text("pinned\n")
            git("add", "source")
            git("commit", "-qm", "source")
            commit = git("rev-parse", "HEAD")
            short = git("rev-parse", "--short=8", "HEAD")
            tag = f"1.5.0-build.{short}"
            git("tag", "-a", tag, "-m", "release")
            self.assertNotEqual(git("rev-parse", f"refs/tags/{tag}"), commit)
            result = subprocess.check_output(
                ["python3", str(PATH), "check", tag, f"refs/tags/{tag}"],
                cwd=repo, text=True)
            self.assertEqual(json.loads(result)["git_commit"], commit)
            self.assertEqual(json.loads(result)["tag_object"],
                             git("rev-parse", f"refs/tags/{tag}"))


if __name__ == "__main__":
    unittest.main()

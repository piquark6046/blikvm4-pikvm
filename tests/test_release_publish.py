"""An existing GitHub release is never overwritten when its bytes conflict."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build/release"))
import policy  # noqa: E402
import publish  # noqa: E402


class ReleasePublishTests(unittest.TestCase):
    def test_existing_asset_conflict_stops_before_upload(self):
        manifest = {"release_tag": "1.2.5-beta.2", "channel": "beta", "prerelease": True,
                    "git_commit": "c" * 40,
                    "public_image": {"sha256": "a" * 64},
                    "compressed_image": {"sha256": "b" * 64},
                    "qualification": {"bootloader_hardware": "PASSED", "core_kvm": "NOT_CLAIMED",
                                      "p2": "NOT_CLAIMED", "p3": "UNACCEPTED",
                                      "m6_atx": "DEFERRED", "ro_overlay": "DEFERRED"}}
        remote = {"assets": [{"name": "asset.txt"}], "isDraft": True,
                  "isPrerelease": True, "name": "BliKVM v4 PiKVM 1.2.5-beta.2",
                  "tagName": "1.2.5-beta.2", "targetCommitish": "c" * 40,
                  "body": publish.notes(manifest)}
        calls = []
        def fake_gh(*args, **_kwargs):
            calls.append(args)
            if args[:2] == ("release", "view"):
                return subprocess.CompletedProcess(args, 0, json.dumps(remote), "")
            if args[:2] == ("release", "download"):
                Path(args[-1]).write_bytes(b"different remote bytes")
                return subprocess.CompletedProcess(args, 0, "", "")
            raise AssertionError(f"unexpected GitHub write: {args}")
        with tempfile.TemporaryDirectory() as temp:
            dist = Path(temp)
            (dist / "asset.txt").write_bytes(b"local release bytes")
            with patch.dict(os.environ, {"GH_TOKEN": "test-token"}), \
                 patch.object(publish.prepublish, "check", return_value=manifest), \
                 patch.object(publish, "gh", side_effect=fake_gh):
                with self.assertRaisesRegex(policy.ReleaseBlocked, "EXISTING_RELEASE_ASSET_CONFLICT"):
                    publish.publish(dist, "1.2.5-beta.2", "refs/tags/1.2.5-beta.2")
        self.assertFalse(any(args[:2] in (("release", "upload"), ("release", "edit"))
                             for args in calls))


if __name__ == "__main__":
    unittest.main()

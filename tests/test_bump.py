import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import bump  # noqa: E402

FIX = os.path.join(HERE, "fixtures")


def fixture(name):
    with open(os.path.join(FIX, name), "rb") as fh:
        return fh.read()


TOOLS = bump.load_tools(os.path.join(os.path.dirname(HERE), "tools.json"))
TOOL = TOOLS[0]
with open(os.path.join(os.path.dirname(HERE), "templates", "formula.rb.tmpl"), encoding="utf-8") as fh:
    TEMPLATE = fh.read()


class BumpTest(unittest.TestCase):
    def run_bump(self, releases, checksums=b"checksums.txt", tool=TOOL):
        calls = []

        def fetch(url):
            calls.append(url)
            return fixture("checksums.txt") if checksums == b"checksums.txt" else checksums

        with tempfile.TemporaryDirectory() as d:
            res = bump.bump_tool(tool, releases, fetch, TEMPLATE, d)
            files = os.listdir(d)
            text = open(os.path.join(d, files[0])).read() if files else None
            again = bump.bump_tool(tool, releases, fetch, TEMPLATE, d) if files else None
        return res, text, calls, again

    def test_renders_latest_stable(self):
        rels = json.loads(fixture("releases.json"))
        res, text, calls, again = self.run_bump(rels)
        self.assertEqual(res, ("0.3.0", "written"))
        self.assertEqual(again, ("0.3.0", "unchanged"))
        self.assertEqual(set(calls), {"https://github.com/pkalin/shadewright/releases/download/v0.3.0/checksums.txt"})
        self.assertIn("class KubectlShadewright < Formula", text)
        self.assertIn("releases/download/v0.3.0/kubectl-shadewright_0.3.0_darwin_arm64.tar.gz", text)
        self.assertIn('sha256 "%s"' % ("b" * 64), text)  # darwin/arm64
        self.assertIn('system bin/"kubectl-shadewright", "version"', text)
        self.assertNotIn("{{", text)
        self.assertNotIn("rc.1", text)

    def test_no_matching_assets(self):
        rels = json.loads(fixture("releases-no-assets.json"))
        res, text, calls, _ = self.run_bump(rels)
        self.assertEqual(res, ("0.2.0", "none"))
        self.assertIsNone(text)
        self.assertEqual(calls, [])

    def test_no_stable_release(self):
        rels = [r for r in json.loads(fixture("releases.json")) if r["prerelease"]]
        res, text, _, _ = self.run_bump(rels)
        self.assertEqual(res, (None, "none"))
        self.assertIsNone(text)

    def test_rejects_bad_digest(self):
        with self.assertRaises(bump.BumpError):
            self.run_bump(json.loads(fixture("releases.json")), checksums=b"zz  x.tar.gz\n")

    def test_rejects_missing_checksum(self):
        text = b"\n".join(l for l in fixture("checksums.txt").splitlines() if b"linux_arm64" not in l)
        with self.assertRaises(bump.BumpError):
            self.run_bump(json.loads(fixture("releases.json")), checksums=text)

    def test_rejects_duplicate_checksum(self):
        with self.assertRaises(bump.BumpError):
            bump.parse_checksums(("a" * 64 + "  x\n") * 2)

    def test_picks_highest_version(self):
        rels = [{"tag_name": t, "prerelease": False, "draft": False, "assets": []} for t in ("v0.9.0", "v0.10.0", "v0.2.0")]
        self.assertEqual(bump.latest_release(TOOL, rels)[1], "0.10.0")

    def test_skips_drafts(self):
        rels = [{"tag_name": "v1.0.0", "prerelease": False, "draft": True, "assets": []}]
        self.assertEqual(bump.latest_release(TOOL, rels), (None, None))

    def test_tool_validation(self):
        for key, val in (("name", "Bad Name"), ("repo", "a/b c"), ("description", 'x"y'), ("homepage", "http://x"),
                         ("test_args", ["#{system}"]), ("platforms", ["linux/amd64"])):
            bad = dict(TOOL, **{key: val})
            with self.assertRaises(bump.BumpError, msg=key):
                bump.validate_tool(bad)

    def test_refuses_foreign_host(self):
        with self.assertRaises(bump.BumpError):
            bump.http_get("https://example.com/checksums.txt")


if __name__ == "__main__":
    unittest.main()

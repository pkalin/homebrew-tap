#!/usr/bin/env python3
"""Render Formula/<name>.rb from tools.json and the latest public release.

Reads the latest non-pre-release of each tool through the public GitHub API,
downloads its checksums file (as text only, never executed) and renders the
formula from templates/formula.rb.tmpl. Python 3 standard library only.

stdout, one line per tool: "<name> <version|-> <written|unchanged|none>".
"""
import argparse
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
ASSET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
TEXT_RE = re.compile(r"^[A-Za-z0-9 ,.:;()/@+_-]+$")  # no quote, backslash or '#'
URL_RE = re.compile(r"^https://[A-Za-z0-9./_-]+$")
PLATFORMS = ("darwin/amd64", "darwin/arm64", "linux/amd64", "linux/arm64")
MAX_BYTES = 1024 * 1024


class BumpError(Exception):
    pass


def http_get(url):
    """Fetch a small https resource from GitHub. Returns bytes."""
    if not url.startswith(("https://api.github.com/", "https://github.com/")):
        raise BumpError("refusing to fetch " + url)
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "homebrew-tap-bump"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (host checked above)
        data = resp.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise BumpError("response too large: " + url)
    return data


def validate_tool(tool):
    def need(cond, msg):
        if not cond:
            raise BumpError("tools.json (%s): %s" % (tool.get("name", "?"), msg))

    need(NAME_RE.match(str(tool.get("name", ""))), "bad name")
    need(REPO_RE.match(str(tool.get("repo", ""))), "bad repo")
    try:
        pat = re.compile(tool["tag_pattern"])
    except (KeyError, re.error):
        raise BumpError("tools.json (%s): bad tag_pattern" % tool.get("name"))
    need("version" in pat.groupindex, "tag_pattern needs a (?P<version>...) group")
    tmpl = str(tool.get("asset_template", ""))
    need(all(k in tmpl for k in ("{version}", "{os}", "{arch}")), "asset_template needs {version} {os} {arch}")
    need(ASSET_RE.match(tmpl.replace("{version}", "1").replace("{os}", "a").replace("{arch}", "b")), "bad asset_template")
    need(ASSET_RE.match(str(tool.get("checksums_asset", ""))), "bad checksums_asset")
    plats = tool.get("platforms")
    need(sorted(plats or []) == sorted(PLATFORMS), "platforms must be exactly " + ", ".join(PLATFORMS))
    need(ASSET_RE.match(str(tool.get("binary", ""))), "bad binary")
    args = tool.get("test_args")
    need(isinstance(args, list) and all(TEXT_RE.match(str(a)) for a in args), "bad test_args")
    for key in ("description", "license"):
        need(TEXT_RE.match(str(tool.get(key, ""))), "bad " + key)
    need(URL_RE.match(str(tool.get("homepage", ""))), "bad homepage")
    return pat


def load_tools(path):
    with open(path, encoding="utf-8") as fh:
        tools = json.load(fh)["tools"]
    names = [t.get("name") for t in tools]
    if len(set(names)) != len(names):
        raise BumpError("tools.json: duplicate names")
    for t in tools:
        validate_tool(t)
    return tools


def latest_release(tool, releases):
    """Highest-version published non-pre-release whose tag matches the pattern."""
    pat = re.compile(tool["tag_pattern"])
    best = None
    for rel in releases:
        if rel.get("draft") or rel.get("prerelease"):
            continue
        m = pat.fullmatch(str(rel.get("tag_name", "")))
        if not m or not VERSION_RE.match(m.group("version")):
            continue
        key = tuple(int(p) for p in m.group("version").split("."))
        if best is None or key > best[0]:
            best = (key, rel, m.group("version"))
    return (best[1], best[2]) if best else (None, None)


def parse_checksums(text):
    sums = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 2 or not SHA_RE.match(parts[0]):
            raise BumpError("malformed checksums line")
        name = parts[1].lstrip("*")
        if name in sums:
            raise BumpError("duplicate checksum entry: " + name)
        sums[name] = parts[0]
    return sums


def class_name(name):
    return "".join(p.capitalize() for p in name.split("-"))


def render(tool, tag, version, sums, template):
    values = {
        "class_name": class_name(tool["name"]),
        "description": tool["description"],
        "homepage": tool["homepage"],
        "license": tool["license"],
        "binary": tool["binary"],
        "test_args": "".join(', "%s"' % a for a in tool["test_args"]),
    }
    for plat in PLATFORMS:
        os_, arch = plat.split("/")
        asset = tool["asset_template"].format(version=version, os=os_, arch=arch)
        values["%s_%s_url" % (os_, arch)] = "https://github.com/%s/releases/download/%s/%s" % (tool["repo"], tag, asset)
        values["%s_%s_sha256" % (os_, arch)] = sums[asset]
    out = template
    for key, val in values.items():
        out = out.replace("{{%s}}" % key, val)
    if "{{" in out:
        raise BumpError("unfilled placeholder in template")
    return out


def bump_tool(tool, releases, fetch, template, formula_dir):
    """Returns (version or None, status)."""
    rel, version = latest_release(tool, releases)
    if rel is None:
        return None, "none"
    assets = {a.get("name") for a in rel.get("assets", [])}
    needed = [tool["asset_template"].format(version=version, os=p.split("/")[0], arch=p.split("/")[1]) for p in PLATFORMS]
    if not set(needed) <= assets or tool["checksums_asset"] not in assets:
        return version, "none"
    tag = rel["tag_name"]
    url = "https://github.com/%s/releases/download/%s/%s" % (tool["repo"], tag, tool["checksums_asset"])
    sums = parse_checksums(fetch(url).decode("utf-8"))
    missing = [a for a in needed if a not in sums]
    if missing:
        raise BumpError("checksums file lacks " + ", ".join(missing))
    text = render(tool, tag, version, sums, template)
    path = os.path.join(formula_dir, tool["name"] + ".rb")
    old = None
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            old = fh.read()
    if old == text:
        return version, "unchanged"
    os.makedirs(formula_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return version, "written"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tools", default=os.path.join(ROOT, "tools.json"))
    ap.add_argument("--template", default=os.path.join(ROOT, "templates", "formula.rb.tmpl"))
    ap.add_argument("--formula-dir", default=os.path.join(ROOT, "Formula"))
    ap.add_argument("--tool", help="only this tool")
    ap.add_argument("--names", action="store_true", help="print tool names and exit")
    args = ap.parse_args(argv)
    try:
        tools = load_tools(args.tools)
        if args.names:
            for t in tools:
                print(t["name"])
            return 0
        if args.tool:
            tools = [t for t in tools if t["name"] == args.tool]
            if not tools:
                raise BumpError("unknown tool " + args.tool)
        with open(args.template, encoding="utf-8") as fh:
            template = fh.read()
        for tool in tools:
            data = http_get("https://api.github.com/repos/%s/releases?per_page=30" % tool["repo"])
            version, status = bump_tool(tool, json.loads(data), http_get, template, args.formula_dir)
            print(tool["name"], version or "-", status)
    except (BumpError, OSError, ValueError, KeyError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

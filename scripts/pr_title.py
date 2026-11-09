#!/usr/bin/env python3
"""Check a pull request title against the rules in .github/workflows/pr-title.yml.

pr-title.yml checks titles with action-semantic-pull-request on pull_request_target. Pull requests
opened by bump.yml with GITHUB_TOKEN do not trigger that event, so bump.yml starts pr-title.yml by
workflow_dispatch, and that run uses this script. The types, scopes and subject pattern are read
from pr-title.yml itself, so both paths share one set of rules. Python 3 standard library only.

Usage: TITLE="..." pr_title.py   (exit 0 when valid, 1 with a message when not)
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "pr-title.yml")
WORD_RE = re.compile(r"^[a-z][a-z0-9-]*$")


class RulesError(Exception):
    pass


def load_rules(path=WORKFLOW):
    """Return (types, scopes, subject_pattern) from the action's `with:` block."""
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    rules = {}
    i = 0
    while i < len(lines):
        m = re.match(r"^(\s*)(types|scopes): \|\s*$", lines[i])
        if m:
            indent, key, items = len(m.group(1)), m.group(2), []
            i += 1
            while i < len(lines) and lines[i].strip() and len(lines[i]) - len(lines[i].lstrip()) > indent:
                items.append(lines[i].strip())
                i += 1
            rules[key] = items
            continue
        m = re.match(r"^\s*subjectPattern: (\S.*)$", lines[i])
        if m:
            rules["subject"] = m.group(1).strip()
        i += 1
    if not rules.get("types") or not rules.get("scopes") or "subject" not in rules:
        raise RulesError(f"types, scopes or subjectPattern missing in {path}")
    for word in rules["types"] + rules["scopes"]:
        if not WORD_RE.match(word):
            raise RulesError(f"unexpected type or scope {word!r} in {path}")
    return rules["types"], rules["scopes"], re.compile(rules["subject"])


def check(title, types, scopes, subject_re):
    """Return None when the title is valid, else a message."""
    m = re.match(r"^([a-z]+)(?:\(([^()]+)\))?(!)?: (.+)$", title)
    if not m:
        return "The title must look like 'type(scope): summary' (Conventional Commits)."
    kind, scope, _, subject = m.groups()
    if kind not in types:
        return f"Unknown type {kind!r}; allowed: {', '.join(types)}."
    if scope is not None:
        for s in scope.split(","):
            if s.strip() not in scopes:
                return f"Unknown scope {s.strip()!r}; allowed: {', '.join(scopes)}."
    if not subject_re.match(subject):
        return f'The summary "{subject}" must start with a lower-case letter and must not end with a full stop.'
    return None


def main():
    title = os.environ.get("TITLE", "")
    if not title:
        print("TITLE is empty", file=sys.stderr)
        return 1
    try:
        error = check(title, *load_rules())
    except RulesError as e:
        print(e, file=sys.stderr)
        return 1
    if error:
        print(error, file=sys.stderr)
        return 1
    print("Title OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

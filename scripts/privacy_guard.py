#!/usr/bin/env python3
"""Pre-commit privacy guard.

The repository is public. This script blocks a commit when the staged changes
or the commit metadata could leak personal or secret data:

* author/committer identity that is not an anonymous noreply address;
* forbidden files (.env, private keys, database dumps);
* added lines containing e-mail addresses, Telegram bot tokens, private keys,
  local user paths (C:\\Users\\..., /home/..., /Users/...) or hard-coded secrets.

Usage (wired up by .githooks/):
    python scripts/privacy_guard.py staged        # pre-commit
    python scripts/privacy_guard.py message FILE  # commit-msg
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import PurePosixPath

ALLOWED_EMAIL_SUFFIXES = (
    "@users.noreply.github.com",
    "@anthropic.com",  # Co-Authored-By trailer
    "@example.com",
    "@example.org",
)

FORBIDDEN_FILE_PATTERNS = [
    re.compile(r"(^|/)\.env($|\.(?!example$)[^/]*$)"),
    re.compile(r"\.(pem|key|p12|pfx|sqlite3?|db|dump|sql|age)$", re.I),
    re.compile(r"(^|/)id_(rsa|ed25519|ecdsa)$"),
]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")

CONTENT_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("Telegram bot token", re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b")),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("local Windows user path", re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+", re.I)),
    ("local Windows user path", re.compile(r"/[a-z]/Users/", re.I)),
    ("local Unix home path", re.compile(r"(?<![\w.])/(home|Users)/[A-Za-z0-9._-]+/")),
    ("Windows 8.3 user path", re.compile(r"\\[0-9A-F]{4,6}~\d", re.I)),
    (
        "hard-coded secret",
        re.compile(
            r"(?i)\b(bot_token|api_key|secret|password|passwd|pepper)\b\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"
        ),
    ),
]

# Files that legitimately contain the patterns above (this guard itself).
SELF_EXEMPT = {"scripts/privacy_guard.py"}


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout


def bad_emails(text: str) -> list[str]:
    return [
        e for e in EMAIL_RE.findall(text)
        if not e.lower().endswith(ALLOWED_EMAIL_SUFFIXES)
    ]


def check_identity() -> list[str]:
    problems = []
    for var in ("GIT_AUTHOR_IDENT", "GIT_COMMITTER_IDENT"):
        ident = git("var", var)
        email = ident[ident.find("<") + 1 : ident.find(">")]
        if not email.lower().endswith("@users.noreply.github.com"):
            problems.append(
                f"{var}: commit would be signed with a non-anonymous e-mail. "
                "Run: git config --local user.email finuchet-dev@users.noreply.github.com"
            )
    return problems


def check_staged() -> list[str]:
    problems = check_identity()
    files = [f for f in git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").split("\0") if f]
    for path in files:
        posix = str(PurePosixPath(path))
        for pattern in FORBIDDEN_FILE_PATTERNS:
            if pattern.search(posix):
                problems.append(f"{posix}: this file type must never be committed")
        if posix in SELF_EXEMPT:
            continue
        diff = git("diff", "--cached", "-U0", "--no-color", "--", path)
        for line in diff.splitlines():
            if not line.startswith("+") or line.startswith("+++"):
                continue
            added = line[1:]
            for email in bad_emails(added):
                problems.append(f"{posix}: e-mail address {email!r}")
            for name, rule in CONTENT_RULES:
                if rule.search(added):
                    problems.append(f"{posix}: {name}: {added.strip()[:80]!r}")
    return problems


def check_message(path: str) -> list[str]:
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    problems = [f"commit message: e-mail address {e!r}" for e in bad_emails(text)]
    for name, rule in CONTENT_RULES:
        if rule.search(text):
            problems.append(f"commit message: {name}")
    return problems


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in {"staged", "message"}:
        print(__doc__)
        return 2
    problems = check_staged() if sys.argv[1] == "staged" else check_message(sys.argv[2])
    if problems:
        print("privacy-guard: commit blocked - possible leak of personal/secret data:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print("Fix the lines above (move secrets to .env) and try again.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

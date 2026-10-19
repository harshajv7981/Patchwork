#!/usr/bin/env python3
"""Patchwork bot state + hard limits.

Every upstream action (issue, PR, comment) goes through this file, so the limits that
keep the bot account in good standing are enforced in code, not left to judgement.
Exit code 0 = allowed/ok, 3 = refused by a limit (reason printed as JSON).

State lives in $PATCHWORK_BOT_HOME/state.json (default ~/.patchwork-bot/state.json).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

DAILY_NEW_SUBMISSIONS = 2   # new issues/PRs opened per day, all repos combined
OPEN_PER_REPO = 1           # open items per repo at any time
MAX_REVIEW_ROUNDS = 2       # automatic replies to review comments per PR
MAX_CI_ATTEMPTS = 2         # automatic CI-fix pushes per PR
AUDIT_COOLDOWN_DAYS = 14    # don't re-audit the same repo more often than this
OPEN_STATUSES = {"issue_open", "invited", "pr_open"}
REFUSED = 3


def _home() -> Path:
    return Path(os.environ.get("PATCHWORK_BOT_HOME", Path.home() / ".patchwork-bot"))


def _path() -> Path:
    return _home() / "state.json"


def load() -> dict:
    try:
        state = json.loads(_path().read_text())
    except FileNotFoundError:
        state = {"repos": {}, "items": [], "seen": {}}
    state.setdefault("deferred", {})  # repo -> {fingerprint: finding}
    return state


def save(state: dict) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    tmp.replace(path)  # atomic: a crash mid-write never corrupts the state


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fingerprint(repo: str, kind: str, file: str, title: str) -> str:
    key = "|".join(part.strip().lower() for part in (repo, kind, file, title))
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def check(state: dict, repo: str, new_submission: bool = True, audit: bool = False) -> tuple[bool, str]:
    """Can the bot open a new item in `repo` right now? With audit=True: is it due for an audit?"""
    info = state["repos"].get(repo, {})
    if info.get("status") == "dnc":
        return False, f"{repo} is do-not-contact: {info.get('reason', '')}"
    if audit and info.get("audited_at"):
        last = datetime.fromisoformat(info["audited_at"])
        if datetime.now(timezone.utc) - last < timedelta(days=AUDIT_COOLDOWN_DAYS):
            return False, f"{repo} was audited {info['audited_at'][:10]} (cool-down {AUDIT_COOLDOWN_DAYS}d)"
    open_here = [i for i in state["items"] if i["repo"] == repo and i["status"] in OPEN_STATUSES]
    if len(open_here) >= OPEN_PER_REPO:
        return False, f"{repo} already has an open item ({open_here[0]['url']})"
    if new_submission:
        today = date.today().isoformat()
        made_today = [i for i in state["items"] if i["created_at"][:10] == today]
        if len(made_today) >= DAILY_NEW_SUBMISSIONS:
            return False, f"daily cap of {DAILY_NEW_SUBMISSIONS} new submissions reached"
    return True, "ok"


def _out(payload: dict, code: int = 0) -> int:
    print(json.dumps(payload, indent=2))
    return code


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="may we open a new item in this repo?")
    c.add_argument("repo")
    c.add_argument("--audit", action="store_true", help="also require the audit cool-down to have passed")

    t = sub.add_parser("audited", help="record that a repo was just audited (starts the cool-down)")
    t.add_argument("repo")

    s = sub.add_parser("seen", help="was this finding already submitted or dropped?")
    for a in ("--repo", "--kind", "--file", "--title"):
        s.add_argument(a, required=True)

    d = sub.add_parser("drop", help="remember a dropped finding so audits don't re-find it")
    for a in ("--repo", "--kind", "--file", "--title", "--reason"):
        d.add_argument(a, required=True)

    f = sub.add_parser("defer", help="keep a good finding for later (repo slot taken / cap reached)")
    for a in ("--repo", "--kind", "--file", "--title"):
        f.add_argument(a, required=True)
    f.add_argument("--line", type=int, default=0)
    f.add_argument("--confidence", default="")
    f.add_argument("--note", default="")

    dl = sub.add_parser("deferred", help="deferred findings for a repo (or all repos)")
    dl.add_argument("repo", nargs="?")

    a = sub.add_parser("add", help="record a new upstream issue/PR (enforces caps)")
    for x in ("--repo", "--kind", "--file", "--title", "--url"):
        a.add_argument(x, required=True)
    a.add_argument("--type", choices=["issue", "pr"], required=True)
    a.add_argument("--number", type=int, required=True)
    a.add_argument("--branch", default="")

    u = sub.add_parser("update", help="update an item's status / counters")
    u.add_argument("id")
    u.add_argument("--status", choices=sorted(OPEN_STATUSES | {"merged", "rejected", "closed"}))
    u.add_argument("--pr-url")
    u.add_argument("--pr-number", type=int)
    u.add_argument("--branch")
    u.add_argument("--inc", choices=["review", "ci"], help="count one automatic review reply / CI fix")

    m = sub.add_parser("mark", help="set a repo's trust status")
    m.add_argument("repo")
    m.add_argument("status", choices=["new", "trusted", "dnc"])
    m.add_argument("--reason", default="")

    sub.add_parser("open", help="items that still need watching")
    r = sub.add_parser("repo", help="show a repo's trust status")
    r.add_argument("repo")
    sub.add_parser("summary", help="counts for the run report")

    args = p.parse_args(argv)
    state = load()

    if args.cmd == "check":
        ok, reason = check(state, args.repo, audit=args.audit)
        return _out({"ok": ok, "reason": reason}, 0 if ok else REFUSED)

    if args.cmd == "audited":
        state["repos"].setdefault(args.repo, {"status": "new"})["audited_at"] = _now()
        save(state)
        return _out({"ok": True, "repo": args.repo})

    if args.cmd == "seen":
        fp = fingerprint(args.repo, args.kind, args.file, args.title)
        return _out({"seen": fp in state["seen"], "fingerprint": fp, "detail": state["seen"].get(fp)})

    if args.cmd == "drop":
        fp = fingerprint(args.repo, args.kind, args.file, args.title)
        state["seen"][fp] = {"outcome": "dropped", "reason": args.reason, "at": _now()}
        state["deferred"].get(args.repo, {}).pop(fp, None)
        save(state)
        return _out({"dropped": fp})

    if args.cmd == "defer":
        fp = fingerprint(args.repo, args.kind, args.file, args.title)
        if fp in state["seen"]:
            return _out({"ok": False, "reason": f"already {state['seen'][fp]['outcome']}"}, REFUSED)
        state["deferred"].setdefault(args.repo, {})[fp] = {
            "kind": args.kind, "file": args.file, "line": args.line, "title": args.title,
            "confidence": args.confidence, "note": args.note, "at": _now(),
        }
        save(state)
        return _out({"ok": True, "deferred": fp})

    if args.cmd == "deferred":
        repos = [args.repo] if args.repo else sorted(state["deferred"])
        return _out({r: list(state["deferred"].get(r, {}).values()) for r in repos})

    if args.cmd == "add":
        ok, reason = check(state, args.repo)
        if not ok:
            return _out({"ok": False, "reason": reason}, REFUSED)
        fp = fingerprint(args.repo, args.kind, args.file, args.title)
        item = {
            "id": f"pb-{len(state['items']) + 1:04d}",
            "repo": args.repo, "kind": args.kind, "type": args.type, "title": args.title,
            "file": args.file, "url": args.url, "number": args.number, "branch": args.branch,
            "fingerprint": fp, "status": "pr_open" if args.type == "pr" else "issue_open",
            "review_rounds": 0, "ci_attempts": 0, "created_at": _now(), "updated_at": _now(),
        }
        state["items"].append(item)
        state["seen"][fp] = {"outcome": "submitted", "item": item["id"], "at": _now()}
        state["deferred"].get(args.repo, {}).pop(fp, None)
        state["repos"].setdefault(args.repo, {"status": "new"})
        save(state)
        return _out({"ok": True, "item": item})

    if args.cmd == "update":
        item = next((i for i in state["items"] if i["id"] == args.id), None)
        if item is None:
            return _out({"ok": False, "reason": f"no item {args.id}"}, 2)
        if args.inc:
            field, limit = ("review_rounds", MAX_REVIEW_ROUNDS) if args.inc == "review" else ("ci_attempts", MAX_CI_ATTEMPTS)
            if item[field] >= limit:
                return _out({"ok": False, "reason": f"{field} limit {limit} reached — hand off, don't push again"}, REFUSED)
            item[field] += 1
        if args.pr_url:
            item["url"], item["type"] = args.pr_url, "pr"
        if args.pr_number:
            item["number"] = args.pr_number
        if args.branch:
            item["branch"] = args.branch
        if args.status:
            item["status"] = args.status
            if args.status == "merged":
                state["repos"].setdefault(item["repo"], {})["status"] = "trusted"
            if args.status == "rejected":
                state["repos"].setdefault(item["repo"], {}).update(status="dnc", reason=f"{item['id']} rejected", at=_now())
        item["updated_at"] = _now()
        save(state)
        return _out({"ok": True, "item": item})

    if args.cmd == "mark":
        if state["repos"].get(args.repo, {}).get("status") == "dnc" and args.status != "dnc":
            return _out({"ok": False, "reason": "do-not-contact is permanent"}, REFUSED)
        state["repos"].setdefault(args.repo, {}).update(status=args.status, reason=args.reason, at=_now())
        save(state)
        return _out({"ok": True, "repo": args.repo, "status": args.status})

    if args.cmd == "open":
        return _out({"items": [i for i in state["items"] if i["status"] in OPEN_STATUSES]})

    if args.cmd == "repo":
        return _out({"repo": args.repo, **state["repos"].get(args.repo, {"status": "new"})})

    if args.cmd == "summary":
        today = date.today().isoformat()
        return _out({
            "submitted_today": sum(i["created_at"][:10] == today for i in state["items"]),
            "daily_cap": DAILY_NEW_SUBMISSIONS,
            "open": sum(i["status"] in OPEN_STATUSES for i in state["items"]),
            "merged": sum(i["status"] == "merged" for i in state["items"]),
            "rejected": sum(i["status"] == "rejected" for i in state["items"]),
            "trusted_repos": sorted(r for r, v in state["repos"].items() if v.get("status") == "trusted"),
            "dnc_repos": sorted(r for r, v in state["repos"].items() if v.get("status") == "dnc"),
        })
    return 2


if __name__ == "__main__":
    sys.exit(main())

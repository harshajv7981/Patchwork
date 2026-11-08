#!/usr/bin/env python3
"""Bug bounty research log, candidate queue, and the work-in-progress limits.

One investigation may be worked on (scoping or testing) at a time, and at most
MAX_AWAITING submitted reports may wait for triage at once; `start`/`promote` refuse past
either limit until something is submitted or closed with an outcome. patchwork-bot queues
proven security findings with `candidate` (private, never posted). Exit 0 = ok, 3 = refused.

State: $BUG_BOUNTY_HOME/log.json (default ~/.bug-bounty). Each investigation also gets a
folder there holding scope.md, notes.md and report.md, copied from the skill's templates.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKING = {"scoping", "testing"}
MAX_AWAITING = 3  # submitted reports awaiting triage at once (operator decision 2026-11-08)
OUTCOMES = ["accepted", "duplicate", "informative", "out_of_scope", "rejected", "disproved", "abandoned"]
TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
REFUSED = 3


def _home() -> Path:
    return Path(os.environ.get("BUG_BOUNTY_HOME", Path.home() / ".bug-bounty"))


def load() -> dict:
    try:
        return json.loads((_home() / "log.json").read_text())
    except FileNotFoundError:
        return {"investigations": []}


def save(log: dict) -> None:
    path = _home() / "log.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(log, indent=2))
    tmp.replace(path)  # atomic: a crash mid-write never loses the log


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def active(log: dict) -> dict | None:
    """The investigation being worked on (scoping/testing), if any."""
    return next((i for i in log["investigations"] if i["status"] in WORKING), None)


def awaiting(log: dict) -> list[dict]:
    return [i for i in log["investigations"] if i["status"] == "submitted"]


def _start(log: dict, program: str, policy: str) -> tuple[dict | None, str]:
    """Open an investigation in `log` (caller saves). Returns (investigation, "") or (None, refusal)."""
    cur = active(log)
    if cur:
        return None, f"{cur['id']} ({cur['program']}) is still {cur['status']}; submit or close it first"
    if len(awaiting(log)) >= MAX_AWAITING:
        return None, f"{MAX_AWAITING} reports already await triage; close one with its outcome first"
    if not policy.startswith("https://"):
        return None, "policy must be the program's https policy URL"
    inv = {"id": f"bb-{len(log['investigations']) + 1:03d}", "program": program, "policy": policy,
           "status": "scoping", "hypothesis": "", "report_url": "", "outcome": "", "bounty": 0.0,
           "note": "", "started_at": _now(), "submitted_at": "", "closed_at": ""}
    folder = _home() / inv["id"]
    folder.mkdir(parents=True, exist_ok=True)
    for t in TEMPLATES.glob("*.md"):
        shutil.copy(t, folder / t.name)
    log["investigations"].append(inv)
    return inv, ""


def _out(payload: dict, code: int = 0) -> int:
    print(json.dumps(payload, indent=2))
    return code


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start", help="open a new investigation (refused while one is active)")
    s.add_argument("program")
    s.add_argument("--policy", required=True, help="URL of the program's current policy")
    h = sub.add_parser("hypothesis", help="record the one-sentence hypothesis; moves to testing")
    h.add_argument("text")
    sb = sub.add_parser("submit", help="record that the report was submitted (by the human)")
    sb.add_argument("--url", required=True, help="report URL / ID on the platform")
    c = sub.add_parser("close", help="record the outcome; frees the slot for the next one")
    c.add_argument("outcome", choices=OUTCOMES)
    c.add_argument("--id", help="which investigation (needed when more than one is open)")
    c.add_argument("--bounty", type=float, default=0.0)
    c.add_argument("--note", default="")
    sub.add_parser("status", help="the investigation being worked on, and reports awaiting triage")
    sub.add_parser("metrics", help="quality metrics across all investigations")
    ca = sub.add_parser("candidate", help="queue a proven security finding from patchwork-bot (private)")
    for a in ("--repo", "--file", "--title", "--channel", "--policy"):
        ca.add_argument(a, required=True)
    ca.add_argument("--severity", default="")
    ca.add_argument("--note", default="")
    sub.add_parser("candidates", help="queued candidates not yet promoted or discarded")
    pr = sub.add_parser("promote", help="turn a candidate into the active investigation")
    pr.add_argument("cid")
    dc = sub.add_parser("discard", help="drop a candidate (false positive, duplicate, fixed)")
    dc.add_argument("cid")
    dc.add_argument("--reason", required=True)
    args = p.parse_args(argv)
    log = load()
    log.setdefault("candidates", [])
    cur = active(log)

    if args.cmd == "candidate":
        key = [args.repo.lower(), args.file, args.title.strip().lower()]
        dup = next((c for c in log["candidates"] if [c["repo"].lower(), c["file"], c["title"].lower()] == key), None)
        if dup:
            return _out({"ok": False, "reason": f"already queued as {dup['id']} ({dup['status']})"}, REFUSED)
        c = {"id": f"bc-{len(log['candidates']) + 1:03d}", "repo": args.repo, "file": args.file,
             "title": args.title.strip(), "channel": args.channel, "policy": args.policy,
             "severity": args.severity, "note": args.note, "status": "queued", "at": _now()}
        folder = _home() / "candidates" / c["id"]
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copy(TEMPLATES / "report.md", folder / "report.md")
        log["candidates"].append(c)
        save(log)
        return _out({"ok": True, "candidate": c, "folder": str(folder)})

    if args.cmd == "candidates":
        return _out({"candidates": [c for c in log["candidates"] if c["status"] == "queued"]})

    if args.cmd in ("promote", "discard"):
        c = next((c for c in log["candidates"] if c["id"] == args.cid and c["status"] == "queued"), None)
        if c is None:
            return _out({"ok": False, "reason": f"no queued candidate {args.cid}"}, REFUSED)
        if args.cmd == "discard":
            c.update(status="discarded", note=args.reason)
            save(log)
            return _out({"ok": True, "candidate": c})
        inv, err = _start(log, f"{c['repo']} via {c['channel']}", c["policy"])
        if err:
            return _out({"ok": False, "reason": err}, REFUSED)
        folder = _home() / inv["id"]
        shutil.copytree(_home() / "candidates" / c["id"], folder, dirs_exist_ok=True)  # draft + PoC win over blank templates
        inv.update(candidate=c["id"], hypothesis=c["title"], status="testing")
        c.update(status="promoted", investigation=inv["id"])
        save(log)
        return _out({"ok": True, "investigation": inv, "folder": str(folder)})

    if args.cmd == "start":
        inv, err = _start(log, args.program, args.policy)
        if err:
            return _out({"ok": False, "reason": err}, REFUSED)
        save(log)
        return _out({"ok": True, "investigation": inv, "folder": str(_home() / inv["id"])})

    if args.cmd == "status":
        return _out({"active": cur, "folder": str(_home() / cur["id"]) if cur else None,
                     "awaiting_triage": awaiting(log), "max_awaiting": MAX_AWAITING})

    if args.cmd == "close":
        open_ = ([cur] if cur else []) + awaiting(log)
        if args.id:
            open_ = [i for i in open_ if i["id"] == args.id]
        if len(open_) != 1:
            return _out({"ok": False, "reason": f"pass --id, one of {[i['id'] for i in open_]}" if open_
                         else "nothing open to close"}, REFUSED)
        inv = open_[0]
        inv.update(outcome=args.outcome, bounty=args.bounty, note=args.note, status="closed", closed_at=_now())
        save(log)
        return _out({"ok": True, "investigation": inv})

    if args.cmd == "metrics":
        invs = log["investigations"]
        closed = [i for i in invs if i["outcome"]]
        submitted = [i for i in invs if i["submitted_at"]]
        days = [(datetime.fromisoformat(i["closed_at"]) - datetime.fromisoformat(i["submitted_at"])).days
                for i in closed if i["submitted_at"]]
        return _out({
            "investigations": len(invs), "submitted": len(submitted),
            "by_outcome": {o: sum(i["outcome"] == o for i in closed) for o in OUTCOMES},
            "avg_triage_days": round(sum(days) / len(days), 1) if days else None,
            "bounty_total": sum(i["bounty"] for i in closed),
        })

    if not cur:
        return _out({"ok": False, "reason": "no investigation being worked on; run start or promote first"}, REFUSED)

    if args.cmd == "hypothesis":
        cur.update(hypothesis=args.text, status="testing")
    elif args.cmd == "submit":
        if not cur["hypothesis"]:
            return _out({"ok": False, "reason": "no hypothesis recorded; a report needs exactly one"}, REFUSED)
        cur.update(report_url=args.url, status="submitted", submitted_at=_now())
    save(log)
    return _out({"ok": True, "investigation": cur})


if __name__ == "__main__":
    sys.exit(main())

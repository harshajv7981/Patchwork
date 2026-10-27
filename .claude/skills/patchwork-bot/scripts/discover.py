#!/usr/bin/env python3
"""Find repos worth auditing: today's trending Python repos, the top repos by stars, and
mid-sized repos (1k-20k stars) pushed in the last week, kept only if they're
English-language and merge outsiders' PRs quickly.

  discover.py [--top N] [--mid N] [--refresh]

Prints JSON: {"eligible": [...ranked best first...], "skipped": [{repo, reason}]}.

Why receptiveness and not stars: a repo that closes most outside PRs, or takes weeks to
merge them, will ignore a bug report too, however good it is. So every candidate is
scored from its last 100 closed PRs (one GraphQL call), cached for a week in
$PATCHWORK_BOT_HOME/receptiveness.json.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import state as bot_state  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "backend"))
from app.contribution_service import is_english_text  # noqa: E402

TRENDING_URL = "https://github.com/trending/python?since=daily"
OUTSIDERS = {"CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER", "NONE"}
LIST_WORDS = re.compile(
    r"\b(list|lists|collection|curated|tutorials?|books?|interview|roadmap|awesome|"
    r"resources|course|cheatsheet|guide|learn)\b", re.I)
CACHE_DAYS = 7

# Receptiveness thresholds. Large repos get stricter speed limits: with a big backlog,
# a slow queue means an outsider's PR effectively never gets looked at.
MIN_OUTSIDER_SAMPLE = 5
MIN_MERGE_RATE = 0.40
MAX_MEDIAN_DAYS = 7
LARGE_STARS = 20_000
LARGE_MAX_MEDIAN_DAYS = 3
LARGE_MAX_BACKLOG_MONTHS = 1.5

QUERY = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    nameWithOwner stargazerCount pushedAt isFork isArchived description
    languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { totalSize edges { size node { name } } }
    openPRs: pullRequests(states: OPEN) { totalCount }
    readmeMd: object(expression: "HEAD:README.md") { ... on Blob { text } }
    readmeRst: object(expression: "HEAD:README.rst") { ... on Blob { text } }
    closed: pullRequests(states: [MERGED, CLOSED], first: 100, orderBy: {field: UPDATED_AT, direction: DESC}) {
      nodes { authorAssociation createdAt mergedAt author { login __typename } }
    }
  }
}"""


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


CJK = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af]")


def prose(markdown: str, limit: int = 3000) -> str:
    """README text with code, HTML, links, badges and URLs removed, for language detection."""
    text = re.sub(r"```.*?```|~~~.*?~~~", " ", markdown, flags=re.S)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)          # images/badges first...
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)       # ...then links (keep their text)
    text = re.sub(r"<[^>]+>|`[^`]*`|https?://\S+", " ", text)
    text = re.sub(r"[#>*_|=\-\[\]()]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


MIN_DETECT_LETTERS = 80  # langdetect is unreliable below this (it calls short English French)


def is_english_repo(description: str, readme: str) -> bool:
    """Is the repo's description + README English? Maintainers of a repo whose primary README
    is in another language mostly work in it, so an English report is a poor fit there."""
    text = f"{description}. {prose(readme)}".strip(". ")
    letters = re.findall(r"[^\W\d_]", text)
    if not letters:
        return True  # nothing to judge by; the receptiveness checks still apply
    if len(CJK.findall(text)) / len(letters) > 0.1:
        return False
    if len(letters) < MIN_DETECT_LETTERS:
        # Too short for language detection: accept Latin-script text.
        return all(ord(c) < 0x250 for c in letters)
    return is_english_text(text)


def trending() -> list[str]:
    req = urllib.request.Request(TRENDING_URL, headers={"User-Agent": "Mozilla/5.0"})
    try:
        html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    except OSError:
        return []
    return list(dict.fromkeys(re.findall(r'<h2[^>]*>\s*<a[^>]*href="/([\w.-]+/[\w.-]+)"', html)))


def search_repos(n: int, *query: str) -> list[str]:
    out = subprocess.run(
        ["gh", "search", "repos", *query, "--language=python", "--archived=false",
         f"--limit={n}", "--json", "fullName"],
        capture_output=True, text=True)
    return [r["fullName"] for r in json.loads(out.stdout or "[]")]


def fetch(repo: str) -> dict | None:
    owner, name = repo.split("/", 1)
    out = subprocess.run(["gh", "api", "graphql", "-f", f"query={QUERY}", "-F", f"owner={owner}",
                          "-F", f"name={name}"], capture_output=True, text=True)
    if out.returncode != 0:
        return None
    return json.loads(out.stdout)["data"]["repository"]


def measure(repo_data: dict, now: datetime) -> dict:
    """Turn raw repo data into the numbers the decision is based on."""
    langs = repo_data["languages"]
    total = langs["totalSize"] or 1
    python_share = sum(e["size"] for e in langs["edges"] if e["node"]["name"] == "Python") / total

    readme = (repo_data.get("readmeMd") or repo_data.get("readmeRst") or {}).get("text") or ""
    nodes = repo_data["closed"]["nodes"]

    def is_outsider(pr):
        author = pr.get("author") or {}
        return (pr["authorAssociation"] in OUTSIDERS and author.get("__typename") != "Bot"
                and not str(author.get("login", "")).endswith("[bot]"))

    outsiders = [pr for pr in nodes if is_outsider(pr)]
    merged = [pr for pr in outsiders if pr["mergedAt"]]
    days = [(_ts(pr["mergedAt"]) - _ts(pr["createdAt"])).total_seconds() / 86400 for pr in merged]
    # Lower bound on merges per month (the sample is capped at 100), so backlog is an upper bound.
    merges_30d = sum(1 for pr in nodes if pr["mergedAt"] and now - _ts(pr["mergedAt"]) <= timedelta(days=30))
    return {
        "stars": repo_data["stargazerCount"],
        "pushed_at": repo_data["pushedAt"],
        "is_fork": repo_data["isFork"],
        "is_archived": repo_data["isArchived"],
        "description": repo_data.get("description") or "",
        "english": is_english_repo(repo_data.get("description") or "", readme),
        "python_share": round(python_share, 2),
        "outsider_closed": len(outsiders),
        "outsider_merged": len(merged),
        "merge_rate": round(len(merged) / len(outsiders), 2) if outsiders else 0.0,
        "median_days": round(statistics.median(days), 1) if days else None,
        "backlog_months": round(repo_data["openPRs"]["totalCount"] / max(merges_30d, 1), 1),
    }


def assess(m: dict, now: datetime, any_speed: bool = False) -> tuple[bool, str, float]:
    """(eligible, reason, score). Pure: all inputs come from measure().
    any_speed: skip the merge-speed and backlog limits (operator chose big repos over fast ones)."""
    if m["is_fork"] or m["is_archived"]:
        return False, "fork or archived", 0.0
    if now - _ts(m["pushed_at"]) > timedelta(days=30):
        return False, "no pushes in 30 days", 0.0
    if m["python_share"] < 0.5:
        return False, f"only {m['python_share']:.0%} Python", 0.0
    if LIST_WORDS.search(m["description"]):
        return False, "looks like a list/docs repo", 0.0
    if not m.get("english", False):
        return False, "not an English-language repo (README/description)", 0.0
    if m["outsider_closed"] < MIN_OUTSIDER_SAMPLE:
        return False, f"too little outsider PR history ({m['outsider_closed']}) to judge", 0.0
    if m["merge_rate"] < MIN_MERGE_RATE:
        return False, f"merges only {m['merge_rate']:.0%} of outsider PRs", 0.0
    days = m["median_days"] if m["median_days"] is not None else 99
    if any_speed:
        return True, "receptive (speed not checked)", round(m["merge_rate"] / (1 + days), 3)
    large = m["stars"] >= LARGE_STARS
    limit = LARGE_MAX_MEDIAN_DAYS if large else MAX_MEDIAN_DAYS
    if days > limit:
        return False, f"slow: median {days}d to merge outsider PRs (limit {limit}d)", 0.0
    if large and m["backlog_months"] > LARGE_MAX_BACKLOG_MONTHS:
        return False, f"large repo with {m['backlog_months']} months of open-PR backlog", 0.0
    return True, "receptive", round(m["merge_rate"] / (1 + days), 3)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--top", type=int, default=50, help="how many top-by-stars repos to add to trending")
    p.add_argument("--mid", type=int, default=100,
                   help="how many mid-sized (1k-20k stars) repos pushed in the last week to add")
    p.add_argument("--refresh", action="store_true", help="ignore the receptiveness cache")
    p.add_argument("--min-stars", type=int, default=0,
                   help="only the top --top repos with at least this many stars; no merge-speed limits")
    args = p.parse_args(argv)

    now = datetime.now(timezone.utc)
    if args.min_stars:
        sources = {r: "top" for r in search_repos(
            args.top, f"--stars=>={args.min_stars}", "--sort=stars", "--order=desc")}
    else:
        sources = {r: "trending" for r in trending()}
        for r in search_repos(args.top, "--sort=stars", "--order=desc"):
            sources.setdefault(r, "top")
        # Mid-sized active repos: smaller backlogs, and a different set every day (top-N barely moves).
        week_ago = (now - timedelta(days=7)).date().isoformat()
        for r in search_repos(args.mid, f"pushed:>={week_ago}", "--stars=1000..20000", "--sort=updated"):
            sources.setdefault(r, "mid")

    cache_path = bot_state._home() / "receptiveness.json"
    try:
        cache = json.loads(cache_path.read_text())
    except (OSError, ValueError):
        cache = {}
    st = bot_state.load()
    eligible, skipped = [], []

    for repo, source in sources.items():
        ok, reason = bot_state.check(st, repo, new_submission=False, audit=True)
        if not ok:
            skipped.append({"repo": repo, "source": source, "reason": reason})
            continue
        hit = cache.get(repo)
        if hit and not args.refresh and "english" in hit["metrics"] and now - _ts(hit["at"]) < timedelta(days=CACHE_DAYS):
            m = hit["metrics"]
        else:
            data = fetch(repo)
            if data is None:
                skipped.append({"repo": repo, "source": source, "reason": "GitHub API lookup failed"})
                continue
            m = measure(data, now)
            cache[repo] = {"at": now.isoformat(timespec="seconds"), "metrics": m}
        good, reason, score = assess(m, now, any_speed=bool(args.min_stars))
        row = {"repo": repo, "source": source, **{k: m[k] for k in
               ("stars", "merge_rate", "median_days", "backlog_months", "outsider_closed")}}
        if good:
            eligible.append({**row, "score": score})
        else:
            skipped.append({**row, "reason": reason})

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2, sort_keys=True))
    # Trusted repos first (they get PRs directly), then by score.
    trusted = {r for r, v in st["repos"].items() if v.get("status") == "trusted"}
    eligible.sort(key=lambda r: (r["repo"] not in trusted, -r["score"]))
    print(json.dumps({"eligible": eligible, "skipped": skipped}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

---
name: patchwork-bot
description: Autonomous open-source contribution bot. Audits Python repos for real, provable bugs (and, on repos that already trust the bot, small cleanups and feature proposals), proves each bug with a failing test in a Docker sandbox, then files a bug report with a linked fix PR from the operator's own GitHub account under hard volume and etiquette limits. Run as `/patchwork-bot run`, `/patchwork-bot watch`, `/patchwork-bot audit <owner/repo>`, or `/patchwork-bot status`; add `--dry-run` to see what it would do without touching GitHub.
disable-model-invocation: true
---

# Patchwork bot

You are running an automated contributor that posts to other people's repositories from the
operator's **personal** GitHub account, so every submission carries their name and
reputation. Everything below exists to make it behave like a contributor maintainers are
glad to hear from: every submission is a *proven* problem, volume is tiny, it reports
before it pushes code, it's honest that a tool found the problem, and it backs off the
moment someone says no. One careless submission can get the operator's account flagged or
banned, so when in doubt, drop the finding — a skipped bug costs nothing, a bad report
costs the operator.

The limits (daily cap, one open item per repo, do-not-contact, follow-up rounds) live in
`scripts/state.py` and are enforced there. Never work around a refusal from it; a refusal
is the system working.

## Commands

| Command | What it does |
|---|---|
| `run` | The daily cycle: `watch` first, then discover and audit new repos until the daily cap is used. |
| `watch` | Check every open item for maintainer replies, CI results and review comments, and react. |
| `audit <owner/repo>` | Run the audit → prove → submit pipeline on one specific repo. |
| `status` | Print `state.py summary` and the open items. No GitHub writes. |

`--dry-run` on any command: do every read and every local step (clone, audit, prove,
review, draft), but make **no** GitHub writes (no fork, issue, PR, comment, push) and no
`state.py` writes. Save the drafts to `$PATCHWORK_BOT_HOME/dry-run/<timestamp>.md` and
print the path. Use it the first few times on any new setup.

## Setup and preflight (do this at the start of every command)

Paths and environment:

- `SKILL_DIR` = this skill's directory; `PW` = the Patchwork repo (four levels up from
  `scripts/`). Run scripts with `$PW/.venv/bin/python`.
- `PATCHWORK_BOT_HOME` (default `~/.patchwork-bot`) holds `state.json`,
  `receptiveness.json` (cache), `patches/`, `dry-run/`. Clones never go here (see step 1).
- If `$PATCHWORK_BOT_HOME/env` exists, source it. It should define `PATCHWORK_OPERATOR`
  (the operator's GitHub login).

Preflight, stop with a clear message if any fails:

1. **Account.** The bot uses the machine's normal `gh` login (the operator's personal
   account). `gh api user --jq .login` must return exactly `$PATCHWORK_OPERATOR`. If it
   doesn't, stop: posting from some other account that happens to be logged in would put
   the wrong person's name on the submission. `git push` goes through
   `gh auth git-credential`, so the same login is used for pushes.
2. **Sandbox.** `docker info` works and `docker image ls patchwork-sandbox` lists at least
   one `pyX.Y` tag. If none are built, build them from the Patchwork repo:
   `for v in 3.12 3.13 3.14 3.15; do docker build --build-arg PYTHON_VERSION=$v -f "$PW/Dockerfile.sandbox" -t patchwork-sandbox:py$v "$PW"; done`. Proving bugs requires running untrusted code, so no Docker means no audit
   (`watch` and `status` may still run).
3. **Commit identity.** Every commit is authored as the operator's GitHub login with their
   noreply email, so GitHub links it to their account:
   `GIT_NAME=$PATCHWORK_OPERATOR`,
   `GIT_EMAIL=$(gh api user --jq '"\(.id)+\(.login)@users.noreply.github.com"')`.
   Set both in **every** clone right after cloning (`git -C <clone> config user.name/user.email`).
   Never rely on global or Patchwork-repo config: a temp clone doesn't see the Patchwork repo's
   config, and git's fallback (Mac account name @ hostname) leaks the wrong name. Before any
   push, `git log -1 --format='%an <%ae>'` must show exactly `$GIT_NAME <$GIT_EMAIL>`.

State helper (prints JSON; exit 3 = refused by a limit):

```
# a function, not a string variable: zsh doesn't word-split "$S"
S() { "$PW/.venv/bin/python" "$SKILL_DIR/scripts/state.py" "$@"; }
SANDBOX() { "$PW/.venv/bin/python" "$SKILL_DIR/scripts/sandbox.py" "$@"; }
S check <repo> [--audit]      # may we open a new item? --audit also checks the 14-day cool-down
S audited <repo>              # start the cool-down after auditing a repo
S seen|drop --repo --kind --file --title [--reason]   # drop = never revisit (false positive, duplicate, fixed)
S defer --repo --kind --file --title [--line --confidence --note]  # good finding, not now
S deferred [<repo>]            # the backlog; submitting or dropping a finding clears it
S add --repo --kind --file --title --url --type issue|pr --number N [--branch]
S update <id> [--status S] [--pr-url U --pr-number N] [--inc review|ci]
S mark <repo> new|trusted|dnc [--reason]
S open | repo <repo> | summary
```

Sandbox helper (runs Patchwork's hardened Docker sandbox on a throwaway copy):

```
SANDBOX <checkout> [--changed F ...] [--tests T ...]
# exit 0 = passed, 1 = failed, 2 = setup error (deps couldn't be installed)
```

## The `run` cycle

1. `watch` (below). Answering maintainers who already engaged matters more than new work.
2. If `S summary` shows the daily cap is used, stop and report.
3. **Discover**: `"$PW/.venv/bin/python" "$SKILL_DIR/scripts/discover.py"`. It combines
   today's GitHub trending Python repos, the top 50 by stars, and 100 mid-sized repos
   (1k–20k stars) pushed in the last week (`--top`/`--mid` change the counts), drops forks, inactive
   repos, list/docs repos, repos under 50% Python, and anything `state.py` blocks
   (do-not-contact, open item, audit cool-down). It keeps **English-language repos only**
   (description + README judged together; a README that's more than 10% CJK, or that
   language detection says isn't English, is skipped): maintainers of a repo whose primary
   README is in another language mostly work in it, so an English report is a poor fit.
   Then it keeps only repos that are **receptive**, judged from their last 100 closed PRs:
   - at least 5 PRs from outside contributors to judge by (bots and maintainers excluded)
   - at least 40% of outsider PRs merged
   - median time to merge an outsider PR ≤ 7 days, or ≤ 3 days and ≤ 1.5 months of
     open-PR backlog for large repos (20k+ stars)

   Slow or closed repos are skipped: a repo that ignores outside PRs will ignore a bug
   report too. Work down `eligible` in order (trusted repos come first, then by score).
   Many will still be skipped at step 1 (CLA, AI policy) or step 2 (test suite won't run in
   the sandbox); that's expected and cheap.
4. Audit up to **3 repos per run** (it's expensive) with the pipeline below, stopping as
   soon as the daily cap is reached.
5. Report (see "Run report").

## Audit pipeline (one repo)

### 1. Clone and read the room

Clone into a fresh temp directory, never into a fixed path:
`WORK=$(mktemp -d "${TMPDIR:-/tmp}/patchwork-bot.XXXXXX") && git clone --depth 50 <url> "$WORK/repo" && git -C "$WORK/repo" config user.name "$GIT_NAME" && git -C "$WORK/repo" config user.email "$GIT_EMAIL"`.
Delete `$WORK` as soon as the repo is finished, whether it ended in a submission, a skip or
an error. Each shell call is separate, so a `trap` won't survive a crash; instead, every
command starts by sweeping leftovers from crashed runs:
`find "${TMPDIR:-/tmp}" -maxdepth 1 -name 'patchwork-bot.*' -mmin +360 -exec rm -rf {} +`.
Read `README*`, `CONTRIBUTING*`, `CODE_OF_CONDUCT*`, any `AI_POLICY*`, and `.github/`
templates. Then grep these and the docs for `AI`, `LLM`, `ChatGPT`, `Copilot`,
`generated`, `bot`, `CLA`.

Mark the repo `dnc` with a reason and stop if any of these apply:

- it prohibits or discourages AI-generated or automated contributions
- it requires a CLA (a bot can't meaningfully sign one)
- it says it doesn't accept outside contributions

If it asks for an issue before any PR, note it; untrusted repos get an issue first anyway.
Run `S audited <repo>` once you've gone past this step, even if nothing is found later.

### 2. Baseline

Prove the sandbox can run this repo's tests before auditing anything. Don't run the whole
suite: big projects have thousands of test files and it would take hours. Pick one or
two small test files from the area you're about to audit and run
`SANDBOX <checkout> --tests <files>`. `sandbox.py` picks the Docker image matching the
repo's `requires-python` (stepping down to older Pythons if the dependencies won't install on the newest).
Exit 2 (setup error), or a run that collects zero tests → the bot can't prove anything
here; stop (no dnc, it may work after the repo changes). Note any of those tests that
already fail; they're pre-existing and not the bot's to fix.

### 3. Audit with fresh eyes

**Start from the backlog.** If `S deferred <repo>` lists findings, take them first, in
confidence order: re-check each against the current code (it may have been fixed), then
run it through dedupe (step 4) and prove (step 5) as if it were new. Only run the lenses
below if none of the deferred findings survive.

Check trust with `S repo <repo>`. Spawn the lenses as **parallel subagents** (Agent
tool), each told the repo path and its lens. Subagents read cold, which is the point: no
shared assumptions.

- **Bug hunter (always).** Find defects reachable through the public API: wrong results,
  crashes on valid input, broken edge cases (empty, None, unicode, boundaries), resource
  leaks, error handling that loses data, security bugs. For each finding give: `file:line`,
  the triggering input, expected vs. actual behaviour, why it happens, and confidence
  high/medium. Exclude style, typing nits, performance guesses, "might" bugs, and anything
  that needs network or credentials to reproduce. Five real findings beat twenty plausible
  ones.
- **Ponytail (trusted repos only).** Behaviour-preserving simplifications in the spirit of
  `$PW/CLAUDE.md`: dead code, duplicated logic, reimplemented stdlib, needless
  abstraction. Each must be small (one concern, under ~50 lines changed) and backed by
  existing test coverage.
- **Feature scout (trusted repos only).** Small, clearly-scoped gaps a user of the library
  would hit: a missing parameter, an unhandled common case, a documented-but-missing
  behaviour. Each needs a concrete use case.

Untrusted repos get the bug lens only. Unsolicited cleanups and features from a stranger
are the contributions maintainers resent most.

### 4. Dedupe

For each finding: if `S seen ...` says seen, skip it. Otherwise search open and closed
issues and PRs (`gh search issues --repo <repo> --include-prs "<key terms>"`, plus the
file and function names). Already reported, being fixed, or previously rejected →
`S drop` with the reason.

### 5. Prove (this is what makes the bot trustworthy)

**Bugs.** Write a minimal regression test in the repo's existing test style and location.
It must fail on the untouched code **for the reason claimed**: an assertion about the
wrong behaviour, not an import error, a typo or a setup failure. Run
`SANDBOX <checkout-with-test> --tests <test>`. If it doesn't fail that way, the bug
isn't real: `S drop --reason "not reproducible"`.

Then write the **smallest** fix that makes it pass. Follow the repo's conventions over
your own taste. Run `SANDBOX <checkout-with-fix> --changed <files> --tests <test>`
(must pass), then the tests that cover the changed code: the test files for the changed
module and its package's test directory, not the whole suite. Nothing that passed before
the fix may fail after it. If it isn't
green after 3 attempts at the fix, drop it; a fix the bot can't get right isn't one to
send.

**Ponytail.** The tests covering the changed code must be identical before and after (same tests pass), and
the diff must not change any public behaviour.

**Features.** There's nothing to prove. Draft a proposal issue only: the problem, the use
case, and a sketch of the API. No code goes upstream unless a maintainer asks.

### 6. Cold review

Spawn a fresh subagent that has seen none of the above. Give it the finding, the test,
the diff and the sandbox output, and ask: Is this a real bug that users would hit? Does
the test reproduce it for the right reason? Is the fix minimal and correct, with no
behaviour change elsewhere? Would a busy maintainer merge it? It must answer
`PASS / REVISE / BLOCK` with a reason. Only `PASS` proceeds, at any confidence level:
the proof step already established that the bug is real, so a medium-confidence PASS
(usually "correct but small impact") is still worth submitting. Mention the reviewer's
caveats in the submission if they matter to a maintainer. Act on one `REVISE` if the
fix is quick and review again; anything else, drop it.

### 7. Rank and pick

Rank the surviving findings by impact × confidence × smallness. Submit the top one (and
another only if the cap allows and it's from a different repo; the one-open-item-per-repo
rule means a second finding in the same repo waits for a later run). **Defer** the other
proven-or-plausible findings with `S defer ...` (include confidence and a short note) so
the next audit of this repo starts from them. Don't `drop` them: `drop` means "never look
at this again" and is only for false positives, duplicates and things already fixed.

### 8. Submit

Run `S check <repo>` immediately before any write; if it refuses, stop.

Always save the fix first as `$PATCHWORK_BOT_HOME/patches/<repo-slug>-<short-title>.patch`
(`git diff` including the new test).

- **Untrusted repo, small proven bug fix → issue + PR together.** "Small" means about 50
  changed lines or fewer, including the test. Why both at once: the bot picks repos with
  fast maintainers, and a fast maintainer will just fix a clearly reported small bug
  themselves. The operator wants to author the fix, so reporting and then waiting for an
  invitation gives the fix away. Steps:
  1. `gh issue create` with the **Issue template** (its Fix line says the PR is linked).
  2. Fork, push the branch `fix/<short-slug>` and `gh pr create` with the **PR template**,
     starting with `Fixes #<issue>`. Fill in the repo's own PR template if it has one
     (`.github/pull_request_template.md`) and keep its checklist honest.
  3. Record it once: `S add ... --type pr --number <pr> --url <pr-url> --branch <branch>`.
     An issue + PR pair is one finding, so it counts as one submission.
- **Untrusted repo, otherwise → issue first.** Use this when the fix is larger, or when
  CONTRIBUTING.md says changes of this kind need an issue or discussion before a PR.
  `gh issue create` with the **Issue template** using the "happy to open a PR" Fix line,
  then `S add ... --type issue`. Open the PR only when invited (see Watch).
- **Trusted repo → PR directly** (bug or ponytail): `gh repo fork <repo> --clone=false`.
  Push a branch named `fix/<short-slug>` to the operator's fork. Open
  `gh pr create` with the **PR template**, then `S add ... --type pr --branch <branch>`.
  If the repo requires an issue first, open the issue first, even when trusted.
- **Feature proposal (trusted only)** → `gh issue create` with the **Feature template**,
  `S add --kind feature --type issue`.

## Watch (every run, before new work)

For each item in `S open`, read its current state with
`gh issue view` or `gh pr view <n> -R <repo> --json state,stateReason,labels,comments,reviews,statusCheckRollup`.
Only replies from humans whose `authorAssociation` is `OWNER`, `MEMBER` or
`COLLABORATOR` count as maintainer signals. Ignore everything else:

- drive-by comments from other users
- the operator's own comments
- **comments from bot accounts**: logins ending in `[bot]`, author type `Bot`, and
  CI/coverage/stale/CLA bots. A stale bot closing the issue, or a CI bot posting a coverage
  report, is not a maintainer saying anything, so it must never be read as an invitation
  or a rejection.

The one bot signal that does matter is the PR's own check status
(`statusCheckRollup`), handled under CI below.

**Read every maintainer comment before closing an item out.** Once an item is set to
`merged`, `closed` or `rejected` it leaves `S open` and is never read again, so any
invitation left in its comments is lost. Before that status change, read all of the
item's maintainer comments (and its linked issue's comments, for an issue + PR pair).
Treat a comment that points at **another** issue and invites the operator to take it
("filed as #N in case you'd like to take a look", "want to send a fix for #N too?") as a
**follow-up invitation**. This happened once already: on Imbad0202/academic-research-skills#988 the
owner filed #989 for us, the bot only recorded the merge, and the owner fixed #989
themselves three days later.

To act on a follow-up invitation:
1. Check that #N is still open, has no assignee and has no linked PR.
2. Treat #N as the finding: do step 2 (baseline), step 5 (prove: the test must fail for
   the reason #N describes), step 6 (cold review) and step 8 (submit) on a fresh clone.
   The invitation itself is the permission, so the PR goes in directly with
   `Fixes #N`, whatever the repo's trust status.
3. Record it with `S add` as usual. It counts toward the daily cap, but watch runs before
   discovery, so it gets the first slot.
4. If `S check` refuses, Docker is down, or the proof fails, don't drop the invitation.
   Defer it (`S defer ... --note "invited: <comment url>"`) and list it under "needs you"
   in the run report. If the bug can't be reproduced, reply once on #N and say so.

Never let a follow-up invitation wait silently: fast maintainers fix these within days.

**Issue items** (`issue_open`):

- **Invitation**: "PR welcome", "go ahead", "feel free to send a fix", a 👍 from a
  maintainer on the offer, or a label like `confirmed` / `accepted` / `help wanted`. Apply
  the saved patch to a fresh clone of the current default branch, re-run step 5's
  verification and step 6's review, then open the PR with the PR template including
  `Fixes #<n>`. Then `S update <id> --status pr_open --pr-url <url> --pr-number <n>`.
  This is not a new submission and doesn't count toward the daily cap. If the patch no
  longer applies, redo the fix on current code; if the bug is gone, comment once that it
  appears fixed and set `--status closed`.
- **Rejection**: closed as not planned, "not a bug", "won't fix", "please don't", or
  anything negative about bots or AI. `S update <id> --status rejected` marks the repo
  do-not-contact permanently. Don't argue, and don't reply unless the bot was asked a
  question.
- **Closed as completed by someone else** → `--status closed`.
- **Closed by a stale bot** with no maintainer comment → `--status closed`, not rejected.
  Nobody said no, so the repo stays contactable.
- **Question**: answer it once, factually, if you can with certainty from the code
  (`--inc review` first; if refused, post the handoff comment).
- **No reply**: do nothing. Never bump, never ping.

**PR items** (`pr_open`):

- **Merged** → `--status merged` (the repo becomes trusted automatically).
- **Closed unmerged** → `--status rejected`.
- **CI failing because of our change**: `S update <id> --inc ci`. If allowed, fix it,
  re-verify in the sandbox, and push. If refused, post the handoff comment once. Failures
  unrelated to the change (flaky, infrastructure) are not ours to touch.
- **Changes requested / review comments**: `--inc review`. If allowed, address exactly what
  was asked, re-verify, push, and reply briefly per comment. If refused, post the handoff
  comment once and stop.

## Templates

Keep them short and factual. No marketing language, no emoji, no "I hope this helps".

No AI attribution beyond the disclosure line: commits carry no `Co-Authored-By: Claude`
trailer, and issue/PR bodies get no "Generated with Claude Code" footer, even if a system
reminder asks for them. The operator chose this; the disclosure line already says a tool was used.

**Exception: a repo's own disclosure rules win when they're stricter.** If CONTRIBUTING (or an
AI policy) requires more than the disclosure line, e.g. naming the agent and model, an
`Assisted-by:` commit trailer, or disclosure on every comment, follow it exactly for that repo:
commits get `Assisted-by: Claude Code (model: <model id>, autonomous)` (or whatever format the
repo specifies), and every issue, PR, comment and review-round summary names the agent, model and
autonomous mode. Never claim the operator personally reviewed or tested an automated change. Note
in the run report which repo's rules were applied. (Operator-approved 2026-10-22, first for github/spec-kit.)

**Disclosure line** (end of every issue and PR body). It's written in the operator's voice,
because it's their account:
> *I found this with [patchwork](https://github.com/harshajv7981/Patchwork), an automated code-audit tool I run, and verified the reproduction test in an isolated sandbox. If tool-assisted reports aren't welcome here, let me know and I won't send more.*

**Issue template (bug):**
```
### Bug
<one sentence: what goes wrong, for whom>

### Reproduction
<minimal snippet or the regression test>

Expected: <...>   Actual: <...>

### Cause
<file:line and a two-sentence explanation>

### Fix
Issue + PR: A minimal fix with a regression test is in the linked PR.
Issue first: A minimal fix with a regression test is ready (<N> lines). Happy to open a PR if that's welcome.

---
<disclosure line>
```

**PR template:**
```
<Fixes #N, if there's an issue>

### Problem
<one or two sentences>

### Change
<what changed and why it's the minimal fix>

### Verification
- New regression test `<path::name>` fails before this change and passes after.
- Full test suite: <X passed>, no new failures.

---
<disclosure line>
```

**Feature template:** Problem / Use case / Proposed API sketch / Willing to implement if
wanted / disclosure line.

**Handoff comment** (when the review/CI round limit is hit):
> Thanks for the review. I'll follow up on this one by hand.

Also flag the item in the run report under "needs you", so the operator actually does.

## Scheduling

`scripts/scheduled_run.sh [run|watch|status]` runs the skill headless
(`claude -p "/patchwork-bot run"` with pre-approved tools) and logs to
`~/.patchwork-bot/logs/run-<timestamp>.log`, keeping the last 60. On macOS it's driven by
a launchd job, `~/Library/LaunchAgents/local.patchwork-bot.plist`, at 10:00 daily (a
missed run fires on wake). That wake is often a network-less dark wake, so the script
waits up to 8 hours for the Anthropic and GitHub APIs to be reachable before starting
`claude`, and keeps the Mac awake during the run with `caffeinate -i`.

- Run now: `launchctl kickstart gui/$(id -u)/local.patchwork-bot`
- Pause: `launchctl bootout gui/$(id -u)/local.patchwork-bot`
- Resume: `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/local.patchwork-bot.plist`

Docker Desktop must be running for audits; if it isn't, the preflight still lets `watch`
answer maintainers and the run report says why no audit happened.

## Run report

End every command with a short report:

- items watched and what changed (invitations, merges, rejections)
- repos audited (and those skipped, with the reason)
- findings proven / dropped (with the reasons, briefly)
- submissions made (with links), or the dry-run file path
- **needs you**: items where a follow-up limit was hit, or a maintainer asked something the
  bot couldn't answer with certainty. Link each one.
- the `S summary` line

If anything surprised you (a policy you weren't sure about, a sandbox oddity), say so in
the report rather than guessing. The operator reads these.

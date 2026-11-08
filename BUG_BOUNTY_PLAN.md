# Bug Bounty Research Plan

This plan is intentionally slow: one investigation worked on at a time, at most 3 reports awaiting triage. The goal is to produce strong, reproducible reports and build researcher reputation without mass submissions.

## Operating Rule

Only work on one active investigation at a time:

1. Choose one authorized bug bounty or vulnerability disclosure program.
2. Read its current scope, exclusions, safe-harbor terms, and testing rules.
3. Choose one vulnerability hypothesis.
4. Test only with an account and data you control.
5. Create the smallest proof of concept that demonstrates real impact.
6. Submit one report.
7. Start the next investigation if fewer than 3 reports await triage; otherwise pause until one is triaged.
8. Record the outcome: accepted, duplicate, informative, out of scope, or rejected.
9. Close each report with its outcome as soon as triage answers; that frees a slot.

Do not scan many programs, submit batches of findings, or automate external security testing without explicit authorization.

## Recommended Starting Programs

### Microsoft Copilot

The Microsoft Copilot Bounty Program is a strong starting point for AI and agent-security research. Its published program page lists qualifying rewards from $100 to $30,000 USD.

- Program: <https://www.microsoft.com/en-us/msrc/bounty-ai>
- Submit through the MSRC Researcher Portal.
- Use a personal test account.
- Include the conversation ID when required.
- Reports must be reproducible on the latest version and demonstrate security impact.

Potentially relevant categories include authentication, improper access control, code injection, SSRF, information disclosure, and certain inference-manipulation issues.

Prompt leakage alone, harmless jailbreaks, hallucinations, denial of service, and issues affecting only the researcher are commonly excluded. Check the current policy before every test.

### Other Research Channels

Use these for discovery and comparison, but always follow the individual program policy:

- HackerOne: <https://hackerone.com/opportunities/all>
- Bugcrowd: <https://www.bugcrowd.com/bug-bounty-list/>
- Google Bug Hunters: <https://bughunters.google.com/>
- Anthropic Responsible Disclosure: <https://www.anthropic.com/responsible-disclosure-policy>

A vulnerability disclosure program does not necessarily offer payment. Confirm the reward terms before investing time.

## Patchwork's Role

Patchwork should assist with local research preparation, not mass-submit security reports.

Useful capabilities include:

- Auditing authorization boundaries in FastAPI routes.
- Tracing approval-gated actions and possible bypasses.
- Checking secret scrubbing and sandbox isolation.
- Reviewing repository-controlled input flowing into tools or subprocesses.
- Generating small local regression tests.
- Organizing evidence and reviewing report quality.

Promising areas in this codebase include:

- `backend/app/agent_routes.py`
- `backend/app/sandbox_routes.py`
- `backend/app/sandbox_service.py`
- `backend/app/agent_tools.py`
- `backend/app/github_service.py`

All external testing and report submission must remain human-approved. Keep Docker isolation, credential scrubbing, approval gates, rate limits, and low submission volume enabled.

## Research Workflow

### 1. Scope Check

Before testing, record:

- Program name and policy URL.
- In-scope products, domains, versions, and accounts.
- Explicitly excluded vulnerability classes.
- Permitted traffic volume and tooling.
- Disclosure and safe-harbor requirements.
- Reward eligibility and duplicate-report rules.

If scope is unclear, ask the program before testing.

### 2. Hypothesis

Write one sentence describing the suspected security property that may be broken.

Examples:

- "A user may access another user's conversation by changing an object identifier."
- "An approval-gated tool may execute an action before approval is recorded."
- "A repository-controlled value may reach a privileged subprocess without validation."

Do not investigate multiple unrelated theories in the same report.

### 3. Minimal Verification

Use the least invasive test that can confirm or reject the hypothesis:

- Use only your own accounts and test data.
- Avoid accessing or retaining other users' information.
- Do not attempt destructive actions.
- Do not evade rate limits or create service load.
- Stop once the impact is demonstrated.
- Remove secrets and personal data from all evidence.

A failed hypothesis is useful. Record it and move on later rather than forcing a report.

### 4. Report Preparation

Every report should contain:

- Clear vulnerability title.
- Affected product, endpoint, feature, version, or conversation ID.
- Preconditions and account type.
- Exact reproduction steps.
- Minimal proof of concept.
- Expected behavior.
- Actual behavior.
- Security impact tied to users or the service.
- Sanitized screenshots, requests, responses, or logs.
- Suggested remediation.
- Disclosure intentions, if requested by the program.

Avoid unsupported claims such as "this may lead to RCE." Describe only the impact that was actually demonstrated.

## Report Template

The template lives in `.claude/skills/bug-bounty/templates/report.md`; `/bug-bounty start` copies it, with `scope.md` and `notes.md`, into each investigation folder under `~/.bug-bounty/`.

## 30/60/90-Day Progression

### Days 1-30: Foundation

- Create researcher accounts on the relevant platforms.
- Read one complete program policy before testing.
- Practice API authorization, OAuth, Docker, webhooks, and LLM tool security in a local lab.
- Write sample reports without submitting speculative findings.
- Keep a research log of hypotheses and rejected ideas.

### Days 31-60: Focused Research

- Work on one authorized program.
- Investigate one hypothesis at a time.
- Focus on authorization, access control, tool execution, SSRF, and information disclosure.
- Submit only a report with reproducible security impact.
- Keep at most 3 reports awaiting triage at once.

### Days 61-90: Specialization

- Choose one niche, such as AI agent security or API authorization.
- Build local test harnesses and evidence templates.
- Improve reports based on triage feedback.
- Increase activity only after establishing a record of accurate reports.
- Publish sanitized write-ups only when the program permits disclosure.

## Success Metrics

Track quality rather than volume:

- Reports submitted.
- Reports accepted.
- Duplicate rate.
- Out-of-scope rate.
- Average triage time.
- Bounty or recognition earned.
- Maintainer or program feedback.
- Reusable research tools created.

The first milestone is one well-written, in-scope, reproducible report. A single accepted report is more valuable than many speculative submissions.

## References

- Microsoft Copilot Bounty: <https://www.microsoft.com/en-us/msrc/bounty-ai>
- Anthropic Responsible Disclosure: <https://www.anthropic.com/responsible-disclosure-policy>
- GitHub Security Advisories: <https://docs.github.com/en/code-security/security-advisories/working-with-repository-security-advisories/about-repository-security-advisories>
- HackerOne Opportunities: <https://hackerone.com/opportunities/all>
- Bugcrowd Program Directory: <https://www.bugcrowd.com/bug-bounty-list/>

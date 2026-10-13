# GitHub Repository Administration Gate

Repository files alone cannot enforce GitHub branch protection or repository-level security settings. This gate must be applied through a GitHub identity with **Administration** permission.

## Automated operator path

The repository includes an idempotent helper:

```bash
python3 scripts/github_admin.py \
  --repo OWNER/REPOSITORY \
  --branch DEFAULT_BRANCH \
  --required-check "EXACT_CHECK_NAME"
```

The target repository, branch, and required-check names are explicit; the helper has no hard-coded repository or status checks. Replace every placeholder with values read from the target repository's settings and Actions checks. Repeat `--required-check` for every required context. A dry-run does not require `gh` authentication.

Apply and immediately verify:

```bash
python3 scripts/github_admin.py \
  --repo OWNER/REPOSITORY \
  --branch DEFAULT_BRANCH \
  --required-check "EXACT_CHECK_NAME" \
  --apply
```

Verify without mutation:

```bash
python3 scripts/github_admin.py \
  --repo OWNER/REPOSITORY \
  --branch DEFAULT_BRANCH \
  --required-check "EXACT_CHECK_NAME" \
  --verify
```

Requirements:

- GitHub CLI (`gh`)
- `gh auth login`
- repository Administration permission

## Enforced policy

The helper configures the explicitly supplied branch to require:

- pull requests before merge;
- at least one approving review;
- stale-review dismissal;
- CODEOWNERS approval;
- approval after the latest push;
- conversation resolution;
- strict/up-to-date required status checks;
- each exact status-check name supplied with `--required-check`;
- administrator enforcement;
- no force pushes;
- no branch deletion.

It also enables or verifies:

- Dependabot vulnerability alerts;
- automated security fixes;
- private vulnerability reporting;
- secret scanning;
- secret scanning push protection;
- read-only default Actions `GITHUB_TOKEN` permission;
- Actions cannot approve pull requests.

## Evidence rule

A successful script run is operational evidence only when the final verification step reads the effective settings back from GitHub and exits successfully.

Do not close the production-readiness gate from the presence of this script alone.

If GitHub does not expose a requested security feature for the repository plan or ownership model, classify that control according to `ZEAZ-INTRODUCTION.md` rather than silently treating it as enabled.

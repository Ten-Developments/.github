# Ten-Developments `.github` Repository

This repository is a **special org-level configuration repository** for the [Ten-Developments](https://github.com/Ten-Developments) GitHub organization. GitHub automatically recognizes a public repo named `.github` at the org level and uses it for:

- The organization profile README
- **Reusable workflows** callable by any other repo in the org

This repo currently hosts one reusable workflow: **`freeze-check.yml`** — the implementation of the enterprise branch freeze policy (task TEN-TR01_00001).

---

## What is the Branch Freeze Policy?

A branch freeze prevents PR merges to `main` and `develop` on **weekends** and **US federal holidays**. The policy is enforced by an **Org Ruleset** that requires the `freeze-check` status check to pass before any merge.

### Frozen days

| Day type | Days |
|----------|------|
| Weekends | Saturday, Sunday |
| Federal holidays | New Year's Day (Jan 1) |
|  | Independence Day (Jul 4) |
|  | Labor Day (first Monday in September) |
|  | Thanksgiving (fourth Thursday in November) |
|  | Day after Thanksgiving (fourth Friday in November) |
|  | Christmas Eve (Dec 24) |
|  | Christmas (Dec 25) |
|  | New Year's Eve (Dec 31) |

Holidays are **auto-calculated** by the workflow each year. No manual YAML edits are required to add the next year's holidays.

### Timezone

Default: **`America/Los_Angeles`**. Configurable per consumer repo via the `timezone` input.

---

## Reusable Workflow: `freeze-check.yml`

Path: `.github/workflows/freeze-check.yml`

- **Trigger:** `workflow_call` (callable from any consumer repo)
- **Job name:** `freeze-check` (this exact name is the required status check in the Org Ruleset)
- **Inputs:** `timezone` (string, default `America/Los_Angeles`)
- **Behavior:** Exits 0 on non-frozen days, exits 1 on frozen days

### Calling this workflow from a consumer repo

```yaml
# .github/workflows/merge-freeze.yml
name: Merge Freeze Check
on:
  pull_request:
    types: [opened, reopened, synchronize, ready_for_review]
  schedule:
    - cron: "*/30 * * * *"   # re-evaluate open PRs every 30 min
jobs:
  freeze:
    uses: Ten-Developments/.github/.github/workflows/freeze-check.yml@main
    with:
      timezone: "America/Los_Angeles"
```

> **Important:** The job name (`freeze-check`) and the reusable workflow path must not change. The Org Ruleset references this exact name as a required status check.

---

## Org Ruleset: "Branch Freeze Policy"

| Field | Value |
|-------|-------|
| Name | `Branch Freeze Policy` |
| Enforcement | `active` |
| Target branches | `main`, `develop` |
| Target repositories | All |
| Required status check | `freeze-check` |
| Bypass list | `Organization Admin` role |

To view or edit: `https://github.com/organizations/Ten-Developments/settings/rules`

---

## Adding the Freeze to a New Repo

1. Create a file `.github/workflows/merge-freeze.yml` in the new repo with the snippet above
2. Commit to the default branch
3. The freeze starts working on the next PR or cron tick — no further action needed
4. The Org Ruleset will block merges to `main`/`develop` during frozen days automatically

## Updating the Freeze Policy

The freeze policy lives in **one file**: `.github/workflows/freeze-check.yml`. To change the rules:

1. Edit the file in a feature branch
2. Test the date math locally (extract the Bash logic and run it)
3. Open a PR to `main` of this repo
4. Merge
5. All consumer repos inherit the new logic on the next PR event or cron tick

## Emergency Bypass

Org admins can bypass the freeze for true emergencies:

1. Open the PR that needs to be merged
2. Click the **"Merge with bypass"** option (available because `Organization Admin` is in the bypass list)
3. Provide a justification in the PR description
4. Bypass events are logged in the [org audit log](https://github.com/organizations/Ten-Developments/settings/audit-log)

---

## Files in this repo

```
.github/
├── README.md                                  ← this file
└── .github/
    └── workflows/
        ├── freeze-check.yml                   ← the reusable workflow (single source of truth)
        └── merge-freeze.yml                   ← the caller workflow template (for copy-paste into consumer repos)
```

> **Note:** Yes, the path is `ten-github-org/.github/.github/workflows/...` — the first `.github` is the repo name, the second `.github` is GitHub's required directory for workflow files.

---

## References

- Task: **TEN-TR01_00001** — Branch freeze lock enterprise level to repos
- [GitHub: Reusable workflows](https://docs.github.com/en/actions/sharing-automations/reusing-workflows)
- [GitHub: Org-level .github repository](https://docs.github.com/en/organizations/collaborating-with-groups-in-organizations/customizing-your-organizations-profile#adding-a-public-organization-profile-readme)
- [GitHub: Rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)

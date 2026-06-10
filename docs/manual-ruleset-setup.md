# Manual Setup Guide: Org Ruleset (Branch Freeze Policy)

This guide explains how to create the **Branch Freeze Policy** Org Ruleset using the GitHub web UI.

If you'd rather use the API, see `scripts/create_org_ruleset.py` in this repo.

## Prerequisites

- You must be an **Organization Admin** or **Owner** of the `Ten-Developments` org
- All consumer repos must already have the `merge-freeze.yml` caller workflow on their default branch
- Task: **TEN-TR01_00001** — Branch freeze lock enterprise level to repos

## Steps

### 1. Open the Org Rulesets settings page

Go to: **https://github.com/organizations/Ten-Developments/settings/rules**

### 2. Create a new ruleset

Click **"New ruleset"** → **"New branch ruleset"**

### 3. Configure the ruleset

#### Ruleset name
```
Branch Freeze Policy
```

#### Enforcement status
- [x] **Active** (selected)

#### Target branches
- **Branch targeting pattern**: `main`, `develop`
- **Include default branch**: ✅ checked (catches repos whose default branch isn't `main`)
- **Include all branches**: ❌ unchecked

#### Target repositories
- [x] **All repositories** (selected)

### 4. Configure required status checks

Scroll to **"Require status checks to pass before merging"** → toggle ON

Click **"Add status check"** and enter:
- **Status check name**: `freeze-check`
  - ⚠️ This MUST match the job name in the reusable workflow exactly. The job is defined at `Ten-Developments/.github/.github/workflows/freeze-check.yml` and is named `freeze-check`.

#### Optional: Strict status checks
- ❌ Leave "Require branches to be up to date" UNCHECKED
- Rationale: The freeze-check job is a pure function of the current date and timezone, not of the PR's branch state. Requiring up-to-date would cause unnecessary churn.

### 5. (Optional) Configure additional rules

You can also enable (recommended for hygiene):
- ✅ **Require linear history** — prevents merge commits, keeps history clean
- ✅ **Require signed commits** — adds cryptographic verification (if your team uses signed commits)
- ✅ **Block force pushes** — prevents rewriting history
- ❌ **Require pull request reviews before merging** — leave OFF, the freeze is a separate concern from code review
- ❌ **Require conversation resolution** — leave OFF, separate concern

### 6. Configure bypass actors (CRITICAL)

Scroll to **"Bypass list"** → **"Add bypass"**

Add:
- **Actor type**: `Roles`
- **Role**: `Organization Admin`

This is what allows org admins to merge critical hotfixes during a freeze.

### 7. Save the ruleset

Click **"Create"** at the bottom of the page.

## Verification

After saving, the ruleset should appear in the list at `https://github.com/organizations/Ten-Developments/settings/rules` with:

- ✅ Name: "Branch Freeze Policy"
- ✅ Status: Active
- ✅ Targets: main, develop on all repos
- ✅ Required checks: freeze-check
- ✅ Bypass: Organization Admin

## Testing

To test the ruleset:

1. **Pick a consumer repo** (e.g., `atlas-api`)
2. **Create a test PR** that targets `main` or `develop`
3. **Verify**:
   - The PR shows a `freeze-check` status check
   - The merge button is greyed out
   - The status of the check is "Expected" (it hasn't run yet)
4. **Wait** for the check to complete (should take <30 seconds)
5. **Verify** on a non-frozen day: the check passes, merge is allowed
6. **Verify** on a frozen day (or by adding today to the holiday list temporarily): the check fails, merge is blocked

## Bypass test

1. As an org admin, attempt to merge a PR that has `freeze-check` failing
2. Click the **"Merge with bypass"** option (visible only to bypass actors)
3. Provide a justification in the PR description
4. Verify the merge succeeds
5. Verify the bypass event appears in the org audit log: https://github.com/organizations/Ten-Developments/settings/audit-log

## Rollback

To disable the freeze policy:

**Option A: Disable enforcement** (preserves the configuration for re-enabling)
- Go to the ruleset → click "..." → "Disable"

**Option B: Delete the ruleset** (irreversible without re-creating)
- Go to the ruleset → click "..." → "Delete"
- Or via API: `gh auth refresh -h github.com -s admin:org && python scripts/create_org_ruleset.py --delete`

**Option C: Edit the freeze logic** (reversible, preserves the ruleset)
- Edit `.github/workflows/freeze-check.yml` in this repo
- All consumer repos inherit the change on the next PR event or cron tick

## References

- [GitHub Docs: Managing rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)
- [GitHub Docs: Bypass policies for rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/using-bypass-policies-for-pull-request-approvals)
- Task: **TEN-TR01_00001** — Branch freeze lock enterprise level to repos

# Ten-Developments `.github` Repository

This repository is a **special org-level configuration repository** for the [Ten-Developments](https://github.com/Ten-Developments) GitHub organization. GitHub automatically recognizes a public repo named `.github` at the org level and uses it for:

- The organization profile README
- **Reusable workflows** callable by any other repo in the org

This repo currently hosts one reusable workflow: **`freeze-check.yml`** — the implementation of the enterprise branch freeze policy (task TEN-TR01_00001).

---

## What is the Branch Freeze Policy?

A branch freeze prevents PR merges on weekends, on US **and** Mexican federal
holidays, and on any ad-hoc dates declared org-wide. The policy is enforced by
an **Org Ruleset** that requires the `freeze-check` status check to pass before
a merge.

> **Which branches are actually frozen: `main` only.**
> The ruleset requires `freeze-check` on `main`. It is **not** required on
> `develop` — verified 2026-10-08 across TenPlatform, core, hydrology,
> atlas-api and geostream; `develop` requires only each repo's own CI.
> So **merges into `develop` proceed normally on frozen days.** This README
> previously claimed both branches were covered, which was wrong and is the
> kind of thing that is only discovered by someone merging during a freeze.
> Check it yourself for any repo — this needs only `repo` scope, not `admin:org`:
> ```bash
> gh api repos/Ten-Developments/<repo>/rules/branches/main \
>   --jq '[.[]|select(.type=="required_status_checks").parameters.required_status_checks[]?.context]'
> ```

### Frozen days

**Weekends** — Friday, Saturday and Sunday by default. Friday is included
because `friday_is_weekend` defaults to `true`; set it to `false` in a consumer
repo to free Fridays there.

**Holidays** — both calendars are on by default (`holiday_calendars:
"us_federal,mexico_federal"`). Pass a subset to enforce only one.

| Calendar | Fixed dates | Floating dates |
|---|---|---|
| `us_federal` | New Year's Day (Jan 1) · Independence Day (Jul 4) · Christmas Eve (Dec 24) · Christmas (Dec 25) · New Year's Eve (Dec 31) | Labor Day (1st Mon Sep) · Thanksgiving (4th Thu Nov) · Day after Thanksgiving (4th Fri Nov) |
| `mexico_federal` | New Year's Day (Jan 1) · Labor Day (May 1) · Independence Day (Sep 16) · Christmas (Dec 25) | Constitution Day (1st Mon Feb) · Benito Juárez Day (3rd Mon Mar) · Revolution Day (3rd Mon Nov) |

Floating holidays are **computed each year** by the workflow — no annual YAML
edit is needed.

> Note what is **not** in `us_federal`: Columbus Day, MLK Day, Presidents' Day,
> Memorial Day, Juneteenth and Veterans Day. The list is the days this
> organization actually stops, not the full federal calendar. A freeze on one of
> those needs `custom_dates` — that is exactly why 2026-10-12 (Columbus Day)
> had to be declared explicitly.

### Ad-hoc freezes — `custom_dates`

`custom_dates` is a comma-separated list of `YYYY-MM-DD` dates. **Its default in
`freeze-check.yml` is the one place an org-wide freeze is declared.** Every
consumer references the workflow `@main`, so editing that default takes effect
immediately in every repo, on every branch, with no per-repo PR and no
promotion:

```yaml
# .github/workflows/freeze-check.yml
custom_dates:
  default: "2026-10-12,2026-10-13"
```

> ⚠ **A consumer repo that sets `custom_dates` in its own `merge-freeze.yml`
> overrides this and is NOT covered by the org-wide freeze.** This has already
> bitten: TenPlatform and core both pinned `"2026-08-26"` and still carried it
> six weeks later, which would have silently exempted the two busiest repos from
> the 2026-10-12/13 freeze. Both were removed (TenPlatform #410, core #139).
> Only set it per-repo for a freeze that applies to that repo alone — and
> include any active org dates alongside it.
>
> Audit before relying on an org-wide date:
> ```bash
> gh repo list Ten-Developments --limit 100 --json name --jq '.[].name' |
> while read r; do
>   gh api "repos/Ten-Developments/$r/contents/.github/workflows/merge-freeze.yml?ref=main" \
>     --jq '.content' 2>/dev/null | base64 -d 2>/dev/null |
>     grep -qE '^[[:space:]]+custom_dates:' && echo "$r OVERRIDES"
> done
> ```

Clear past dates when adding new ones. A stale date is harmless on its own, but
it is what let those two overrides go unnoticed.

### Timezone

Default: **`America/Los_Angeles`**. Configurable per consumer repo via the
`timezone` input. All date and day-of-week evaluation happens in this zone, so
a freeze starts and ends at midnight Pacific, not UTC.

---

## Reusable Workflow: `freeze-check.yml`

Path: `.github/workflows/freeze-check.yml`

- **Trigger:** `workflow_call` (callable from any consumer repo)
- **Job name:** `freeze-check` (this exact name is the required status check in the Org Ruleset)
- **Behavior:** Exits 0 on non-frozen days, exits 1 on frozen days

**Inputs**

| Input | Type | Default | Purpose |
|---|---|---|---|
| `timezone` | string | `America/Los_Angeles` | IANA zone all date evaluation happens in |
| `friday_is_weekend` | boolean | `true` | Treat Friday as a weekend day |
| `holiday_calendars` | string | `us_federal,mexico_federal` | Which calendars to enforce |
| `custom_dates` | string | *(the active org-wide freeze)* | Ad-hoc `YYYY-MM-DD` dates — see above |

### Calling this workflow from a consumer repo

```yaml
# .github/workflows/merge-freeze.yml
name: Merge Freeze Check
on:
  pull_request:
    types: [opened, reopened, synchronize, ready_for_review]
  schedule:
    - cron: "*/30 * * * *"   # re-evaluate open PRs every 30 min
permissions:
  contents: read
  statuses: write            # the reusable workflow posts the commit status
jobs:
  freeze:
    uses: Ten-Developments/.github/.github/workflows/freeze-check.yml@main
    with:
      timezone: "America/Los_Angeles"
      friday_is_weekend: true
      holiday_calendars: "us_federal,mexico_federal"
      # custom_dates: DO NOT SET unless this repo needs a freeze no other repo
      # needs — setting it here overrides the org-wide default entirely.
```

> **Important, three things that silently disable enforcement if changed:**
> - The job name must stay `freeze-check` — the Org Ruleset matches that exact string.
> - The `uses:` ref must stay `@main` — that is what makes an org-wide freeze reach every repo without a per-repo change. Pinning a SHA or tag opts the repo out of future policy updates.
> - `permissions: statuses: write` must be present, or the status is never posted and the required check stays pending forever.

---

## Org Ruleset: "Branch Freeze Policy"

| Field | Value |
|-------|-------|
| Name | `Branch Freeze Policy` |
| Enforcement | `active` |
| Target branches | **`main` only** — see below |
| Target repositories | All |
| Required status check | `freeze-check` |
| Bypass list | `Organization Admin` role |

> **`develop` is not covered.** This table used to read `main, develop`. Verified
> 2026-10-08 against TenPlatform, core, hydrology, atlas-api and geostream:
> `freeze-check` is required on `main`, while `develop` requires only each
> repo's own CI checks. **Merges into `develop` are not blocked on frozen days.**
>
> That may well be intended — a freeze on production releases, not on
> integration work. But it should be a decision on the record rather than a
> surprise, so either add `develop` to the ruleset's target branches or leave
> this note as the explanation.

To view or edit: `https://github.com/organizations/Ten-Developments/settings/rules`

Reading the ruleset over the API needs the `admin:org` scope
(`gh auth refresh -h github.com -s admin:org`). To check what is actually
enforced on a branch without it, the repo-level endpoint needs only `repo`:

```bash
gh api repos/Ten-Developments/TenPlatform/rules/branches/main \
  --jq '[.[]|select(.type=="required_status_checks").parameters.required_status_checks[]?.context]'
```

---

## Adding the Freeze to a New Repo

1. Create `.github/workflows/merge-freeze.yml` in the new repo with the snippet above
2. Commit it to **every branch the ruleset protects** — see the note below
3. The freeze starts working on the next PR or cron tick — no further action needed
4. The Org Ruleset blocks merges to `main` during frozen days automatically

> **Which branch the caller file lives on matters.** For `pull_request` events
> GitHub reads the *caller* workflow from the **base branch of the PR** — a PR
> into `main` uses `main`'s copy. So the file (and any per-repo override in it)
> must be correct on `main`. By contrast the *reusable* workflow is always
> resolved at `@main` of this repo, which is why a policy change here needs no
> per-repo work at all.

## Declaring an org-wide ad-hoc freeze

The common case: freeze every repo on specific dates.

1. Edit `custom_dates`' **default** in `.github/workflows/freeze-check.yml`
2. PR it to **`main` of this repo** — a merge to `develop` here does nothing, because consumers resolve the workflow `@main`
3. Merge. Every consumer picks it up on its next PR event or cron tick — no per-repo PR, no promotion
4. Confirm no repo overrides `custom_dates` (audit snippet above). An override silently exempts that repo

Worked example: [`.github` #2](https://github.com/Ten-Developments/.github/pull/2)
declared 2026-10-12/13, and TenPlatform #410 / core #139 removed the two stale
overrides that would otherwise have exempted them.

## Updating the Freeze Policy

The freeze logic lives in **one file**: `.github/workflows/freeze-check.yml`. To change the rules:

1. Edit the file in a feature branch
2. Test the date math locally (extract the Bash logic and run it against the dates you care about, including the day either side)
3. Open a PR to `main` of this repo
4. Merge
5. All consumer repos inherit the new logic on the next PR event or cron tick

To verify without waiting for a frozen day, dispatch a consumer's caller and
read the log — it prints the resolved inputs and the reason on every run:

```bash
gh workflow run merge-freeze.yml --repo Ten-Developments/hydrology
gh run list --workflow merge-freeze.yml --repo Ten-Developments/hydrology --limit 1
```

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
├── docs/
│   └── manual-ruleset-setup.md                ← creating the Org Ruleset by hand
├── scripts/                                   ← one-off automation used to roll the
│                                                 policy out across the org; not run
│                                                 as part of normal operation
└── .github/
    └── workflows/
        ├── freeze-check.yml                   ← the reusable workflow (single source of truth,
        │                                         and where an org-wide freeze is declared)
        ├── merge-freeze.yml                   ← the caller template (copy into consumer repos)
        └── cert-expiry-monitor.yml            ← unrelated to the freeze
```

> **Note:** Yes, the path is `ten-github-org/.github/.github/workflows/...` — the first `.github` is the repo name, the second `.github` is GitHub's required directory for workflow files.

---

## References

- Task: **TEN-TR01_00001** — Branch freeze lock enterprise level to repos
- [GitHub: Reusable workflows](https://docs.github.com/en/actions/sharing-automations/reusing-workflows)
- [GitHub: Org-level .github repository](https://docs.github.com/en/organizations/collaborating-with-groups-in-organizations/customizing-your-organizations-profile#adding-a-public-organization-profile-readme)
- [GitHub: Rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)

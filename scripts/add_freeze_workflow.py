"""
add_freeze_workflow.py

Adds the merge-freeze.yml caller workflow to one or more repos in the
Ten-Developments org, opening a PR per repo.

Usage:
    # Pilot: add to atlas-api only
    python add_freeze_workflow.py --pilot atlas-api

    # Bulk: add to all eligible repos
    python add_freeze_workflow.py --bulk

    # Add to specific repos
    python add_freeze_workflow.py --repos atlas-api,devremote,geostream

    # Dry run (no API calls)
    python add_freeze_workflow.py --pilot atlas-api --dry-run

Requires: gh CLI authenticated, with repo+workflow scopes.
"""

import argparse
import subprocess
import sys
import base64
import json

ORG = "Ten-Developments"
CALLER_WORKFLOW_PATH = ".github/workflows/merge-freeze.yml"
BRANCH_NAME = "freeze/add-caller-workflow"
PR_TITLE = "feat: add org-level branch freeze caller workflow"
PR_BODY = """\
## What

Adds `.github/workflows/merge-freeze.yml` to enroll this repo in the org-level
**Branch Freeze Policy** (task TEN-TR01_00001).

## Why

Ten-Developments is implementing an enterprise branch freeze that blocks PR
merges to `main` and `develop` on weekends and US federal holidays. The freeze
is enforced by an Org Ruleset that requires the `freeze-check` status check to
pass before any merge.

This PR adds the caller workflow that triggers the `freeze-check` reusable
workflow (which lives in `Ten-Developments/.github`) on every PR and every
30 minutes via cron.

## Behavior

- **Pull request events**: status check runs immediately on `opened`,
  `reopened`, `synchronize`, `ready_for_review`
- **Schedule**: re-evaluates every 30 minutes (`*/30 * * * *`) so that
  PRs opened before a freeze window begins get re-evaluated when the freeze
  starts
- **No secrets required**: the reusable workflow is self-contained, no
  service accounts, no tokens

## What you need to know

- This is a **required status check** in the org ruleset. The merge button
  will be blocked during frozen days/weekends once the ruleset is active.
- To merge during a freeze for an emergency, an org admin can use the
  "Bypass" option (see org audit log for usage).
- See https://github.com/Ten-Developments/.github for full policy docs.

## References

- [Implementation plan](../../freeze_lock_enterprise/implementation.md)
- [Task TEN-TR01_00001](../../freeze_lock_enterprise/Freeze%20lock%20enterpirse%20level%20to%20repos.pdf)
- [Org policy repo](https://github.com/Ten-Developments/.github)
"""

# The content of the caller workflow (inlined so the script is self-contained)
CALLER_WORKFLOW_CONTENT = """\
name: Merge Freeze Check

# This is the CALLER workflow. It enrolls this repo in the org-level
# branch freeze policy (task TEN-TR01_00001).
#
# The freeze logic itself lives in the reusable workflow:
#   Ten-Developments/.github/.github/workflows/freeze-check.yml
# This file just triggers the check on PR events and on a cron schedule.

on:
  pull_request:
    types: [opened, reopened, synchronize, ready_for_review]
  schedule:
    # Re-check open PRs every 30 minutes. The cron schedule is critical —
    # without it, PRs opened before a freeze window begins won't get
    # re-evaluated when the freeze starts.
    - cron: "*/30 * * * *"

jobs:
  freeze:
    uses: Ten-Developments/.github/.github/workflows/freeze-check.yml@main
    with:
      timezone: "America/Los_Angeles"
"""

# Repos to skip (empty repos, archived, or the policy repo itself)
SKIP_REPOS = {".github", "business-hydrology-frontpage"}


def run_gh(args, check=True, capture=True):
    """Run a gh CLI command and return the result."""
    cmd = ["gh"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"  ERROR: gh {' '.join(args)}")
        print(f"  stdout: {result.stdout}")
        print(f"  stderr: {result.stderr}")
        sys.exit(1)
    return result


def get_eligible_repos():
    """List all repos in the org, excluding policy repo and empty repos."""
    result = run_gh(["repo", "list", ORG, "--limit", "200",
                     "--json", "name,defaultBranchRef,isArchived"])
    repos = json.loads(result.stdout)
    eligible = []
    skipped = []
    for r in repos:
        if r["name"] in SKIP_REPOS:
            skipped.append((r["name"], "in skip list"))
            continue
        if r["isArchived"]:
            skipped.append((r["name"], "archived"))
            continue
        if not r.get("defaultBranchRef"):
            skipped.append((r["name"], "no default branch (empty repo)"))
            continue
        eligible.append({
            "name": r["name"],
            "default_branch": r["defaultBranchRef"]["name"],
        })
    return eligible, skipped


def already_has_workflow(repo_name):
    """Check if the repo already has merge-freeze.yml."""
    result = run_gh(
        ["api", f"/repos/{ORG}/{repo_name}/contents/.github/workflows/merge-freeze.yml"],
        check=False,
    )
    return result.returncode == 0


def file_already_exists_on_branch(repo_name, branch):
    """Check if merge-freeze.yml already exists on the branch."""
    result = run_gh(
        ["api", f"/repos/{ORG}/{repo_name}/contents/.github/workflows/merge-freeze.yml?ref={branch}"],
        check=False,
    )
    return result.returncode == 0


def get_default_branch_sha(repo_name, default_branch):
    """Get the SHA of the tip of the default branch."""
    result = run_gh([
        "api", f"/repos/{ORG}/{repo_name}/git/ref/heads/{default_branch}",
        "--jq", ".object.sha"
    ])
    return result.stdout.strip()


def create_branch(repo_name, default_branch, new_branch):
    """Create a new branch off the default branch tip."""
    sha = get_default_branch_sha(repo_name, default_branch)
    run_gh([
        "api", "-X", "POST",
        f"/repos/{ORG}/{repo_name}/git/refs",
        "-f", f"ref=refs/heads/{new_branch}",
        "-f", f"sha={sha}",
    ])
    print(f"  Created branch {new_branch}")


def commit_file_to_branch(repo_name, branch, file_path, content, commit_message):
    """Create or update a file on the given branch via the Contents API."""
    b64_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    # Check if file exists on branch
    existing = run_gh(
        ["api", f"/repos/{ORG}/{repo_name}/contents/{file_path}?ref={branch}",
         "--jq", ".sha"],
        check=False,
    )

    if existing.returncode == 0 and existing.stdout.strip():
        # File exists - update
        existing_sha = existing.stdout.strip()
        run_gh([
            "api", "-X", "PUT",
            f"/repos/{ORG}/{repo_name}/contents/{file_path}",
            "-f", f"message={commit_message}",
            "-f", f"content={b64_content}",
            "-f", f"branch={branch}",
            "-f", f"sha={existing_sha}",
        ])
        print(f"  Updated file {file_path} on {branch}")
    else:
        # File doesn't exist - create
        run_gh([
            "api", "-X", "PUT",
            f"/repos/{ORG}/{repo_name}/contents/{file_path}",
            "-f", f"message={commit_message}",
            "-f", f"content={b64_content}",
            "-f", f"branch={branch}",
        ])
        print(f"  Created file {file_path} on {branch}")


def open_pull_request(repo_name, branch, default_branch, title, body):
    """Open a PR. Returns True if a new PR was created, False if one already exists."""
    # Check for existing open PR
    existing = run_gh([
        "pr", "list", "--repo", f"{ORG}/{repo_name}",
        "--head", branch, "--base", default_branch,
        "--state", "open", "--json", "number",
    ], check=False)
    if existing.stdout.strip() and existing.stdout.strip() != "[]":
        print(f"  PR already exists: {existing.stdout.strip()}")
        return False

    result = run_gh([
        "pr", "create", "--repo", f"{ORG}/{repo_name}",
        "--base", default_branch,
        "--head", branch,
        "--title", title,
        "--body", body,
    ])
    print(f"  Opened PR: {result.stdout.strip()}")
    return True


def process_repo(repo_name, dry_run=False):
    """Add the caller workflow to one repo: branch + commit + PR."""
    print(f"\n{'='*60}")
    print(f"Repo: {ORG}/{repo_name}")
    print(f"{'='*60}")

    # Get default branch
    result = run_gh(["repo", "view", f"{ORG}/{repo_name}", "--json", "defaultBranchRef"])
    repo_info = json.loads(result.stdout)
    if not repo_info.get("defaultBranchRef"):
        print(f"  SKIP: no default branch")
        return False
    default_branch = repo_info["defaultBranchRef"]["name"]
    print(f"  Default branch: {default_branch}")

    # Check if already has the workflow on the default branch
    if already_has_workflow(repo_name):
        print(f"  SKIP: merge-freeze.yml already exists on {default_branch}")
        return False

    # Check if branch already exists
    branch_exists = run_gh(
        ["api", f"/repos/{ORG}/{repo_name}/git/ref/heads/{BRANCH_NAME}"],
        check=False,
    ).returncode == 0

    if dry_run:
        print(f"  [DRY RUN] would create branch {BRANCH_NAME}")
        print(f"  [DRY RUN] would commit {CALLER_WORKFLOW_PATH}")
        print(f"  [DRY RUN] would open PR to {default_branch}")
        return True

    # Create branch
    if not branch_exists:
        create_branch(repo_name, default_branch, BRANCH_NAME)
    else:
        print(f"  Branch {BRANCH_NAME} already exists, reusing")

    # Commit file
    commit_file_to_branch(
        repo_name, BRANCH_NAME, CALLER_WORKFLOW_PATH,
        CALLER_WORKFLOW_CONTENT,
        "feat: add org-level branch freeze caller workflow",
    )

    # Open PR
    open_pull_request(repo_name, BRANCH_NAME, default_branch, PR_TITLE, PR_BODY)

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Add merge-freeze.yml caller workflow to Ten-Developments repos"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pilot", metavar="REPO", help="Pilot: process a single repo")
    group.add_argument("--bulk", action="store_true", help="Process all eligible repos")
    group.add_argument("--repos", metavar="R1,R2,...", help="Comma-separated list of repos")
    parser.add_argument("--dry-run", action="store_true", help="Don't make any API calls")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm in non-interactive mode")

    args = parser.parse_args()

    if args.pilot:
        targets = [args.pilot]
    elif args.bulk:
        eligible, skipped = get_eligible_repos()
        print(f"Eligible repos ({len(eligible)}):")
        for r in eligible:
            print(f"  - {r['name']}")
        if skipped:
            print(f"\nSkipped repos ({len(skipped)}):")
            for name, reason in skipped:
                print(f"  - {name} ({reason})")
        targets = [r["name"] for r in eligible]
    else:
        targets = [r.strip() for r in args.repos.split(",")]

    if args.dry_run:
        print("\n*** DRY RUN MODE — no API calls will be made ***\n")

    print(f"\nWill process {len(targets)} repo(s).")
    if not args.dry_run:
        # Check if stdin is a TTY (interactive). If not (e.g., piped),
        # require --yes to proceed.
        import sys
        if sys.stdin.isatty():
            confirm = input("Continue? (y/n): ")
            if confirm.lower() != "y":
                print("Aborted.")
                return
        else:
            if not args.yes:
                print("Non-interactive mode detected. Use --yes to confirm, or pipe 'y' on stdin.")
                return

    success = 0
    failed = 0
    for repo_name in targets:
        try:
            if process_repo(repo_name, dry_run=args.dry_run):
                success += 1
        except SystemExit:
            failed += 1
        except Exception as e:
            print(f"  UNEXPECTED ERROR: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Done. {success} succeeded, {failed} failed.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

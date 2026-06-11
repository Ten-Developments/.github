"""
recreate_freeze_branch.py

Recreates a clean freeze/add-caller-workflow-v2 branch off `main` (or
the repo's default branch) with only the merge-freeze.yml file. This is
needed when the original freeze branch was based off a different branch
(like `develop`) and accumulated unrelated changes.

Usage:
    # Recreate for one repo
    python recreate_freeze_branch.py --repo core --base main

    # Recreate for all repos that have a polluted freeze branch
    python recreate_freeze_branch.py --all --base main

    # Dry-run
    python recreate_freeze_branch.py --repo core --dry-run
"""

import argparse
import base64
import json
import subprocess
import sys

ORG = "Ten-Developments"
CALLER_WORKFLOW_PATH = ".github/workflows/merge-freeze.yml"
NEW_BRANCH = "freeze/add-caller-workflow-v2"
OLD_BRANCH = "freeze/add-caller-workflow"
COMMIT_MESSAGE = "feat: add org-level branch freeze caller workflow"
PR_TITLE = "feat: add org-level branch freeze caller workflow (clean)"

# The content of the caller workflow (latest version with all inputs)
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
      friday_is_weekend: true
      holiday_calendars: "us_federal,mexico_federal"
"""


def run_gh(args, check=True, capture=True):
    cmd = ["gh"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"  ERROR: gh {' '.join(args)}")
        print(f"  stderr: {result.stderr}")
        if result.stdout:
            print(f"  stdout: {result.stdout}")
        sys.exit(1)
    return result


def get_default_branch(repo_name):
    result = run_gh(["repo", "view", f"{ORG}/{repo_name}", "--json", "defaultBranchRef"])
    data = json.loads(result.stdout)
    return data.get("defaultBranchRef", {}).get("name", "main")


def branch_exists(repo_name, branch):
    result = run_gh(
        ["api", f"/repos/{ORG}/{repo_name}/git/ref/heads/{branch}"],
        check=False,
    )
    return result.returncode == 0


def get_branch_sha(repo_name, branch):
    result = run_gh([
        "api", f"/repos/{ORG}/{repo_name}/git/ref/heads/{branch}",
        "--jq", ".object.sha",
    ])
    return result.stdout.strip()


def create_branch(repo_name, base_branch, new_branch):
    sha = get_branch_sha(repo_name, base_branch)
    run_gh([
        "api", "-X", "POST",
        f"/repos/{ORG}/{repo_name}/git/refs",
        "-f", f"ref=refs/heads/{new_branch}",
        "-f", f"sha={sha}",
    ])
    print(f"  Created branch {new_branch} from {base_branch} (sha={sha[:7]})")


def commit_file_to_branch(repo_name, branch, file_path, content, commit_message):
    b64_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    run_gh([
        "api", "-X", "PUT",
        f"/repos/{ORG}/{repo_name}/contents/{file_path}",
        "-f", f"message={commit_message}",
        "-f", f"content={b64_content}",
        "-f", f"branch={branch}",
    ])
    print(f"  Committed {file_path} to {branch}")


def open_pr(repo_name, head, base, title, body=""):
    # Check if a PR already exists
    result = run_gh([
        "pr", "list", "--repo", f"{ORG}/{repo_name}",
        "--head", head, "--base", base, "--state", "open",
        "--json", "number",
    ], check=False)
    if result.stdout.strip() and result.stdout.strip() != "[]":
        print(f"  PR already exists: {result.stdout.strip()}")
        return
    run_gh([
        "pr", "create", "--repo", f"{ORG}/{repo_name}",
        "--base", base, "--head", head,
        "--title", title,
        "--body", body,
    ])
    print(f"  Opened PR: {base} <- {head}")


def process_repo(repo_name, base_branch, dry_run=False):
    print(f"\n{'='*60}")
    print(f"Repo: {ORG}/{repo_name}")
    print(f"{'='*60}")

    if branch_exists(repo_name, NEW_BRANCH):
        print(f"  SKIP: branch {NEW_BRANCH} already exists")
        return

    if dry_run:
        print(f"  [DRY RUN] would create branch {NEW_BRANCH} from {base_branch}")
        print(f"  [DRY RUN] would commit {CALLER_WORKFLOW_PATH}")
        print(f"  [DRY RUN] would open PR {base_branch} <- {NEW_BRANCH}")
        return

    create_branch(repo_name, base_branch, NEW_BRANCH)
    commit_file_to_branch(repo_name, NEW_BRANCH, CALLER_WORKFLOW_PATH,
                         CALLER_WORKFLOW_CONTENT, COMMIT_MESSAGE)
    open_pr(repo_name, NEW_BRANCH, base_branch, PR_TITLE,
            body="Clean recreation of the freeze caller workflow branch, "
                 "based on `main` to avoid pulling in unrelated changes from `develop`.")


def main():
    parser = argparse.ArgumentParser(
        description="Recreate a clean freeze branch from a specific base branch"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--repo", metavar="REPO", help="Process a single repo")
    group.add_argument("--all", action="store_true", help="Process all org repos")
    parser.add_argument("--base", metavar="BRANCH", default="main",
                        help="Base branch to branch off (default: main)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without changes")
    args = parser.parse_args()

    if args.repo:
        targets = [args.repo]
    else:
        # Get all repos
        result = run_gh(["repo", "list", ORG, "--limit", "200", "--json", "name"])
        repos = json.loads(result.stdout)
        targets = [r["name"] for r in repos]

    print(f"Will process {len(targets)} repo(s) with base={args.base}.")
    if not args.dry_run:
        try:
            confirm = input("Continue? (y/n): ")
            if confirm.lower() != "y":
                print("Aborted.")
                return
        except EOFError:
            print("Non-interactive mode — use --yes or pipe 'y' on stdin.")
            return

    for repo_name in targets:
        try:
            process_repo(repo_name, args.base, args.dry_run)
        except SystemExit:
            pass


if __name__ == "__main__":
    main()

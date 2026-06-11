"""
add_freeze_to_develop.py

Adds merge-freeze.yml to a develop branch via a small PR (since direct
pushes are blocked by the ruleset). Once the PR is merged, any open
PRs against main from develop will have the freeze workflow available.

Usage:
    python add_freeze_to_develop.py devremote develop
"""

import base64
import json
import subprocess
import sys

REPO = "Ten-Developments"
REPO_NAME = sys.argv[1] if len(sys.argv) > 1 else "devremote"
TARGET_BRANCH = sys.argv[2] if len(sys.argv) > 2 else "develop"
SOURCE_BRANCH = f"add-merge-freeze-to-{TARGET_BRANCH}"
FILE_PATH = ".github/workflows/merge-freeze.yml"
PR_TITLE = f"feat: add merge-freeze caller workflow to {TARGET_BRANCH}"
PR_BODY = f"""\
## What

Adds `.github/workflows/merge-freeze.yml` to the `{TARGET_BRANCH}` branch so
that PRs originating from `{TARGET_BRANCH}` can satisfy the org-level
Branch Freeze Policy required check (`freeze / freeze-check`).

## Why

The freeze policy uses a reusable workflow in `Ten-Developments/.github` that
is invoked by a caller workflow in each consumer repo. The caller
workflow must exist on the PR's source branch for the freeze check to
run. Without it, the check is permanently "Expected" and the ruleset
blocks merges.

This PR back-ports the caller workflow to `{TARGET_BRANCH}` so that
existing in-flight PRs (e.g., #7) can satisfy the freeze check.

## Behavior

Same as the existing `merge-freeze.yml` on `main`:
- Pull request events: status check runs immediately
- Schedule: re-evaluates every 30 minutes
- No secrets required

## References

Task: TEN-TR01_00001
"""


def run_gh(args, check=True):
    cmd = ["gh"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"  ERROR: gh {' '.join(args)}")
        print(f"  stderr: {result.stderr}")
        if result.stdout:
            print(f"  stdout: {result.stdout}")
        sys.exit(1)
    return result


def branch_exists(repo_name, branch):
    result = run_gh(
        ["api", f"/repos/{REPO}/{repo_name}/git/ref/heads/{branch}"],
        check=False,
    )
    return result.returncode == 0


def get_sha(repo_name, branch):
    result = run_gh([
        "api", f"/repos/{REPO}/{repo_name}/git/ref/heads/{branch}",
        "--jq", ".object.sha",
    ])
    return result.stdout.strip()


def create_branch(repo_name, base_branch, new_branch):
    if branch_exists(repo_name, new_branch):
        print(f"  Branch {new_branch} already exists, reusing")
        return
    sha = get_sha(repo_name, base_branch)
    run_gh([
        "api", "-X", "POST",
        f"/repos/{REPO}/{repo_name}/git/refs",
        "-f", f"ref=refs/heads/{new_branch}",
        "-f", f"sha={sha}",
    ])
    print(f"  Created branch {new_branch} from {base_branch}")


def commit_file(repo_name, branch, file_path, content, commit_message):
    b64_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    # Check if file already exists
    result = run_gh(
        ["api", f"/repos/{REPO}/{repo_name}/contents/{file_path}?ref={branch}"],
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        import re
        m = re.search(r'"sha":\s*"([a-f0-9]+)"', result.stdout)
        existing_sha = m.group(1) if m else None
        if existing_sha:
            run_gh([
                "api", "-X", "PUT",
                f"/repos/{REPO}/{repo_name}/contents/{file_path}",
                "-f", f"message={commit_message}",
                "-f", f"content={b64_content}",
                "-f", f"branch={branch}",
                "-f", f"sha={existing_sha}",
            ])
            print(f"  Updated {file_path} on {branch}")
            return
    run_gh([
        "api", "-X", "PUT",
        f"/repos/{REPO}/{repo_name}/contents/{file_path}",
        "-f", f"message={commit_message}",
        "-f", f"content={b64_content}",
        "-f", f"branch={branch}",
    ])
    print(f"  Created {file_path} on {branch}")


def open_pr(repo_name, head, base, title, body):
    # Check for existing PR
    result = run_gh([
        "pr", "list", "--repo", f"{REPO}/{repo_name}",
        "--head", head, "--base", base, "--state", "open",
        "--json", "number",
    ], check=False)
    if result.stdout.strip() and result.stdout.strip() != "[]":
        print(f"  PR already exists: {result.stdout.strip()}")
        return
    result = run_gh([
        "pr", "create", "--repo", f"{REPO}/{repo_name}",
        "--base", base, "--head", head,
        "--title", title,
        "--body", body,
    ])
    print(f"  Opened PR: {result.stdout.strip()}")


def main():
    print(f"Adding freeze workflow to {REPO}/{REPO_NAME}@{TARGET_BRANCH}")
    print(f"  Will create branch {SOURCE_BRANCH} from {TARGET_BRANCH}")
    print()

    # Read the latest version
    with open(r"C:\tendevelopments\code\ten-github-org\.github\workflows\merge-freeze.yml", "r", encoding="utf-8") as f:
        content = f.read()

    create_branch(REPO_NAME, TARGET_BRANCH, SOURCE_BRANCH)
    commit_file(REPO_NAME, SOURCE_BRANCH, FILE_PATH, content,
                f"feat: add merge-freeze caller workflow to {TARGET_BRANCH}")
    open_pr(REPO_NAME, SOURCE_BRANCH, TARGET_BRANCH, PR_TITLE, PR_BODY)
    print()
    print(f"Done. PR opened against {TARGET_BRANCH}.")


if __name__ == "__main__":
    main()

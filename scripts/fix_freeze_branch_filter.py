import base64
import json
import os
import subprocess
import sys
import tempfile

ORG = "Ten-Developments"
FILE_PATH = ".github/workflows/merge-freeze.yml"
COMMIT_MSG = "fix: restrict freeze check to PRs targeting main only"
SOURCE_BRANCH = "fix/freeze-branch-filter"
PR_TITLE = "fix: restrict freeze check to PRs targeting main only"
PR_BODY = """\
## What

Updates `.github/workflows/merge-freeze.yml` to add `branches: [main]` to
the `pull_request` trigger.

## Why

The freeze check was running on ALL PRs (including those targeting develop),
causing it to appear as "Expected" on develop PRs. The org-level Branch
Freeze Policy ruleset only targets `main`, so the check should only run
on PRs to `main`.

## What changed

```yaml
# Before
on:
  pull_request:
    types: [opened, reopened, synchronize, ready_for_review]

# After
on:
  pull_request:
    types: [opened, reopened, synchronize, ready_for_review]
    branches:
      - main
```

Task: TEN-TR01_00001
"""

LOCAL_FILE = r"C:\tendevelopments\code\ten-github-org\.github\workflows\merge-freeze.yml"
with open(LOCAL_FILE, "r", encoding="utf-8") as f:
    NEW_CONTENT = f.read()
NEW_B64 = base64.b64encode(NEW_CONTENT.encode("utf-8")).decode("utf-8")


def run_gh(args, check=True):
    cmd = ["gh"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"  ERROR: {result.stderr}")
        sys.exit(1)
    return result.stdout, None


def main():
    if len(sys.argv) < 2:
        print("Usage: python fix_freeze_branch_filter.py <repo> [branch]")
        sys.exit(1)

    repo = sys.argv[1]
    target_branch = sys.argv[2] if len(sys.argv) > 2 else "develop"

    print(f"Creating PR to fix freeze branch filter on {ORG}/{repo}@{target_branch}")

    # Get the SHA of the target branch
    result, _ = run_gh([
        "api", f"/repos/{ORG}/{repo}/git/ref/heads/{target_branch}",
        "--jq", ".object.sha"
    ])
    base_sha = result.strip().strip('"')
    print(f"  Base SHA: {base_sha[:7]}")

    # Check if source branch already exists
    result, _ = run_gh([
        "api", f"/repos/{ORG}/{repo}/git/ref/heads/{SOURCE_BRANCH}",
    ], check=False)
    if result and "sha" in result:
        print(f"  Branch {SOURCE_BRANCH} already exists, reusing")
    else:
        # Create the branch
        run_gh([
            "api", "-X", "POST",
            f"/repos/{ORG}/{repo}/git/refs",
            "-f", f"ref=refs/heads/{SOURCE_BRANCH}",
            "-f", f"sha={base_sha}",
        ])
        print(f"  Created branch {SOURCE_BRANCH}")

    # Get current file SHA on the source branch
    result, _ = run_gh([
        "api", f"/repos/{ORG}/{repo}/contents/{FILE_PATH}?ref={SOURCE_BRANCH}",
        "--jq", ".sha"
    ], check=False)

    sha = None
    if result and result.strip() and result.strip() != "null":
        sha = result.strip().strip('"')

    with tempfile.NamedTemporaryFile(mode="w", suffix=".b64", delete=False, encoding="utf-8") as f:
        f.write(NEW_B64)
        b64_file = f.name

    if sha:
        print(f"  File exists (sha={sha[:7]}), updating...")
        result, err = run_gh([
            "api", "-X", "PUT",
            f"/repos/{ORG}/{repo}/contents/{FILE_PATH}",
            "-F", f"message={COMMIT_MSG}",
            "-F", f"content=@{b64_file}",
            "-F", f"branch={SOURCE_BRANCH}",
            "-F", f"sha={sha}",
        ], check=False)
    else:
        print(f"  File doesn't exist, creating...")
        result, err = run_gh([
            "api", "-X", "PUT",
            f"/repos/{ORG}/{repo}/contents/{FILE_PATH}",
            "-F", f"message={COMMIT_MSG}",
            "-F", f"content=@{b64_file}",
            "-F", f"branch={SOURCE_BRANCH}",
        ], check=False)

    os.unlink(b64_file)

    if err:
        print(f"  ERROR updating file: {err}")
        sys.exit(1)
    print(f"  File updated")

    # Check for existing PR
    result, _ = run_gh([
        "pr", "list", "--repo", f"{ORG}/{repo}",
        "--head", SOURCE_BRANCH, "--base", target_branch, "--state", "open",
        "--json", "number",
    ], check=False)
    if result and result.strip() and result.strip() != "[]":
        prs = json.loads(result)
        pr_num = prs[0]["number"]
        print(f"  PR already exists: #{pr_num}")
        return

    # Create PR
    result, _ = run_gh([
        "pr", "create", "--repo", f"{ORG}/{repo}",
        "--base", target_branch, "--head", SOURCE_BRANCH,
        "--title", PR_TITLE, "--body", PR_BODY,
    ])
    print(f"  Opened PR: {result.strip()}")


if __name__ == "__main__":
    main()

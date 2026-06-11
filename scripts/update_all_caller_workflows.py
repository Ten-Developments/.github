"""
update_all_caller_workflows.py

Pushes the updated merge-freeze.yml (with branches: [main] filter) to all
consumer repos in the Ten-Developments org via the GitHub API.

This is needed when the caller workflow is updated in the .github repo
and the change needs to be propagated to all consumer repos.

Usage:
    python update_all_caller_workflows.py           # dry-run
    python update_all_caller_workflows.py --apply   # actually push
"""

import argparse
import base64
import json
import subprocess
import sys

ORG = "Ten-Developments"
FILE_PATH = ".github/workflows/merge-freeze.yml"

# Read the latest version from the local .github repo
LOCAL_FILE = r"C:\tendevelopments\code\ten-github-org\.github\workflows\merge-freeze.yml"
with open(LOCAL_FILE, "r", encoding="utf-8") as f:
    NEW_CONTENT = f.read()
NEW_B64 = base64.b64encode(NEW_CONTENT.encode("utf-8")).decode("utf-8")

SKIP_REPOS = {".github", "business-hydrology-frontpage"}


def run_gh(args, check=True):
    cmd = ["gh"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        return None, result.stderr
    return result.stdout, None


def get_eligible_repos():
    result, _ = run_gh(["repo", "list", ORG, "--limit", "200", "--json", "name,defaultBranchRef,isArchived"])
    repos = json.loads(result)
    eligible = []
    for r in repos:
        name = r["name"]
        if name in SKIP_REPOS:
            continue
        if r.get("isArchived"):
            continue
        if not r.get("defaultBranchRef"):
            continue
        eligible.append({
            "name": name,
            "default_branch": r["defaultBranchRef"]["name"],
        })
    return eligible


def get_file_sha(repo_name, branch):
    """Get the SHA of the file on a branch. Returns (sha, error)."""
    result, err = run_gh([
        "api", f"/repos/{ORG}/{repo_name}/contents/{FILE_PATH}?ref={branch}",
        "--jq", ".sha"
    ], check=False)
    if result and result.strip() and result.strip() != "null":
        return result.strip().strip('"'), None
    return None, err


def get_file_content(repo_name, branch):
    """Get the current file content on a branch."""
    result, _ = run_gh([
        "api", f"/repos/{ORG}/{repo_name}/contents/{FILE_PATH}?ref={branch}",
        "--jq", ".content"
    ], check=False)
    if result:
        b64 = result.strip().strip('"').replace("\\n", "").replace("\n", "")
        try:
            return base64.b64decode(b64).decode("utf-8")
        except Exception:
            return None
    return None


def update_file(repo_name, branch, sha, dry_run=False):
    """Update the file on a branch via the Contents API."""
    if dry_run:
        return True, "[DRY RUN]"
    import tempfile
    import os
    with tempfile.NamedTemporaryFile(mode="w", suffix=".b64", delete=False, encoding="utf-8") as f:
        f.write(NEW_B64)
        b64_file = f.name
    result, err = run_gh([
        "api", "-X", "PUT",
        f"/repos/{ORG}/{repo_name}/contents/{FILE_PATH}",
        "-F", "message=fix: restrict freeze check to PRs targeting main only",
        "-F", f"content=@{b64_file}",
        "-F", f"branch={branch}",
        "-F", f"sha={sha}",
    ], check=False)
    os.unlink(b64_file)
    if err:
        return False, err
    return True, "updated"


def create_file(repo_name, branch, dry_run=False):
    """Create the file on a branch via the Contents API."""
    if dry_run:
        return True, "[DRY RUN]"
    import tempfile
    import os
    with tempfile.NamedTemporaryFile(mode="w", suffix=".b64", delete=False, encoding="utf-8") as f:
        f.write(NEW_B64)
        b64_file = f.name
    result, err = run_gh([
        "api", "-X", "PUT",
        f"/repos/{ORG}/{repo_name}/contents/{FILE_PATH}",
        "-F", "message=fix: restrict freeze check to PRs targeting main only",
        "-F", f"content=@{b64_file}",
        "-F", f"branch={branch}",
    ], check=False)
    os.unlink(b64_file)
    if err:
        return False, err
    return True, "created"


def main():
    parser = argparse.ArgumentParser(
        description="Push updated merge-freeze.yml to all consumer repos"
    )
    parser.add_argument("--apply", action="store_true", help="Actually push changes")
    parser.add_argument("--force", action="store_true",
                        help="Update even if content is identical")
    args = parser.parse_args()

    print("Finding eligible repos...")
    repos = get_eligible_repos()
    print(f"Found {len(repos)} eligible repos")
    print()

    results = []
    for repo in repos:
        name = repo["name"]
        branch = repo["default_branch"]
        print(f"  [{name}] (default: {branch})", end=" ")

        # Get current file
        sha, err = get_file_sha(name, branch)
        if sha:
            # File exists, check if content is different
            current = get_file_content(name, branch)
            if current == NEW_CONTENT and not args.force:
                print("SKIP (already up to date)")
                results.append((name, "up-to-date"))
                continue

            if args.apply:
                ok, msg = update_file(name, branch, sha)
                print(msg if ok else f"ERROR: {msg}")
                results.append((name, "updated" if ok else "error"))
            else:
                print("[DRY RUN] would update")
                results.append((name, "would-update"))
        else:
            # File doesn't exist
            if args.apply:
                ok, msg = create_file(name, branch)
                print(msg if ok else f"ERROR: {msg}")
                results.append((name, "created" if ok else "error"))
            else:
                print("[DRY RUN] would create")
                results.append((name, "would-create"))

    print()
    print("=" * 60)
    summary = {}
    for name, status in results:
        summary[status] = summary.get(status, 0) + 1
    for status, count in sorted(summary.items()):
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()

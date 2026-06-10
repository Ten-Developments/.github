"""
retrigger_freeze_workflow.py

Pushes a no-op commit to all open PRs that are waiting for the
freeze-check workflow to re-evaluate against a (newly updated) Org Ruleset.

When the Org Ruleset's required check changes, GitHub does NOT
retroactively re-evaluate the existing successful workflow runs.
Pushing a new commit forces a fresh run, which the ruleset will then
evaluate against the new requirement.

Usage:
    python retrigger_freeze_workflow.py           # dry-run by default
    python retrigger_freeze_workflow.py --apply   # actually push commits
"""

import argparse
import json
import subprocess
import sys

ORG = "Ten-Developments"
COMMIT_MESSAGE = "chore: retrigger freeze-check workflow after ruleset update"


def run_gh(args, check=True):
    """Run gh CLI and return parsed JSON."""
    result = subprocess.run(["gh"] + args, capture_output=True, text=True)
    if check and result.returncode != 0:
        return None, result.stderr
    if result.stdout.strip():
        try:
            return json.loads(result.stdout), None
        except json.JSONDecodeError:
            return result.stdout, None
    return None, None


def find_freeze_prs():
    """Find all open PRs with the freeze caller workflow branch."""
    # Get all repos
    repos_data, err = run_gh(["repo", "list", ORG, "--limit", "200", "--json", "name"])
    if err:
        print(f"Error listing repos: {err}")
        return []
    repos = repos_data or []

    freeze_prs = []
    for repo in repos:
        name = repo["name"]
        # Get all open PRs in this repo
        prs_data, _ = run_gh([
            "pr", "list", "--repo", f"{ORG}/{name}",
            "--state", "open", "--json", "number,title,headRefName,baseRefName,url",
        ])
        if not prs_data:
            continue
        for pr in prs_data:
            # Match PRs from the freeze rollout (head branch is freeze/add-caller-workflow)
            if pr.get("headRefName") == "freeze/add-caller-workflow":
                freeze_prs.append({
                    "repo": name,
                    "number": pr["number"],
                    "branch": pr["headRefName"],
                    "base": pr["baseRefName"],
                    "url": pr["url"],
                })
    return freeze_prs


def retrigger_via_empty_commit(repo, branch):
    """Push an empty commit to the branch to force a workflow re-run."""
    # Use the API to create a commit
    # Get the current SHA of the branch
    result = subprocess.run([
        "gh", "api", f"/repos/{ORG}/{repo}/git/ref/heads/{branch}",
        "--jq", ".object.sha",
    ], capture_output=True, text=True)
    if result.returncode != 0:
        return False, f"Could not get branch SHA: {result.stderr}"
    parent_sha = result.stdout.strip()

    # Create a blob for the empty commit
    # Actually use the simpler approach: use git on a temporary clone
    # Or use the Git Data API to create a commit
    # The simpler approach: use the gh CLI to create a commit via the contents API
    # But that creates a file change, not an empty commit.
    # Let's use git directly through a temp clone.

    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        # Clone the repo
        clone_result = subprocess.run([
            "gh", "repo", "clone", f"{ORG}/{repo}", tmpdir,
        ], capture_output=True, text=True, cwd=tmpdir)
        if clone_result.returncode != 0:
            # gh repo clone doesn't accept cwd that way; use git clone
            clone_result = subprocess.run([
                "git", "clone", "--depth=1", f"https://github.com/{ORG}/{repo}.git", "repo",
            ], capture_output=True, text=True, cwd=tmpdir)
            if clone_result.returncode != 0:
                return False, f"Could not clone: {clone_result.stderr}"

        repo_dir = os.path.join(tmpdir, "repo")
        # Configure git to allow push
        subprocess.run(["git", "config", "user.name", "alejandro.velasco@tendev.ai"],
                      cwd=repo_dir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "alejandro.velasco@tendev.ai"],
                      cwd=repo_dir, capture_output=True)
        # Checkout the branch
        checkout = subprocess.run(["git", "checkout", branch],
                                  cwd=repo_dir, capture_output=True, text=True)
        if checkout.returncode != 0:
            return False, f"Could not checkout {branch}: {checkout.stderr}"
        # Empty commit
        commit = subprocess.run(["git", "commit", "--allow-empty", "-m", COMMIT_MESSAGE],
                               cwd=repo_dir, capture_output=True, text=True)
        if commit.returncode != 0:
            return False, f"Could not create commit: {commit.stderr}"
        # Push
        push = subprocess.run(["git", "push", "origin", branch],
                             cwd=repo_dir, capture_output=True, text=True)
        if push.returncode != 0:
            return False, f"Could not push: {push.stderr}"
    return True, None


def main():
    parser = argparse.ArgumentParser(
        description="Push no-op commits to all open freeze PRs to re-trigger workflows"
    )
    parser.add_argument("--apply", action="store_true", help="Actually push commits (default: dry-run)")
    args = parser.parse_args()

    print("Finding open freeze PRs...")
    prs = find_freeze_prs()
    print(f"Found {len(prs)} open PRs with the freeze caller workflow branch")
    print()

    for pr in prs:
        print(f"  - {pr['repo']} #{pr['number']} ({pr['branch']} -> {pr['base']})  {pr['url']}")
    print()

    if not args.apply:
        print("*** DRY RUN MODE — use --apply to actually push commits ***")
        print()
        print("After confirming the ruleset is correct in the UI, re-run with --apply")
        return

    print("Pushing no-op commits to force workflow re-evaluation...")
    print()

    success = 0
    failed = 0
    for pr in prs:
        print(f"  [{pr['repo']}#{pr['number']}]", end=" ")
        ok, err = retrigger_via_empty_commit(pr["repo"], pr["branch"])
        if ok:
            print("pushed empty commit ✓")
            success += 1
        else:
            print(f"FAILED: {err}")
            failed += 1

    print()
    print(f"Done. {success} succeeded, {failed} failed.")
    if failed > 0:
        print("For the failed ones, push manually:")
        print("  git clone https://github.com/Ten-Developments/<repo>")
        print("  cd <repo>")
        print("  git checkout freeze/add-caller-workflow")
        print("  git commit --allow-empty -m 'chore: retrigger freeze-check'")
        print("  git push origin freeze/add-caller-workflow")


if __name__ == "__main__":
    main()

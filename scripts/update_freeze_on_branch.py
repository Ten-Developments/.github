"""
update_freeze_on_branch.py

Pushes the updated merge-freeze.yml to a specific branch of a repo.
Needed when the caller workflow exists on non-default branches (like develop)
and needs to be updated there too.

Usage:
    python update_freeze_on_branch.py devremote develop
    python update_freeze_on_branch.py core develop
"""

import base64
import json
import os
import subprocess
import sys
import tempfile

ORG = "Ten-Developments"
FILE_PATH = ".github/workflows/merge-freeze.yml"
COMMIT_MSG = "fix: restrict freeze check to PRs targeting main only"

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
    if len(sys.argv) < 3:
        print("Usage: python update_freeze_on_branch.py <repo> <branch>")
        sys.exit(1)

    repo = sys.argv[1]
    branch = sys.argv[2]

    print(f"Updating {FILE_PATH} on {ORG}/{repo}@{branch}")

    # Get current file SHA
    result, _ = run_gh([
        "api", f"/repos/{ORG}/{repo}/contents/{FILE_PATH}?ref={branch}",
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
            "-F", f"branch={branch}",
            "-F", f"sha={sha}",
        ], check=False)
    else:
        print(f"  File doesn't exist, creating...")
        result, err = run_gh([
            "api", "-X", "PUT",
            f"/repos/{ORG}/{repo}/contents/{FILE_PATH}",
            "-F", f"message={COMMIT_MSG}",
            "-F", f"content=@{b64_file}",
            "-F", f"branch={branch}",
        ], check=False)

    os.unlink(b64_file)

    if err:
        print(f"  ERROR: {err}")
        sys.exit(1)
    print(f"  Done.")


if __name__ == "__main__":
    main()

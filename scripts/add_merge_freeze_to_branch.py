import base64
import subprocess
import sys

REPO = "Ten-Developments"
REPO_NAME = sys.argv[1] if len(sys.argv) > 1 else "devremote"
BRANCH = sys.argv[2] if len(sys.argv) > 2 else "develop"
FILE_PATH = ".github/workflows/merge-freeze.yml"

# Read the latest version from the local .github repo
with open(r"C:\tendevelopments\code\ten-github-org\.github\workflows\merge-freeze.yml", "rb") as f:
    content_bytes = f.read()
b64_content = base64.b64encode(content_bytes).decode("utf-8")

print(f"Adding {FILE_PATH} to {REPO}/{REPO_NAME}@{BRANCH}")
print(f"  Content: {len(content_bytes)} bytes")

# Check if file already exists on branch
result = subprocess.run([
    "gh", "api",
    f"/repos/{REPO}/{REPO_NAME}/contents/{FILE_PATH}?ref={BRANCH}",
    "--jq", ".sha"
], capture_output=True, text=True)

if result.returncode == 0 and result.stdout.strip():
    # File exists, update it
    existing_sha = result.stdout.strip()
    print(f"  File exists (sha={existing_sha[:7]}), updating...")
    result = subprocess.run([
        "gh", "api", "-X", "PUT",
        f"/repos/{REPO}/{REPO_NAME}/contents/{FILE_PATH}",
        "-f", "message=feat: add merge-freeze caller workflow to develop branch",
        "-f", f"content={b64_content}",
        "-f", f"branch={BRANCH}",
        "-f", f"sha={existing_sha}",
    ], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr}")
        sys.exit(1)
    print(f"  Updated {FILE_PATH} on {BRANCH}")
else:
    # File doesn't exist, create it
    print(f"  File doesn't exist, creating...")
    result = subprocess.run([
        "gh", "api", "-X", "PUT",
        f"/repos/{REPO}/{REPO_NAME}/contents/{FILE_PATH}",
        "-f", "message=feat: add merge-freeze caller workflow to develop branch",
        "-f", f"content={b64_content}",
        "-f", f"branch={BRANCH}",
    ], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr}")
        sys.exit(1)
    print(f"  Created {FILE_PATH} on {BRANCH}")

print()
print("Done. The freeze-check workflow should run on the next PR event or cron tick.")

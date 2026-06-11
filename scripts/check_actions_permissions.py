"""
check_actions_permissions.py

Checks if GitHub Actions is enabled for all consumer repos in the
Ten-Developments org. A repo with Actions disabled will silently
ignore all pull_request and schedule workflow triggers.

Usage:
    python check_actions_permissions.py
"""

import json
import subprocess
import sys

ORG = "Ten-Developments"
SKIP_REPOS = {".github", "business-hydrology-frontpage"}


def main():
    result = subprocess.run(
        ["gh", "repo", "list", ORG, "--limit", "200", "--json", "name"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    repos = json.loads(result.stdout)

    print(f"Checking Actions permissions for {len(repos)} repos in {ORG}...")
    print()

    disabled = []
    enabled = []
    for repo in repos:
        name = repo["name"]
        if name in SKIP_REPOS:
            continue
        result = subprocess.run([
            "gh", "api", f"/repos/{ORG}/{name}/actions/permissions"
        ], capture_output=True, text=True)
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            print(f"  {name}: ERROR (could not parse response)")
            continue
        is_enabled = data.get("enabled", True)
        if is_enabled:
            enabled.append(name)
        else:
            disabled.append(name)

    print(f"Enabled: {len(enabled)}")
    for name in enabled:
        print(f"  [OK]      {name}")
    print()
    print(f"DISABLED: {len(disabled)}")
    for name in disabled:
        print(f"  [ACTION]  {name}")
    print()
    if disabled:
        print("Repos with Actions disabled need manual fix:")
        print("  1. Go to https://github.com/Ten-Developments/<repo>/settings/actions")
        print("  2. Select 'Allow all actions and reusable workflows'")
        print("  3. Save")
    else:
        print("All repos have Actions enabled.")


if __name__ == "__main__":
    main()

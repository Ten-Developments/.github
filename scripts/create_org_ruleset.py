"""
create_org_ruleset.py

Creates the 'Branch Freeze Policy' Org Ruleset for Ten-Developments.

The Org Ruleset is what physically blocks the merge button during frozen
windows. The workflow files alone don't enforce anything — the ruleset
references the `freeze-check` status check as a required check.

Prerequisites:
    gh CLI must be authenticated with the `admin:org` scope:
        gh auth refresh -h github.com -s admin:org

Usage:
    # Preview what would be created (no API calls)
    python create_org_ruleset.py --dry-run

    # Create the ruleset
    python create_org_ruleset.py

    # Delete the ruleset (for rollback / testing)
    python create_org_ruleset.py --delete

Configuration (edit these to change the policy):
"""

import argparse
import json
import subprocess
import sys

ORG = "Ten-Developments"

# The ruleset definition. Edit here if you want to change the policy.
RULESET_DEF = {
    "name": "Branch Freeze Policy",
    "target": "branch",
    "enforcement": "active",
    "conditions": {
        "ref_name": {
            "include": ["~DEFAULT_BRANCH", "refs/heads/main", "refs/heads/develop"],
            "exclude": []
        },
        "repository_name": {
            "include": [],
            "exclude": []
        }
    },
    "rules": [
        {
            "type": "required_status_checks",
            "parameters": {
                "strict_required_status_checks_policy": False,
                "required_status_checks": [
                    {
                        "context": "freeze-check",
                        "integration_id": None
                    }
                ]
            }
        },
        {
            "type": "non_fast_forward"
        }
    ],
    "bypass_actors": [
        {
            "actor_id": 2,   # 2 = Organization Admin role (GitHub's internal role ID)
            "actor_type": "OrganizationRole",
            "bypass_mode": "always"
        }
    ]
}


def gh_api(method, endpoint, data=None):
    """Run gh api and return parsed JSON."""
    cmd = ["gh", "api", method, endpoint]
    if data is not None:
        cmd.extend(["--input", "-"])
    result = subprocess.run(cmd, input=json.dumps(data) if data else None,
                            capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: gh api {method} {endpoint}")
        print(f"  stderr: {result.stderr}")
        if result.stdout:
            print(f"  stdout: {result.stdout}")
        sys.exit(1)
    if result.stdout.strip():
        return json.loads(result.stdout)
    return None


def list_rulesets():
    return gh_api("GET", f"/orgs/{ORG}/rulesets")


def find_ruleset_by_name(name):
    rulesets = list_rulesets()
    for r in rulesets:
        if r.get("name") == name:
            return r
    return None


def create_ruleset():
    existing = find_ruleset_by_name(RULESET_DEF["name"])
    if existing:
        print(f"Ruleset {RULESET_DEF['name']!r} already exists (id={existing['id']}).")
        print("Use --delete first if you want to recreate it.")
        return existing
    print(f"Creating ruleset {RULESET_DEF['name']!r}...")
    result = gh_api("POST", f"/orgs/{ORG}/rulesets", RULESET_DEF)
    print(f"Created ruleset id={result['id']}")
    return result


def delete_ruleset(ruleset_id):
    print(f"Deleting ruleset id={ruleset_id}...")
    result = subprocess.run(
        ["gh", "api", "DELETE", f"/orgs/{ORG}/rulesets/{ruleset_id}"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}")
        sys.exit(1)
    print("Deleted.")


def main():
    parser = argparse.ArgumentParser(description="Manage the Branch Freeze Policy ruleset")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created")
    parser.add_argument("--delete", action="store_true", help="Delete the existing ruleset")
    args = parser.parse_args()

    if args.dry_run:
        print("=== DRY RUN: would create the following ruleset ===")
        print(json.dumps(RULESET_DEF, indent=2))
        print()
        print("Existing rulesets:")
        try:
            for r in list_rulesets():
                print(f"  - id={r['id']} name={r['name']!r} enforcement={r['enforcement']}")
        except SystemExit:
            print("  (could not list — missing admin:org scope)")
            print()
            print("To enable:")
            print("  gh auth refresh -h github.com -s admin:org")
        return

    if args.delete:
        existing = find_ruleset_by_name(RULESET_DEF["name"])
        if not existing:
            print(f"Ruleset {RULESET_DEF['name']!r} does not exist.")
            return
        confirm = input(f"Delete ruleset id={existing['id']}? (y/n): ")
        if confirm.lower() != "y":
            print("Aborted.")
            return
        delete_ruleset(existing["id"])
        return

    # Create
    create_ruleset()


if __name__ == "__main__":
    main()

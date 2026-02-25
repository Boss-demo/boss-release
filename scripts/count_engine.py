import requests
import re
import os
import json

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
ORG = "Boss-demo"

REPOS = [
    "auth-service",
    "payment-service",
    "order-service",
    "inventory-service",
    "notification-service"
]

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

def get_latest_release(repo):
    url = f"https://api.github.com/repos/{ORG}/{repo}/releases/latest"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to fetch {repo}")
        return None
    return response.json()["tag_name"]

def parse_tag(tag):
    """
    Example: v1.2.3-tier2
    """
    match = re.match(r"v(\d+)\.(\d+)\.(\d+)-(tier\d)", tag)
    if not match:
        return None

    major, minor, patch, tier = match.groups()
    return {
        "major": int(major),
        "minor": int(minor),
        "patch": int(patch),
        "tier": tier
    }

def classify_change(version):
    """
    Simple classification:
    If patch > 0 → patch
    If minor > 0 → minor
    If major > 0 → major
    (Later we refine by comparing previous tag)
    """
    if version["major"] > 0:
        return "major"
    elif version["minor"] > 0:
        return "minor"
    else:
        return "patch"

def main():
    counts = {
        "tier1": {"major": 0, "minor": 0, "patch": 0},
        "tier2": {"major": 0, "minor": 0, "patch": 0},
        "tier3": {"major": 0, "minor": 0, "patch": 0},
    }

    for repo in REPOS:
        tag = get_latest_release(repo)
        if not tag:
            continue

        parsed = parse_tag(tag)
        if not parsed:
            continue

        tier = parsed["tier"]
        impact = classify_change(parsed)

        counts[tier][impact] += 1

    print("Tier Count Summary:")
    print(counts)

    # ✅ Write manifest properly here
    with open("boss-manifest.json", "w") as f:
        json.dump(counts, f, indent=2)

    

if __name__ == "__main__":
    main()


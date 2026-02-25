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

# -------------------------
# Fetch Latest Tag
# -------------------------
def get_latest_release(repo):
    url = f"https://api.github.com/repos/{ORG}/{repo}/releases/latest"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None
    return response.json()["tag_name"]

# -------------------------
# Parse Tag
# -------------------------
def parse_tag(tag):
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

# -------------------------
# Classify Change
# -------------------------
def classify_change(version):
    if version["major"] > 0:
        return "major"
    elif version["minor"] > 0:
        return "minor"
    else:
        return "patch"

# -------------------------
# Decision Engine
# -------------------------
def apply_threshold_logic(counts, current_version):
    boss_major, boss_minor, boss_incremental = current_version

    # Always increment incremental
    boss_incremental += 1

    # Tier1 rules
    if counts["tier1"]["major"] >= 1:
        boss_major += 1
        boss_minor = 0
        boss_incremental = 0

    elif counts["tier1"]["minor"] >= 1:
        boss_minor += 1
        boss_incremental = 0

    # Tier2 rules
    elif counts["tier2"]["major"] >= 2:
        boss_major += 1
        boss_minor = 0
        boss_incremental = 0

    elif counts["tier2"]["major"] >= 1:
        boss_minor += 1
        boss_incremental = 0

    elif counts["tier2"]["minor"] >= 2:
        boss_minor += 1
        boss_incremental = 0

    # Tier3 rules
    elif counts["tier3"]["major"] >= 1:
        boss_minor += 1
        boss_incremental = 0

    elif counts["tier3"]["minor"] >= 3:
        boss_minor += 1
        boss_incremental = 0

    return boss_major, boss_minor, boss_incremental

def get_latest_boss_tag():
    url = f"https://api.github.com/repos/{ORG}/boss-release/releases/latest"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return (1, 0, 0)  # default if first release

    tag = response.json()["tag_name"]
    match = re.match(r"v(\d+)\.(\d+)\.(\d+)", tag)

    if not match:
        return (1, 0, 0)

    return tuple(map(int, match.groups()))
# -------------------------
# Main
# -------------------------
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

    # Example current BOSS version (temporary hardcoded)
    current_version = get_latest_boss_tag()

    new_version = apply_threshold_logic(counts, current_version)

    print("New BOSS Version:", f"{new_version[0]}.{new_version[1]}.{new_version[2]}")

    manifest = {
        "counts": counts,
        "boss_version": f"{new_version[0]}.{new_version[1]}.{new_version[2]}"
    }

    with open("boss-manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

if __name__ == "__main__":
    main()
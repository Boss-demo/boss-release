import requests
import re
import os
import json

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
ORG = "Boss-demo"
STATE_FILE = "boss-state.json"

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
# Helpers
# -------------------------

def get_latest_release(repo):
    url = f"https://api.github.com/repos/{ORG}/{repo}/releases/latest"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None
    return response.json()["tag_name"]

def parse_tag(tag):
    match = re.match(r"v(\d+)\.(\d+)\.(\d+)-(tier\d)", tag)
    if not match:
        return None
    major, minor, patch, tier = match.groups()
    return int(major), int(minor), int(patch), tier

def classify_delta(old, new):
    old_major, old_minor, old_patch, _ = parse_tag(old)
    new_major, new_minor, new_patch, _ = parse_tag(new)

    if new_major > old_major:
        return "major"
    elif new_minor > old_minor:
        return "minor"
    elif new_patch > old_patch:
        return "patch"
    return None

def load_state():
    if not os.path.exists(STATE_FILE):
        return {"boss_version": "1.0.0", "last_processed_tags": {}}
    with open(STATE_FILE, "r") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def create_boss_release(version):
    url = f"https://api.github.com/repos/{ORG}/boss-release/releases"
    payload = {
        "tag_name": f"v{version}",
        "name": f"v{version}",
        "body": "Auto-generated BOSS release",
        "draft": False,
        "prerelease": False
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code in [200, 201]:
        print("BOSS Release Created Successfully")
    else:
        print("Release creation skipped or failed:", response.text)

# -------------------------
# Threshold Logic
# -------------------------

def apply_threshold_logic(counts, current_version, any_repo_changed):
    major, minor, inc = current_version

    if not any_repo_changed:
        return major, minor, inc

    # Always increment incremental first
    inc += 1

    # Tier1
    if counts["tier1"]["major"] >= 1:
        major += 1
        minor = 0
        inc = 0

    elif counts["tier1"]["minor"] >= 1:
        minor += 1
        inc = 0

    # Tier2
    elif counts["tier2"]["major"] >= 2:
        major += 1
        minor = 0
        inc = 0

    elif counts["tier2"]["major"] >= 1:
        minor += 1
        inc = 0

    elif counts["tier2"]["minor"] >= 2:
        minor += 1
        inc = 0

    # Tier3
    elif counts["tier3"]["major"] >= 1:
        minor += 1
        inc = 0

    elif counts["tier3"]["minor"] >= 3:
        minor += 1
        inc = 0

    return major, minor, inc

# -------------------------
# Main Engine
# -------------------------

def main():
    state = load_state()

    current_version_tuple = tuple(map(int, state["boss_version"].split(".")))
    old_version_str = state["boss_version"]

    last_tags = state["last_processed_tags"]

    counts = {
        "tier1": {"major": 0, "minor": 0, "patch": 0},
        "tier2": {"major": 0, "minor": 0, "patch": 0},
        "tier3": {"major": 0, "minor": 0, "patch": 0},
    }

    any_repo_changed = False

    for repo in REPOS:
        latest_tag = get_latest_release(repo)
        if not latest_tag:
            continue

        parsed = parse_tag(latest_tag)
        if not parsed:
            continue

        tier = parsed[3]

        if repo not in last_tags:
            counts[tier]["major"] += 1
            any_repo_changed = True
        else:
            delta = classify_delta(last_tags[repo], latest_tag)
            if delta:
                counts[tier][delta] += 1
                any_repo_changed = True

        last_tags[repo] = latest_tag

    print("Delta Counts:", counts)

    new_version_tuple = apply_threshold_logic(
        counts,
        current_version_tuple,
        any_repo_changed
    )

    new_version_str = f"{new_version_tuple[0]}.{new_version_tuple[1]}.{new_version_tuple[2]}"

    print("Old Version:", old_version_str)
    print("New Version:", new_version_str)

    if new_version_str != old_version_str:
        print("Version changed. Creating BOSS release...")
        create_boss_release(new_version_str)

    state["boss_version"] = new_version_str
    state["last_processed_tags"] = last_tags

    save_state(state)

if __name__ == "__main__":
    main()
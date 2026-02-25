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

# -------------------------
# Threshold Logic
# -------------------------

def apply_threshold_logic(counts, current_version, any_repo_changed):
    major, minor, inc = current_version

    if not any_repo_changed:
        return major, minor, inc  # no change

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

    current_boss_version = tuple(map(int, state["boss_version"].split(".")))
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
            # first time seen → treat as change
            counts[tier]["major"] += 1
            any_repo_changed = True
        else:
            delta = classify_delta(last_tags[repo], latest_tag)
            if delta:
                counts[tier][delta] += 1
                any_repo_changed = True

        last_tags[repo] = latest_tag

    print("Delta Counts:", counts)

    new_version = apply_threshold_logic(counts, current_boss_version, any_repo_changed)

    print("New BOSS Version:", f"{new_version[0]}.{new_version[1]}.{new_version[2]}")

    state["boss_version"] = f"{new_version[0]}.{new_version[1]}.{new_version[2]}"
    state["last_processed_tags"] = last_tags

    save_state(state)

if __name__ == "__main__":
    main()
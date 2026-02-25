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

def get_release_details(repo):
    url = f"https://api.github.com/repos/{ORG}/{repo}/releases/latest"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return None

    data = response.json()

    return {
        "service": repo,
        "version": data.get("tag_name"),
        "notes": data.get("body") or "No release notes provided."
    }


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


def detect_priority_override(repo):
    url = f"https://api.github.com/repos/{ORG}/{repo}/commits"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return False

    commits = response.json()

    for commit in commits[:5]:
        message = commit["commit"]["message"].lower()
        if "[priority:critical]" in message:
            return True

    return False


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"boss_version": "1.0.0", "last_processed_tags": {}}
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def generate_release_body(version, counts, changed_services):
    body = f"# BOSS v{version}\n\n"
    body += "## Tier Impact Summary\n"
    body += f"- Tier1: {counts['tier1']}\n"
    body += f"- Tier2: {counts['tier2']}\n"
    body += f"- Tier3: {counts['tier3']}\n\n"

    body += "## Changed Services\n\n"

    for svc in changed_services:
        body += f"### {svc['service']} ({svc['version']})\n"
        body += f"{svc['notes']}\n\n"

    return body


def create_boss_release(version, body):
    url = f"https://api.github.com/repos/{ORG}/boss-release/releases"

    payload = {
        "tag_name": f"v{version}",
        "name": f"v{version}",
        "body": body,
        "draft": False,
        "prerelease": False
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code in [200, 201]:
        print("BOSS Release Created Successfully")
    else:
        print("Release creation failed:", response.text)


# -------------------------
# Threshold Logic
# -------------------------

def apply_threshold_logic(counts, current_version, any_repo_changed):
    major, minor, inc = current_version

    if not any_repo_changed:
        return major, minor, inc

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
    changed_services = []

    # -------------------------
    # Priority Override Check
    # -------------------------

    priority_override = False

    for repo in REPOS:
        if detect_priority_override(repo):
            priority_override = True
            print(f"Priority override detected in {repo}")
            break

    # -------------------------
    # Delta Detection
    # -------------------------

    for repo in REPOS:
        release_details = get_release_details(repo)
        if not release_details:
            continue

        latest_tag = release_details["version"]
        parsed = parse_tag(latest_tag)
        if not parsed:
            continue

        tier = parsed[3]

        if repo not in last_tags:
            counts[tier]["major"] += 1
            any_repo_changed = True
            changed_services.append(release_details)
        else:
            delta = classify_delta(last_tags[repo], latest_tag)
            if delta:
                counts[tier][delta] += 1
                any_repo_changed = True
                changed_services.append(release_details)

        last_tags[repo] = latest_tag

    print("Delta Counts:", counts)

    # -------------------------
    # Version Decision
    # -------------------------

    if priority_override:
        major, minor, inc = current_version_tuple
        major += 1
        minor = 0
        inc = 0
        new_version_tuple = (major, minor, inc)
    else:
        new_version_tuple = apply_threshold_logic(
            counts,
            current_version_tuple,
            any_repo_changed
        )

    new_version_str = f"{new_version_tuple[0]}.{new_version_tuple[1]}.{new_version_tuple[2]}"

    print("Old Version:", old_version_str)
    print("New Version:", new_version_str)

    # -------------------------
    # Release Creation
    # -------------------------

    if new_version_str != old_version_str:
        release_body = generate_release_body(
            new_version_str,
            counts,
            changed_services
        )
        create_boss_release(new_version_str, release_body)

    state["boss_version"] = new_version_str
    state["last_processed_tags"] = last_tags

    save_state(state)


if __name__ == "__main__":
    main()
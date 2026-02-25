import requests
import json
import os
from datetime import datetime, timezone

# -----------------------------
# Load configs
# -----------------------------
with open("config/services.json") as f:
    services_cfg = json.load(f)

with open("config/thresholds.json") as f:
    thresholds = json.load(f)

ORG = services_cfg["org"]
REPOS = services_cfg["repos"]
TOKEN = os.environ.get("GITHUB_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json"
}

# -----------------------------
# Helper: get latest tag
# -----------------------------
def get_latest_release(repo):
    url = f"https://api.github.com/repos/{ORG}/{repo}/releases/latest"
    r = requests.get(url, headers=HEADERS)

    if r.status_code != 200:
        return None

    data = r.json()
    return {
        "service": repo,
        "version": data.get("tag_name"),
        "published_at": data.get("published_at")
    }

# -----------------------------
# Helper: classify bump
# -----------------------------
def classify(version):
    if not version:
        return "patch"

    v = version.lstrip("v").split(".")
    major, minor, patch = map(int, v)

    if major > 1:
        return "major"
    elif minor > 0:
        return "minor"
    else:
        return "patch"

# -----------------------------
# Collect releases
# -----------------------------
results = []

for repo in REPOS:
    rel = get_latest_release(repo)
    if rel:
        rel["bump"] = classify(rel["version"])
        results.append(rel)

# -----------------------------
# Count bumps
# -----------------------------
counts = {"major": 0, "minor": 0, "patch": 0}

for r in results:
    counts[r["bump"]] += 1

# -----------------------------
# Decide boss bump
# -----------------------------
boss_bump = "patch"

if counts["major"] >= thresholds["major"]:
    boss_bump = "major"
elif counts["minor"] >= thresholds["minor"]:
    boss_bump = "minor"

# -----------------------------
# Create manifest
# -----------------------------
manifest = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "counts": counts,
    "boss_bump": boss_bump,
    "services": results
}

# -----------------------------
# Write output
# -----------------------------
with open("boss-manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)

print("✅ Boss manifest generated")
print(json.dumps(manifest, indent=2))
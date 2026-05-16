"""Print flat keyword list from profile.json for Apify setup."""
import json
from pathlib import Path

profile = json.loads((Path(__file__).parent.parent / "profile.json").read_text(encoding="utf-8"))
clusters = profile.get("search_keyword_clusters", {})
flat = sorted({k for terms in clusters.values() for k in terms})
print(f"Total keywords: {len(flat)}")
for k in flat:
    print(k)

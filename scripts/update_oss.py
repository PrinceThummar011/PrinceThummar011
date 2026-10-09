#!/usr/bin/env python3
"""Auto-update the 'Open Source Contribution' section of the profile README.

Counts every public PR you opened on repos you do NOT own (total / merged /
open / closed-unmerged / repos) and shows the logo of each org you contributed to.
Result is written between <!--OSS-START--> and <!--OSS-END-->.
Standard library only - no pip install needed.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html import escape

USER = os.environ.get("GH_USER", "PrinceThummar011")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
README = os.environ.get("README_PATH", "README.md")
MAX_LOGOS = int(os.environ.get("MAX_LOGOS", "40"))
# Comma separated: "owner" or "owner/repo" to hide
EXCLUDE = {x.strip().lower() for x in os.environ.get("EXCLUDE", "").split(",") if x.strip()}

BLUE, GREEN, AMBER, RED, PURPLE = "378ADD", "2ea44f", "f0ad4e", "d73a4a", "8957e5"


def api(path, params=None, retries=3):
    url = "https://api.github.com" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USER}-readme-updater",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (403, 429) and attempt < retries - 1:
                time.sleep(30 * (attempt + 1))  # rate-limited: wait and retry
                continue
            raise
    return {}


def fetch_prs():
    q = f"author:{USER} type:pr is:public -user:{USER}"
    items, page = [], 1
    while page <= 10:  # search API returns at most 1000 results
        data = api("/search/issues", {"q": q, "per_page": 100, "page": page, "sort": "created", "order": "desc"})
        batch = data.get("items", [])
        items += batch
        if len(batch) < 100:
            break
        page += 1
        time.sleep(2)
    return items


def pr_state(item):
    if (item.get("pull_request") or {}).get("merged_at"):
        return "merged"
    return "open" if item["state"] == "open" else "closed"


def search_url(extra=""):
    q = f"is:pr author:{USER} -user:{USER}{extra}"
    return "https://github.com/search?" + urllib.parse.urlencode({"q": q, "type": "pullrequests"})


def badge(label, value, color, logo):
    label = label.replace("_", "__").replace("-", "--").replace(" ", "_")
    return (f"https://img.shields.io/badge/{label}-{value}-{color}"
            f"?style=for-the-badge&logo={logo}&logoColor=white")


def build(items):
    stats = {"merged": 0, "open": 0, "closed": 0}
    repos, owner_merged, owner_total = set(), {}, {}
    for it in items:
        full = it["repository_url"].split("/repos/")[1]
        owner = full.split("/")[0]
        if full.lower() in EXCLUDE or owner.lower() in EXCLUDE:
            continue
        s = pr_state(it)
        stats[s] += 1
        repos.add(full)
        owner_merged[owner] = owner_merged.get(owner, 0) + (s == "merged")
        owner_total[owner] = owner_total.get(owner, 0) + 1
    total = sum(stats.values())
    owners = sorted(owner_total, key=lambda o: (-owner_merged[o], -owner_total[o], o.lower()))

    L = ['<div align="center">', ""]
    L += [
        f'<a href="{search_url()}"><img src="{badge("TOTAL PRs", total, BLUE, "github")}" alt="Total PRs" /></a>',
        f'<a href="{search_url(" is:merged")}"><img src="{badge("MERGED", stats["merged"], GREEN, "git")}" alt="Merged" /></a>',
        f'<a href="{search_url(" is:open")}"><img src="{badge("OPEN", stats["open"], AMBER, "githubactions")}" alt="Open" /></a>',
        f'<a href="{search_url(" is:closed is:unmerged")}"><img src="{badge("CLOSED", stats["closed"], RED, "github")}" alt="Closed" /></a>',
        f'<a href="{search_url()}"><img src="{badge("REPOS", len(repos), PURPLE, "opensourceinitiative")}" alt="Repos" /></a>',
        "", "", "", "<br/>", "", "**Contributed to**", "", '<p align="center">',
    ]
    for o in owners[:MAX_LOGOS]:
        L.append(f'<a href="https://github.com/{o}"><img src="https://github.com/{o}.png?size=96" '
                 f'width="48" height="48" alt="{escape(o)}" title="{escape(o)}" /></a>&nbsp;')
    L += ["</p>", "", "</div>"]
    return "\n".join(L)


def main():
    text = open(README, encoding="utf-8").read()
    pattern = re.compile(r"(<!--OSS-START-->)(.*?)(<!--OSS-END-->)", re.S)
    if not pattern.search(text):
        sys.exit("Markers <!--OSS-START--> and <!--OSS-END--> not found in README")
    block = build(fetch_prs())
    new = pattern.sub(lambda m: f"{m.group(1)}\n{block}\n{m.group(3)}", text)
    if new != text:
        open(README, "w", encoding="utf-8").write(new)
        print("README updated")
    else:
        print("No changes")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Fetch all public repos in the ftsrg-papers org that have a
public-data.yml on their default branch, parse the YAML, and write
repos.json for the org index site.

Expected public-data.yml fields (all optional):
  title:    string
  authors:  string or list of strings
  doi:      string  (bare identifier or full https://doi.org/… URL)
  pdf:      string  (URL)
  slides:   string  (URL)
  mtmt:     string  (URL)
  abstract: string
  bibtex:   string
"""

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

try:
    import yaml
except ModuleNotFoundError:
    import subprocess
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--quiet", "pyyaml"]
    )
    import yaml  # type: ignore

ORG   = "ftsrg-papers"
SELF  = f"{ORG}.github.io"
TOKEN = os.environ.get("GH_TOKEN", "")


def _get(url: str):
    """GET *url* via the GitHub API; return parsed JSON or None on 404."""
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", f"{ORG}-index-workflow")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def get_all_public_repos() -> list:
    repos, page = [], 1
    while True:
        batch = _get(
            f"https://api.github.com/orgs/{ORG}/repos"
            f"?per_page=100&page={page}&type=public&sort=full_name"
        )
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return repos


def get_public_data(repo_name: str) -> dict | None:
    """Return parsed public-data.yml for *repo_name*, or None if absent/invalid."""
    meta = _get(
        f"https://api.github.com/repos/{ORG}/{repo_name}"
        f"/contents/public-data.yml"
    )
    if not meta or "content" not in meta:
        return None

    raw = base64.b64decode(meta["content"]).decode("utf-8")
    try:
        data = yaml.safe_load(raw)
        return data if isinstance(data, dict) else None
    except yaml.YAMLError as exc:
        print(
            f"  WARNING: could not parse public-data.yml for {repo_name}: {exc}",
            file=sys.stderr,
        )
        return None


def main() -> None:
    print(f"Fetching public repos for org '{ORG}'…")
    all_repos = get_all_public_repos()
    print(f"  {len(all_repos)} public repos found.")

    entries = []
    for repo in all_repos:
        name: str = repo["name"]
        if name == SELF:
            continue

        print(f"  {name}: ", end="", flush=True)
        public_data = get_public_data(name)
        if public_data is None:
            print("no public-data.yml — skipped.")
            continue

        print("included.")
        entries.append({
            "name":        name,
            "html_url":    repo["html_url"],
            "public_data": public_data,
        })

    entries.sort(key=lambda r: r["name"].casefold())

    output = {
        "org":     ORG,
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repos":   entries,
    }

    with open("repos.json", "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print(f"\nWrote {len(entries)} repositories to repos.json.")


if __name__ == "__main__":
    main()

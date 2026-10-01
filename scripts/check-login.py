#!/usr/bin/env python3
"""check-login — is a stored-credential library login already set up on this machine?

    ./fw check-login            list every configured site
    ./fw check-login <site>     check one site
    ./fw check-login --json     machine-readable

Run it BEFORE asking the author to sign in to a library proxy. Exit 0 means the
site has a login recipe and a filled credential file, so the author has already
done their part: sign in with the optional `authenticated-fetch` integration
(`login <site> "<source-url>"`) and download without waiting for them. Exit 1
means nothing usable is configured (the reason is printed); only then ask.

It reads the `authenticated-fetch` user configuration, not the skill itself:
recipes in $AUTHENTICATED_FETCH_SITES or ~/.config/authenticated-fetch/sites,
each naming a KEY=value credential file. The file is opened only to see that
both values are present. No value is ever printed, and nothing is created.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

RECIPE_KEYS = ("entry", "credentials", "user_key", "pass_key", "user", "password", "submit", "success_url")


def sites_dir() -> Path:
    return Path(os.environ.get("AUTHENTICATED_FETCH_SITES") or "~/.config/authenticated-fetch/sites").expanduser()


def state(path: Path) -> dict:
    entry = {"site": path.stem, "configured": False}
    try:
        recipe = json.loads(path.read_text(encoding="utf-8"))
        missing = [key for key in RECIPE_KEYS if not recipe.get(key)]
        if missing:
            raise ValueError("recipe lacks: " + ", ".join(missing))
        file = Path(recipe["credentials"]).expanduser()
        if not file.is_file():
            raise ValueError(f"no credential file at {file}")
        if file.stat().st_mode & 0o077:
            raise ValueError(f"{file} is readable by other accounts (chmod 600)")
        values = dict(line.split("=", 1) for line in file.read_text(encoding="utf-8").splitlines()
                      if "=" in line and not line.lstrip().startswith("#"))
        if not all(values.get(recipe[key], "").strip() for key in ("user_key", "pass_key")):
            raise ValueError(f"{file} has an empty {recipe['user_key']} or {recipe['pass_key']}")
        entry["configured"] = True
    except (OSError, ValueError) as error:
        entry["reason"] = str(error)
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("site", nargs="?", help="recipe name; default: all")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = sites_dir()
    found = [state(path) for path in sorted(root.glob("*.json"))] if root.is_dir() else []
    if args.site:
        found = [entry for entry in found if entry["site"] == args.site] or [
            {"site": args.site, "configured": False, "reason": f"no recipe at {root / (args.site + '.json')}"}]
    ready = any(entry["configured"] for entry in found)
    if args.json:
        print(json.dumps({"sites_dir": str(root), "sites": found, "ready": ready}, ensure_ascii=False))
    else:
        for entry in found:
            print(f"{entry['site']}: " + ("configured — sign in with it, do not wait for the author"
                                          if entry["configured"] else "not configured — " + entry["reason"]))
        if not found:
            print(f"no login recipes in {root} — ask the author to sign in by hand, or to set one up")
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())

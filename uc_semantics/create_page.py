#!/usr/bin/env python3
"""
Create or update a UC semantics Page from a Markdown file, plus its asset links.

    python3 uc_semantics/create_page.py --profile <PROFILE> [--md <file>] [--publish] [--dry-run]

What it does:
  * Reads YAML frontmatter (display_name, domain, owner, state, synonyms,
    description, related_assets, sources). The Markdown after the
    frontmatter becomes the Page body.
  * Replaces __CATALOG__ / __SCHEMA__ with TARGET_CATALOG / TARGET_SCHEMA from .env or _env.
  * POST /api/2.0/knowledge/pages, or PATCH if the page was already created.
    The page name is cached in uc_semantics/.page_state.json.
  * Links each UC table/view under Related Assets / Sources
    (ASSET_TYPE_UC_TABLE, scope = current metastore ID).

Auth comes from the Databricks CLI profile. The Pages API is Beta.
"""
import argparse
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
STATE = HERE / ".page_state.json"


def load_env():
    env_file = ROOT / ".env" if (ROOT / ".env").exists() else ROOT / "_env"
    env = {}
    for line in env_file.read_text().splitlines():
        m = re.match(r'^\s*([A-Z_][A-Z0-9_]*)\s*=\s*"?([^"#]*)"?', line)
        if m:
            env[m.group(1)] = m.group(2).strip()
    return env


def parse_md(path, env):
    text = path.read_text()
    text = text.replace("__CATALOG__", env["TARGET_CATALOG"]).replace("__SCHEMA__", env["TARGET_SCHEMA"])
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        sys.exit(f"{path}: missing YAML frontmatter")
    return yaml.safe_load(m.group(1)), m.group(2).strip() + "\n"


def api(profile, method, path, body=None):
    cmd = ["databricks", "api", method, path, "--profile", profile, "--output", "json"]
    if body is not None:
        cmd += ["--json", json.dumps(body)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{method.upper()} {path} failed:\n{r.stderr or r.stdout}")
    return json.loads(r.stdout) if r.stdout.strip() else {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--md", default=str(HERE / "page_cold_chain_shipment_risk.md"))
    ap.add_argument("--publish", action="store_true", help="set state=PUBLISHED (needs MANAGE PAGES)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    env = load_env()
    meta, body = parse_md(Path(a.md), env)

    page = {
        "domain": meta["domain"],
        "display_name": meta["display_name"],
        "description": " ".join(meta.get("description", "").split()),
        "synonyms": meta.get("synonyms") or [],
        "body": body,
        "state": "PUBLISHED" if a.publish else meta.get("state", "DRAFT"),
    }
    if meta.get("owner"):
        page["owner_ids"] = [str(meta["owner"])]
    links = {"RELATED_ASSETS": meta.get("related_assets") or [], "SOURCE": meta.get("sources") or []}

    if a.dry_run:
        print(json.dumps({"page": page, "links": links}, indent=2))
        return

    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    key = f"{a.profile}:{a.md}"
    name = state.get(key)

    if name:
        mask = ",".join(page)
        print(f"Updating {name} ...")
        res = api(a.profile, "patch", f"/api/2.0/knowledge/{name}?update_mask={mask}", page)
    else:
        print(f"Creating page '{page['display_name']}' in {page['domain']} ...")
        res = api(a.profile, "post", f"/api/2.0/knowledge/pages?request_id={uuid.uuid4()}", page)
        name = res["name"]
        state[key] = name
        STATE.write_text(json.dumps(state, indent=2))
    print(f"  {res.get('name')}  state={res.get('state')}  updated={res.get('update_time')}")

    metastore_id = api(a.profile, "get", "/api/2.1/unity-catalog/current-metastore-assignment")["metastore_id"]
    for category, assets in links.items():
        for fqn in assets:
            try:
                api(a.profile, "post",
                    f"/api/2.0/knowledge/{name}/asset-link-categories/{category}/asset-links",
                    {"asset_type": "ASSET_TYPE_UC_TABLE", "asset_scope_id": metastore_id, "asset_id": fqn})
                print(f"  linked {category:<14} {fqn}")
            except RuntimeError as e:
                print(f"  WARN could not link {category} {fqn}: {e}".strip())

    host = subprocess.run(["databricks", "auth", "describe", "--profile", a.profile, "--output", "json"],
                          capture_output=True, text=True)
    try:
        h = json.loads(host.stdout)["details"]["host"].rstrip("/")
        print(f"\nOpen: {h}/discover/pages  (page {name.split('/')[-1]})")
    except Exception:
        pass


if __name__ == "__main__":
    main()

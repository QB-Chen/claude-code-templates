#!/usr/bin/env python3
"""
Generate a lean, agent-friendly catalog for GitHub Pages.

Scans cli-tool/components (+ templates) and writes:
  site/catalog.json  — machine index for coding agents
  site/llms.txt      — short human/LLM summary

Does NOT run security audit or download stats (those stay in generate_components_json.py).
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "cli-tool" / "components"
TEMPLATES = ROOT / "cli-tool" / "templates"
SITE = ROOT / "site"
OUT_CATALOG = SITE / "catalog.json"
OUT_LLMS = SITE / "llms.txt"

TYPE_LABELS = {
    "agents": "Agents",
    "commands": "Commands",
    "skills": "Skills",
    "mcps": "MCPs",
    "hooks": "Hooks",
    "settings": "Settings",
    "loops": "Loops",
    "sandbox": "Sandbox",
    "templates": "Project templates",
}

CLI_FLAGS = {
    "agents": "agent",
    "commands": "command",
    "skills": "skill",
    "mcps": "mcp",
    "hooks": "hook",
    "settings": "setting",
    "loops": "loop",
    "sandbox": "sandbox",
    "templates": "template",
}


def github_repo() -> str:
    env = os.environ.get("GITHUB_REPOSITORY")
    if env:
        return env
    try:
        import subprocess

        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        m = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", url)
        if m:
            return f"{m.group(1)}/{m.group(2)}"
    except Exception:
        pass
    return "QB-Chen/claude-code-templates"


def read_text(path: Path, limit: int = 80_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except OSError:
        return ""


def parse_frontmatter(text: str) -> dict:
    meta: dict = {}
    if not text.startswith("---"):
        return meta
    end = text.find("\n---", 3)
    if end == -1:
        return meta
    block = text[3:end]
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().lower()
        val = val.strip().strip('"').strip("'")
        if not key:
            continue
        if key in ("description", "name", "author", "version", "license", "repo"):
            meta[key] = val
        elif key in ("tags", "keywords"):
            inner = val.strip("[]")
            meta["tags"] = [t.strip().strip("\"'") for t in inner.split(",") if t.strip()]
    return meta


def clean_summary(raw: str, fallback: str, limit: int = 220) -> str:
    if not raw:
        return fallback
    s = raw
    # Unescape common sequences from frontmatter
    s = s.replace("\\n", " ").replace('\\"', '"')
    s = re.sub(r"<example>.*?</example>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<commentary>.*?</commentary>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip().strip('"').strip()
    if len(s) > limit:
        s = s[: limit - 3].rsplit(" ", 1)[0] + "..."
    return s or fallback


def first_paragraph_after_frontmatter(text: str) -> str:
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            body = text[end + 4 :]
    lines = []
    for line in body.splitlines():
        s = line.strip()
        if not s:
            if lines:
                break
            continue
        if s.startswith("#"):
            if lines:
                break
            continue
        if s.startswith("```"):
            break
        lines.append(s)
    return " ".join(lines)


def install_cmd(component_type: str, install_key: str) -> str:
    flag = CLI_FLAGS.get(component_type)
    if not flag:
        return f"npx claude-code-templates@latest  # {component_type}/{install_key}"
    return f"npx claude-code-templates@latest --{flag} {install_key} --yes"


def entry_from_md(
    *,
    path: Path,
    component_type: str,
    category: str,
    name: str,
    install_key: str,
    repo: str,
    branch: str,
) -> dict:
    rel = path.relative_to(ROOT).as_posix()
    text = read_text(path)
    meta = parse_frontmatter(text)
    display = meta.get("name") or name.replace("-", " ").replace("_", " ")
    summary = clean_summary(
        meta.get("description") or first_paragraph_after_frontmatter(text),
        f"{TYPE_LABELS.get(component_type, component_type)}: {name}",
    )
    tags = list(meta.get("tags") or [])
    tags.insert(0, component_type.rstrip("s") if component_type.endswith("s") else component_type)
    if category:
        tags.append(category)
    # de-dupe preserve order
    seen = set()
    tags = [t for t in tags if not (t in seen or seen.add(t))][:12]

    return {
        "id": f"{component_type}__{install_key.replace('/', '__')}",
        "name": display if len(display) < 80 else name,
        "slug": name,
        "type": component_type,
        "type_label": TYPE_LABELS.get(component_type, component_type),
        "category": category or "general",
        "path": rel,
        "install_key": install_key,
        "install": install_cmd(component_type, install_key),
        "summary": summary,
        "tags": tags,
        "github_url": f"https://github.com/{repo}/tree/{branch}/{rel}",
        "readme_url": f"https://raw.githubusercontent.com/{repo}/{branch}/{rel}",
    }


def entry_from_mcp_json(
    path: Path, category: str, name: str, repo: str, branch: str
) -> dict:
    rel = path.relative_to(ROOT).as_posix()
    install_key = f"{category}/{name}"
    summary = f"MCP integration: {name}"
    try:
        data = json.loads(read_text(path))
        servers = data.get("mcpServers") or data
        if isinstance(servers, dict) and servers:
            first = next(iter(servers.values()))
            if isinstance(first, dict) and first.get("description"):
                summary = clean_summary(str(first["description"]), summary)
    except json.JSONDecodeError:
        pass

    return {
        "id": f"mcps__{install_key.replace('/', '__')}",
        "name": name.replace("-", " "),
        "slug": name,
        "type": "mcps",
        "type_label": "MCPs",
        "category": category,
        "path": rel,
        "install_key": install_key,
        "install": install_cmd("mcps", install_key),
        "summary": summary,
        "tags": ["mcp", category],
        "github_url": f"https://github.com/{repo}/tree/{branch}/{rel}",
        "readme_url": f"https://raw.githubusercontent.com/{repo}/{branch}/{rel}",
    }


def _json_summary(path: Path, fallback: str) -> str:
    try:
        data = json.loads(read_text(path))
    except json.JSONDecodeError:
        return fallback
    if isinstance(data, dict):
        for key in ("description", "summary", "name"):
            if data.get(key) and isinstance(data[key], str):
                return clean_summary(data[key], fallback)
        # hooks often nest under a single key
        for v in data.values():
            if isinstance(v, dict) and isinstance(v.get("description"), str):
                return clean_summary(v["description"], fallback)
    return fallback


def scan_typed_components(component_type: str, repo: str, branch: str) -> list[dict]:
    """Scan agents/commands (md) and hooks/settings (json primary)."""
    base = COMPONENTS / component_type
    if not base.is_dir():
        return []
    items: list[dict] = []
    seen_keys: set[str] = set()

    patterns = ("*.md", "*.json") if component_type in ("hooks", "settings") else ("*.md",)
    paths: list[Path] = []
    for pat in patterns:
        paths.extend(base.rglob(pat))

    for path in sorted(set(paths), key=lambda p: str(p).lower()):
        if path.name.lower() in (
            "readme.md",
            "changelog.md",
            "package.json",
            "package-lock.json",
            "hook_patterns_compressed.json",
        ):
            continue
        # Prefer category/name leaf files; skip helper scripts next to json
        if path.suffix.lower() in (".py", ".sh", ".js", ".html"):
            continue

        rel = path.relative_to(base)
        parts = rel.parts
        if len(parts) == 1:
            # top-level meta files
            if path.suffix.lower() == ".json" and path.stem.isupper():
                continue
            category, name = "general", path.stem
            install_key = name
        else:
            category, name = parts[0], path.stem
            install_key = f"{category}/{name}"

        if install_key in seen_keys:
            continue
        seen_keys.add(install_key)

        if path.suffix.lower() == ".md":
            items.append(
                entry_from_md(
                    path=path,
                    component_type=component_type,
                    category=category,
                    name=name,
                    install_key=install_key,
                    repo=repo,
                    branch=branch,
                )
            )
        else:
            rel_repo = path.relative_to(ROOT).as_posix()
            summary = _json_summary(
                path, f"{TYPE_LABELS.get(component_type, component_type)}: {name}"
            )
            items.append(
                {
                    "id": f"{component_type}__{install_key.replace('/', '__')}",
                    "name": name.replace("-", " "),
                    "slug": name,
                    "type": component_type,
                    "type_label": TYPE_LABELS.get(component_type, component_type),
                    "category": category,
                    "path": rel_repo,
                    "install_key": install_key,
                    "install": install_cmd(component_type, install_key),
                    "summary": summary,
                    "tags": [
                        component_type.rstrip("s")
                        if component_type.endswith("s")
                        else component_type,
                        category,
                    ],
                    "github_url": f"https://github.com/{repo}/tree/{branch}/{rel_repo}",
                    "readme_url": f"https://raw.githubusercontent.com/{repo}/{branch}/{rel_repo}",
                }
            )
    return items

def scan_skills(repo: str, branch: str) -> list[dict]:
    base = COMPONENTS / "skills"
    if not base.is_dir():
        return []
    items: list[dict] = []
    for skill_md in sorted(base.rglob("SKILL.md")):
        # skills/category/skill-name/SKILL.md
        rel_parts = skill_md.relative_to(base).parts
        if len(rel_parts) < 2:
            continue
        category = rel_parts[0]
        name = rel_parts[-2] if len(rel_parts) >= 2 else skill_md.parent.name
        install_key = f"{category}/{name}"
        items.append(
            entry_from_md(
                path=skill_md,
                component_type="skills",
                category=category,
                name=name,
                install_key=install_key,
                repo=repo,
                branch=branch,
            )
        )
    return items


def scan_mcps(repo: str, branch: str) -> list[dict]:
    base = COMPONENTS / "mcps"
    if not base.is_dir():
        return []
    items: list[dict] = []
    for path in sorted(base.rglob("*.json")):
        if path.name in ("package.json", "package-lock.json"):
            continue
        rel = path.relative_to(base)
        parts = rel.parts
        if len(parts) < 2:
            category, name = "general", path.stem
        else:
            category, name = parts[0], path.stem
        items.append(entry_from_mcp_json(path, category, name, repo, branch))
    return items


def scan_templates(repo: str, branch: str) -> list[dict]:
    if not TEMPLATES.is_dir():
        return []
    items: list[dict] = []
    for path in sorted(TEMPLATES.rglob("README.md")):
        # templates/python/README.md → name=python
        rel = path.relative_to(TEMPLATES)
        if len(rel.parts) < 2:
            continue
        name = rel.parts[0]
        install_key = name
        items.append(
            entry_from_md(
                path=path,
                component_type="templates",
                category="templates",
                name=name,
                install_key=install_key,
                repo=repo,
                branch=branch,
            )
        )
    return items


def write_llms(items: list[dict], repo: str, pages_base: str) -> str:
    by_type: dict[str, list[dict]] = {}
    for it in items:
        by_type.setdefault(it["type"], []).append(it)

    lines = [
        "# Claude Code Templates - Agent Catalog",
        "",
        f"> Lean index of {len(items)} Claude Code components (agents, commands, skills, MCPs, hooks, settings, loops).",
        f"> Source: https://github.com/{repo}",
        f"> Official browse UI: https://aitmpl.com",
        "",
        "## For coding agents",
        "",
        "1. Fetch catalog JSON:",
        f"   - {pages_base}/catalog.json",
        "2. Filter by type/tags/category; pick 1-3 components.",
        "3. Install with the `install` field or read `readme_url` / `github_url`.",
        "",
        "## Key URLs",
        "",
        f"- [Human site]({pages_base}/)",
        f"- [catalog.json]({pages_base}/catalog.json)",
        f"- [llms.txt]({pages_base}/llms.txt)",
        f"- [AGENTS.md]({pages_base}/AGENTS.md)",
        "",
        "## Types",
        "",
    ]
    for t in sorted(by_type.keys(), key=lambda x: TYPE_LABELS.get(x, x)):
        bucket = by_type[t]
        lines.append(f"### {TYPE_LABELS.get(t, t)} ({len(bucket)})")
        lines.append("")
        for it in sorted(bucket, key=lambda x: x["name"].lower())[:25]:
            lines.append(
                f"- [{it['name']}]({it['github_url']}): {it['summary'][:140]} | `{it['install']}`"
            )
        if len(bucket) > 25:
            lines.append(f"- ... and {len(bucket) - 25} more — see catalog.json")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    repo = github_repo()
    owner, _, name = repo.partition("/")
    pages_base = os.environ.get(
        "PAGES_BASE_URL",
        f"https://{owner.lower()}.github.io/{name}" if owner and name else "https://qb-chen.github.io/claude-code-templates",
    )
    branch = os.environ.get("GITHUB_REF_NAME") or "main"

    items: list[dict] = []
    for t in ("agents", "commands", "hooks", "settings", "loops", "sandbox"):
        items.extend(scan_typed_components(t, repo, branch))
    items.extend(scan_skills(repo, branch))
    items.extend(scan_mcps(repo, branch))
    items.extend(scan_templates(repo, branch))

    items.sort(key=lambda x: (x["type"], x["category"], x["slug"]))

    type_counts = Counter(i["type"] for i in items)
    types = [
        {"id": t, "label": TYPE_LABELS.get(t, t), "count": c}
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1])
    ]
    tag_counts = Counter(tag for i in items for tag in i.get("tags") or [])
    cat_counts = Counter(i["category"] for i in items)

    catalog = {
        "version": "1.0",
        "kind": "claude-code-templates",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo": repo,
        "pages_base_url": pages_base,
        "official_site": "https://aitmpl.com",
        "install_cli": "npx claude-code-templates@latest",
        "item_count": len(items),
        "types": types,
        "top_tags": [{"tag": t, "count": c} for t, c in tag_counts.most_common(40)],
        "top_categories": [{"category": c, "count": n} for c, n in cat_counts.most_common(40)],
        "items": items,
    }

    SITE.mkdir(parents=True, exist_ok=True)
    OUT_CATALOG.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    OUT_LLMS.write_text(write_llms(items, repo, pages_base), encoding="utf-8")

    print(f"Wrote {OUT_CATALOG.relative_to(ROOT)} ({len(items)} items)")
    print(f"Wrote {OUT_LLMS.relative_to(ROOT)}")
    print(f"Repo: {repo}")
    print(f"Pages: {pages_base}")
    for t in types:
        print(f"  - {t['label']}: {t['count']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

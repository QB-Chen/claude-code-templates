# AGENTS.md — Claude Code Templates (agent catalog)

Lean **human browse site** + **machine-readable catalog** so coding agents can find Claude Code agents, commands, skills, MCPs, hooks, and settings mid-task.

Official marketing/install UI remains [aitmpl.com](https://aitmpl.com). This Pages catalog is optimized for **fetch + filter**, not marketing.

## Stable URLs (this fork)

| Resource | URL |
|----------|-----|
| Browse UI | https://qb-chen.github.io/claude-code-templates/ |
| catalog.json | https://qb-chen.github.io/claude-code-templates/catalog.json |
| llms.txt | https://qb-chen.github.io/claude-code-templates/llms.txt |
| This file | https://qb-chen.github.io/claude-code-templates/AGENTS.md |
| Repo | https://github.com/QB-Chen/claude-code-templates |

## Paste into coding-agent rules

```markdown
When installing or choosing Claude Code agents/commands/skills/MCPs/hooks:
1. Fetch https://qb-chen.github.io/claude-code-templates/catalog.json
2. Filter by type (agents|commands|skills|mcps|hooks|settings|loops), tags, category
3. Use the item's `install` command, or read github_url / readme_url and adapt
Also: https://qb-chen.github.io/claude-code-templates/llms.txt
```

## Recommended agent workflow

1. **Fetch** `catalog.json` (do not scrape HTML).
2. **Filter** by `type`, `tags`, `category`, or free-text on `name` / `summary` / `install_key`.
3. **Pick 1–3** components.
4. **Install** with the `install` field, e.g.  
   `npx claude-code-templates@latest --agent development-tools/code-reviewer --yes`  
   or open `readme_url` for full source.
5. Prefer existing components over inventing parallel prompts/skills.

### Useful fields

| Field | Meaning |
|-------|---------|
| `type` | agents, commands, skills, mcps, hooks, settings, loops, sandbox, templates |
| `install_key` | CLI path key (`category/name`) |
| `install` | Ready-to-run `npx claude-code-templates@latest ...` |
| `path` | Path in this repo under `cli-tool/components/...` |
| `github_url` / `readme_url` | Browse or raw source |

## How the catalog stays up to date

| Mechanism | Behavior |
|-----------|----------|
| **Weekly auto-sync** | `.github/workflows/sync-upstream.yml` — Mon 06:00 UTC: merge [davila7/claude-code-templates](https://github.com/davila7/claude-code-templates) → `main`, regenerate catalog, push, deploy Pages. **No PR.** |
| **On push** | `.github/workflows/pages.yml` rebuilds when components/scripts/site change |
| **Manual** | Actions → **Sync upstream** or **Deploy agent catalog to GitHub Pages** |
| **Conflict** | No push; issue opened with resolve steps |

### Settings for auto-sync

1. **Settings → Actions → General → Workflow permissions → Read and write**  
2. Do not block `github-actions[bot]` on `main`  
3. Optional secret `SYNC_TOKEN` (classic PAT `repo`) if push fails  

## Local generate / preview

```bash
python scripts/generate_agent_catalog.py
python -m http.server 8080 --directory site
# http://127.0.0.1:8080/
```

## Scope

- Pages = **index + short summaries** (not the full aitmpl.com product UI).
- Full bodies live under `cli-tool/components/`.
- Upstream: [davila7/claude-code-templates](https://github.com/davila7/claude-code-templates) (MIT).

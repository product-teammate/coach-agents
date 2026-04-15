# Skill authoring

The canonical guide is [skills/_base/SKILL.schema.md](../skills/_base/SKILL.schema.md).
This page gives the short version and cross-links to the manifests
already in the repo for reference.

## Required shape

Each skill is a directory under `skills/`. It must contain a `SKILL.md`
with YAML frontmatter validated against
[`schemas/skill.schema.json`](../schemas/skill.schema.json).

Frontmatter fields: `name`, `version`, `description`, `required_tools`,
`inputs`, `outputs`, `triggers`.

The body must include four sections: "When to use", "How it works",
"Examples", "Constraints".

## Optional files

- `playbook.md` — longer step-by-step prompt (see
  [skill-evolver/playbook.md](../skills/skill-evolver/playbook.md) and
  [kb-research/playbook.md](../skills/kb-research/playbook.md)).
- `sources.yaml`, `templates/`, `scripts/` — supporting assets.

## Authoring loop

1. Copy the shape from `skills/kb-research/SKILL.md`.
2. Trim to a focused purpose — one skill, one job.
3. Keep playbooks under ~200 lines.
4. Add the skill name to a dev agent via `coach add-skill`.
5. Exercise it in stub mode first.

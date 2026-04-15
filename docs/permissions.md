# Permissions

Two sources declare tools:

1. **Agent-level** — `agent.yaml.brain.allowed_tools`. A baseline of
   tools the agent's owner trusts across all turns.
2. **Skill-level** — `SKILL.md.required_tools` in every enabled skill.

The runtime merges the two via `runtime.permissions.merge_tools`:

```python
final = dedupe(agent_tools + union(skill_tools))
```

Order is stable: agent tools first, then each skill in `agent.yaml.skills`
order. Duplicates collapse.

## Why a merge, not just a union

- Agent-level declarations document intent and make audits easy.
- Skill-level declarations make skills portable between agents.
- A future tightening policy (`skills cannot add tools not in agent`) can
  be added here without touching brains/channels.

## Deny-by-default

If neither the agent nor a skill requests a tool, the brain does not see
it. There is no implicit whitelist.

## Permission mode

Separately, `brain.permission_mode` in `agent.yaml` maps to the
`--permission-mode` flag of the Claude Code CLI (`default`,
`acceptEdits`, `plan`, `bypassPermissions`).

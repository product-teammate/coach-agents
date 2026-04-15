# coach CLI

Typer-based entry point. Installed as `coach` after `pip install -e .`.

```
coach new <id>        # scaffold a new agent from template/
coach add-skill <id> <skill>
coach validate <id>   # schema + sanity checks
coach doctor          # environment health report
coach status          # list known agents
coach start --all     # run every configured agent
coach stop            # Phase 1 stub — Ctrl-C instead
```

Each subcommand lives in `coach_cli/commands/` as a one-file module.

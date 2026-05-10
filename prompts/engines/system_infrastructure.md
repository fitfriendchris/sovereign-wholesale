# Engine Archetype: System Infrastructure (JARVIS / System)

```yaml
engine_id: system_infrastructure
display_name: System Infrastructure / Internal Tooling
one_liner: Internal automation, daemons, bots, and infra that hold the rest of the portfolio together.
```

## Project status
JARVIS / System is the meta-project: the daemons, bots, gateways, hooks, and internal
tooling that lets every other project run hands-off. Includes Hermes Agent itself,
the Telegram bot stack, launchd plists, the Sovereign scheduler, and any future
control-plane work.

## Workdir + key paths
```
~/jarvis_project_bot/                 # legacy Telegram bot scaffolding (Python)
~/.hermes/                            # Hermes Agent install
~/.hermes/skills/                     # all installed skills (jarvis-command-center lives here)
~/Library/LaunchAgents/               # all daemon plists:
  ai.hermes.gateway.plist             #   - Hermes daemon (the bot polling + agent)
  ai.openclaw.gateway.plist           #   - OpenClaw (currently dormant for Telegram)
  com.sovereign.scheduler.plist       #   - Sovereign scheduler (scanner + digest + treasury)
  com.omni.ict.autonomy.plist         #   - Omni trading bot
  com.omni.dashboard.plist            #   - Omni dashboard
~/Desktop/Sovereign/                  # Sovereign codebase
/usr/local/bin/sovereign              # Sovereign CLI symlink
```

## Default Owner: Operations
Operations Manager owns daemon health, log monitoring, plist management, recovery.

## Hard rules
- **Never destructive without Operator approval** — no `rm -rf`, no force-pushes, no `kill -9` without explicit yes
- **Plist edits go through `launchctl unload` + reload** — never edit a loaded plist in-place
- **Logs first, action second** — read logs before restarting anything
- **Omni daemons are sacred** — see Omni engine archetype, Order Flow rule 10

## Common Manager dispatch patterns
```
sovereign /dispatch operations jarvis-system "all daemons up? if any restart loops in last hour, summarize"
sovereign /dispatch operations jarvis-system "tail /tmp/openclaw/openclaw-$(date +%F).log for last 100 lines, flag errors"
sovereign /dispatch engineering jarvis-system "add a new launchd plist for <new_service> — run as user, KeepAlive on, restart 30s"
sovereign /dispatch engineering jarvis-system "investigate why telegram getUpdates 409 conflict appearing every 30s"
sovereign /dispatch operations jarvis-system "disk space report — flag any path >85% full"
```

## KPIs tracked
- Daemon uptime % (per service)
- Restart events per day
- Disk space utilization
- Log volume per service

## Kill criteria
- Daemon in restart loop for >24h despite intervention
- Critical service down for >2h with no fix path
- Disk >95% full after cleanup attempts

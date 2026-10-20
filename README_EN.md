# Linger: schedule the next wake-up only after the current turn ends

> AstrBot plugin · keep_playing records intent; on_agent_done schedules

## The problem

The core has no self-sustaining loop: one wake-up = one turn, then the engine idles.

"Play for the next 40 minutes" therefore needs external cron, `future_task`, or this plugin.

v1.0.0 started the countdown when the tool was called, while the turn might run for four minutes — the timer fired mid-run and two chains operated the same device concurrently.

## Features

- `keep_playing` only records intent; `on_agent_done` schedules the next wake-up
- If a turn used no tools, the chain ends instead of spinning
- `stop_playing` stops immediately
- Four guardrails: total minutes, max rounds, admin-only, step interval
- Configurable wake-up note with `{left}` placeholder

## Install

### Option 1: Plugin marketplace (recommended)

Search "续命" in the AstrBot WebUI plugin marketplace.

### Option 2: Download from Releases

Grab the zip from [Releases](../../releases), then WebUI → Plugins → Upload.

### Option 3: Clone manually

```bash
cd AstrBot/data/plugins
git clone https://github.com/RandyLuaW/astrbot_plugin_linger.git
```

No extra Python dependencies.

## Configuration

| Key | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | `true` | See Chinese README |
| `admin_only` | bool | `true` | See Chinese README |
| `max_total_minutes` | int | `40` | See Chinese README |
| `step_minutes` | int | `2` | See Chinese README |
| `max_rounds` | int | `20` | See Chinese README |
| `wake_note` | string | `接着来。这是你自己的时间，还剩 {left} 分钟。桌上有手机。` | See Chinese README |

## Notes

- Do not disable all guardrails on a public platform
- Keep `wake_note` conversational, not task-like

## License

MIT

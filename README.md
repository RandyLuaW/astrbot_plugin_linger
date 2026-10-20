# 续命：回合结束后才排下一次唤醒，不和自己撞车

> AstrBot 插件 · 回合结束后才排下一次唤醒，不和自己撞车

## 它解决什么问题

内核没有「自持循环」：一次唤醒 = 一个回合，回合结束引擎就空转，没有任何机制会自己再叫一次自己。

所以「后面 40 分钟随便玩」只能靠外部 cron、`future_task`、或者这个插件。

v1.0.0 在工具被调用那一刻就开始倒计时，但那一轮实际可能跑四分钟——闹钟两分钟就响，第二个 run 在第一个还没停时启动，两条链同时操作同一台设备，互相打断。

## 功能

- `keep_playing` 只记状态，**不排程**；`on_agent_done`（回合真结束）才排下一次唤醒
- 这一轮没动过任何工具（只回了一句话）时，链条自动结束，不空转
- `stop_playing` 随时收工
- 四道护栏：`max_total_minutes` / `max_rounds` / `admin_only` / `step_minutes`
- 唤醒语可配置（`wake_note`），支持 `{left}` 占位符

## 工作机制

keep_playing() → 只记「想继续」
        ↓
on_agent_done（回合真结束）→ 排下一次唤醒，间隔 step_minutes
        ↓
到点唤醒 → 新的回合；本轮若没调工具 → 链条结束

四道护栏拦的是「无限自跑」：总时长、续次上限、管理员限定、步长。

## 安装

### 方式一：插件市场（推荐）

WebUI 插件市场搜索「续命」。

### 方式二：Releases 下载

从 [Releases](../../releases) 下载 zip，WebUI → 插件 → 上传安装。

### 方式三：手动克隆

```bash
cd AstrBot/data/plugins
git clone https://github.com/RandyLuaW/astrbot_plugin_linger.git
```

无额外 Python 依赖。

## 配置项

| 键 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `enabled` | bool | `true` | 启用续命。关掉后 keep_playing 直接拒绝。 |
| `admin_only` | bool | `true` | 只在管理员私聊可用。关掉等于谁都能让她自己跑起来，不建议。 |
| `max_total_minutes` | int | `40` | 一段自己的时间最长多少分钟。到点后必须重新发起，防止无限自跑。 |
| `step_minutes` | int | `2` | 每两次之间隔多久回来一次。太短会连续烧 token，太长中间那段就白等了。 |
| `max_rounds` | int | `20` | 一段里最多续几次。防死循环的最后一道闸。 |
| `wake_note` | string | `接着来。这是你自己的时间，还剩 {left} 分钟。桌上有手机。` | 到点唤醒时投给她的那句话。{left} 会替换成剩余分钟数。注意别写成任务口吻。 |

## 注意事项

- 不设上限的自由操作会在公开平台上连发内容，护栏不要全关
- `wake_note` 别写成任务口吻，否则模型会当任务是执行

## License

MIT

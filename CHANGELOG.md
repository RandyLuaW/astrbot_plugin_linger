# 更新日志

所有重要变更记录于此。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

## [1.1.0] - 2026-10-20

### 新增

- 首个公开版本。
- `keep_playing` 只记状态，**不排程**；`on_agent_done`（回合真结束）才排下一次唤醒
- 这一轮没动过任何工具（只回了一句话）时，链条自动结束，不空转
- `stop_playing` 随时收工
- 四道护栏：`max_total_minutes` / `max_rounds` / `admin_only` / `step_minutes`
- 唤醒语可配置（`wake_note`），支持 `{left}` 占位符


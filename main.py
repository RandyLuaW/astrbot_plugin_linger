# -*- coding: utf-8 -*-
"""续命：让她在自己的时间里接着玩，不用外面给她排任务。

为什么需要
----------
    内核没有「自持循环」。一次唤醒 = 一个回合（message → agent run），回合
    结束引擎就空转，没有任何机制会自己再叫一次自己。所以你跟她说「后面
    40 分钟随便玩」，她能做的只是**这一回合里连续调工具**，停了就是真停了。

    想跨过 40 分钟，只有三条路：外部 cron、她自己用 future_task 排闹钟、
    或者这个插件。

v1.1.0 修的是撞车
-----------------
    v1.0.0 在 `keep_playing` 被调用的那一刻就开始倒计时，可那一轮实际可能
    跑四分钟——闹钟两分钟就响，第二个 run 在第一个还没停时启动，两条链同时
    点同一台手机（实测 19:13:57：一条链 118 条消息、一条 27 条，并行；
    uiautomator 互相打断，`adb 返回 137`）。

    现在改成：
      - `keep_playing` 只记状态，**不排程**
      - `on_agent_done`（回合真结束）才排下一次唤醒
      - 这一轮要是没动过任何工具（她就回了一句话，比如「逛完了」），
        链条自动结束，不会空转

约束（必须留）
--------------
    - `max_total_minutes`  一轮最多多久（默认 40）
    - `max_rounds`         最多续几次（默认 20）
    - `admin_only`         只在管理员私聊可用
    - `stop_playing()`     随时收工
    不设上限的自由操作会在公开平台上连发东西，得能按住。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

PLUGIN_NAME = "astrbot_plugin_linger"
JOB_PREFIX = "linger-"

DEFAULT_CONFIG = {
    "enabled": True,
    "admin_only": True,
    "max_total_minutes": 40,
    "step_minutes": 2,
    "max_rounds": 20,
    "wake_note": "接着来。这是你自己的时间，还剩 {left} 分钟。桌上有手机。",
}


def _flag(v: Any) -> bool:
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on", "是")
    return bool(v)


def _num(v: Any, default: float) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _umo_of(obj: Any) -> str:
    umo = getattr(obj, "unified_msg_origin", "")
    return umo if isinstance(umo, str) else str(umo or "")


class LingerPlugin(Star):
    def __init__(self, context: Context, config: Any = None):
        super().__init__(context)
        self.cfg = dict(DEFAULT_CONFIG)
        if isinstance(config, dict):
            self.cfg.update({k: v for k, v in config.items() if k in DEFAULT_CONFIG})
        # umo -> {"started","deadline","rounds","acted","pending_until"}
        self._state: dict[str, dict] = {}

    async def initialize(self) -> None:
        removed = await self._purge_stale_jobs()
        logger.info(
            f"[linger] 就绪，单轮上限 {self._cfg('max_total_minutes')} 分钟、"
            f"每 {self._cfg('step_minutes')} 分钟续一次、最多 {self._cfg('max_rounds')} 次"
            f"（回合结束后才排程）"
            f"{f'；清掉 {removed} 个残留任务' if removed else ''}"
        )

    async def terminate(self) -> None:
        self._state.clear()

    # ------------------------------------------------------------ 配置/工具

    def _cfg(self, key: str) -> Any:
        return self.cfg.get(key, DEFAULT_CONFIG.get(key))

    def _cron(self):
        return getattr(self.context, "cron_manager", None)

    def _allowed(self, event: AstrMessageEvent) -> bool:
        if not _flag(self._cfg("admin_only")):
            return True
        try:
            return event.is_admin() is True and event.is_private_chat() is True
        except Exception:
            return False

    async def _purge_stale_jobs(self) -> int:
        """清掉上一进程留下的 linger 任务（一次性任务跑完自删，崩溃才留）。"""
        mgr = self._cron()
        if mgr is None:
            return 0
        n = 0
        try:
            jobs = await mgr.list_jobs()
            for job in jobs or []:
                if not str(getattr(job, "name", "") or "").startswith(JOB_PREFIX):
                    continue
                try:
                    await mgr.delete_job(str(job.job_id))
                    n += 1
                except Exception:  # noqa: BLE001
                    continue
        except Exception as e:  # noqa: BLE001
            logger.debug(f"[linger] 清理残留任务失败: {e}")
        return n

    @staticmethod
    def _left(st: dict) -> float:
        return max(0.0, st["deadline"] - datetime.now().timestamp())

    # ------------------------------------------------------------ 工具

    @filter.llm_tool(name="keep_playing")
    async def keep_playing(
        self, event: AstrMessageEvent, minutes: float = 0, next_in: float = 0
    ) -> str:
        """把接下来一段时间划给自己，想干嘛干嘛。

        不是任务，是让你能连着玩：这一轮忙完，过一会儿会自己再醒过来，
        你还想接着玩就继续，不想动就停手（不动工具就自然收尾）。
        随时可以 stop_playing 收工。

        Args:
            minutes (number): 这段时间想开多久，单位分钟。留空用默认上限。
            next_in (number): 这一轮结束后隔多久再醒，单位分钟。留空用默认间隔。
        Returns:
            str: 这段还剩多少时间
        """
        if not _flag(self._cfg("enabled")):
            return "续命功能关着。"
        if not self._allowed(event):
            return "这个功能只在管理员私聊里能用。"

        umo = _umo_of(event)
        now = datetime.now().timestamp()
        cap = max(1.0, _num(self._cfg("max_total_minutes"), 40))

        st = self._state.get(umo)
        if st and now >= st["deadline"]:
            self._state.pop(umo, None)
            return "这段自己的时间已经用完了。想再开就重新说一次。"

        if st is None:
            span = _num(minutes, cap) if minutes and minutes > 0 else cap
            span = min(span, cap)
            st = {
                "started": now,
                "deadline": now + span * 60,
                "rounds": 0,
                "acted": True,
                "pending_until": 0.0,
            }
            self._state[umo] = st
            left = int(span)
            logger.info(f"[linger] {umo} 开一段自己的时间，{left} 分钟")
            return (
                f"行，这段归你了：{left} 分钟。这一轮忙完我会自己再醒过来，"
                "接着玩就继续，不想动就停手。"
            )

        if next_in and next_in > 0:
            st["step_override"] = max(0.5, float(next_in))
        left = int(self._left(st) // 60)
        return f"这段还剩 {left} 分钟，一直在走。"

    @filter.llm_tool(name="stop_playing")
    async def stop_playing(self, event: AstrMessageEvent) -> str:
        """收工：把自己的时间结束掉，不再叫回来。

        Returns:
            str: 收了
        """
        umo = _umo_of(event)
        st = self._state.pop(umo, None)
        if st is None:
            return "本来也没在玩。"
        used = int((datetime.now().timestamp() - st["started"]) // 60)
        return f"收了。这段玩了 {used} 分钟，醒了 {st['rounds']} 次。"

    # ------------------------------------------------------------ 钩子

    @filter.on_using_llm_tool()
    async def note_tool_use(
        self, event: AstrMessageEvent, tool: Any, tool_args: Any
    ) -> None:
        """她这一轮动过手吗。没动过就说明玩够了，不用再叫。"""
        st = self._state.get(_umo_of(event))
        if st is not None:
            st["acted"] = True

    @filter.on_agent_done()
    async def schedule_next(self, event: Any, run_context: Any, response: Any) -> None:
        """回合真的结束了才排下一次唤醒——v1.0 漏了这一步才会撞车。"""
        if not _flag(self._cfg("enabled")):
            return
        umo = _umo_of(event)
        st = self._state.get(umo)
        if st is None:
            return

        now = datetime.now().timestamp()
        if now >= st["deadline"]:
            self._state.pop(umo, None)
            logger.info(f"[linger] {umo} 时间到，收尾（醒了 {st['rounds']} 次）")
            return

        # 先看有没有已排好的唤醒：排过就别再judge，也别重复排。
        # 这个判断必须在 acted 之前——同一个回合的结束钩子万一触发两次，
        # 第二次会看到 acted 已被重置成 False，误判成"她停了"。
        if st.get("pending_until", 0) > now:
            return

        if not st.get("acted"):
            self._state.pop(umo, None)
            logger.info(f"[linger] {umo} 这一轮没动手，链条自然结束")
            return

        mgr = self._cron()
        if mgr is None:
            return

        step = max(0.5, _num(st.get("step_override") or self._cfg("step_minutes"), 2))
        max_rounds = max(1, int(_num(self._cfg("max_rounds"), 20)))
        if st["rounds"] >= max_rounds:
            self._state.pop(umo, None)
            logger.info(f"[linger] {umo} 到续命上限 {max_rounds}，停")
            return

        run_at = datetime.now().astimezone() + timedelta(minutes=step)
        left = int(self._left(st) // 60)
        note = str(self._cfg("wake_note") or "").format(left=left)
        try:
            sender = ""
            get_id = getattr(event, "get_sender_id", None)
            if callable(get_id):
                sender = str(get_id() or "")
            await mgr.add_active_job(
                name=f"{JOB_PREFIX}{umo[-12:]}",
                cron_expression=None,
                payload={
                    "session": umo,
                    "sender_id": sender,
                    "note": note,
                    "origin": "linger",
                },
                description=note,
                timezone=None,
                persistent=False,
                run_once=True,
                run_at=run_at,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[linger] 订唤醒失败: {e}")
            self._state.pop(umo, None)
            return

        st["rounds"] += 1
        st["acted"] = False
        st["pending_until"] = run_at.timestamp() + 1
        logger.info(
            f"[linger] {umo} 第 {st['rounds']} 次排唤醒，{step:g} 分钟后，"
            f"这段还剩 {left} 分钟"
        )

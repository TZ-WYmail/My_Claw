"""
通知服务 — 邮件通知配置与发送
支持 SMTP 邮件发送，配置持久化到 data/notification_config.json
"""
from __future__ import annotations

import asyncio
import json
import logging
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config import BASE_DIR

logger = logging.getLogger(__name__)


class NotificationConfig:
    """通知配置，持久化到 data/notification_config.json"""

    _CONFIG_FILE = BASE_DIR / "data" / "notification_config.json"

    def __init__(self):
        self.smtp_host = ""
        self.smtp_port = 465
        self.smtp_user = ""
        self.smtp_password = ""
        self.notify_email = ""
        self.reminder_minutes_before = 15  # 开始前提醒分钟数
        self.reminder_due_minutes = 30  # 截止前提醒分钟数
        self._load()

    def _load(self):
        """从本地 JSON 文件加载持久化配置"""
        try:
            if self._CONFIG_FILE.exists():
                with open(self._CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("smtp_host"):
                    self.smtp_host = data["smtp_host"]
                if data.get("smtp_port"):
                    self.smtp_port = int(data["smtp_port"])
                if data.get("smtp_user"):
                    self.smtp_user = data["smtp_user"]
                if data.get("smtp_password"):
                    self.smtp_password = data["smtp_password"]
                if data.get("notify_email"):
                    self.notify_email = data["notify_email"]
                if data.get("reminder_minutes_before") is not None:
                    self.reminder_minutes_before = int(data["reminder_minutes_before"])
                if data.get("reminder_due_minutes") is not None:
                    self.reminder_due_minutes = int(data["reminder_due_minutes"])
        except Exception as e:
            logger.warning(f"加载通知配置文件失败: {e}")

    def save(self) -> bool:
        """持久化当前配置到本地 JSON 文件"""
        try:
            self._CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(self._CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "smtp_host": self.smtp_host,
                    "smtp_port": self.smtp_port,
                    "smtp_user": self.smtp_user,
                    "smtp_password": self.smtp_password,
                    "notify_email": self.notify_email,
                    "reminder_minutes_before": self.reminder_minutes_before,
                    "reminder_due_minutes": self.reminder_due_minutes,
                }, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存通知配置失败: {e}")
            return False

    def to_dict(self, mask_password: bool = True) -> dict:
        """返回配置字典，mask_password 时隐藏密码"""
        return {
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "smtp_user": self.smtp_user,
            "smtp_password": "***" if mask_password and self.smtp_password else self.smtp_password,
            "notify_email": self.notify_email,
            "reminder_minutes_before": self.reminder_minutes_before,
            "reminder_due_minutes": self.reminder_due_minutes,
        }

    def is_configured(self) -> bool:
        """检查邮件通知是否已完整配置"""
        return bool(
            self.smtp_host
            and self.smtp_user
            and self.smtp_password
            and self.notify_email
        )

    def update(self, **kwargs):
        """更新配置字段，仅接受非空字符串或有效整数"""
        if kwargs.get("smtp_host") and isinstance(kwargs["smtp_host"], str):
            self.smtp_host = kwargs["smtp_host"]
        if kwargs.get("smtp_port") and isinstance(kwargs["smtp_port"], int):
            self.smtp_port = kwargs["smtp_port"]
        if kwargs.get("smtp_user") and isinstance(kwargs["smtp_user"], str):
            self.smtp_user = kwargs["smtp_user"]
        if kwargs.get("smtp_password") and isinstance(kwargs["smtp_password"], str):
            self.smtp_password = kwargs["smtp_password"]
        if kwargs.get("notify_email") and isinstance(kwargs["notify_email"], str):
            self.notify_email = kwargs["notify_email"]
        if isinstance(kwargs.get("reminder_minutes_before"), int) and kwargs["reminder_minutes_before"] > 0:
            self.reminder_minutes_before = kwargs["reminder_minutes_before"]
        if isinstance(kwargs.get("reminder_due_minutes"), int) and kwargs["reminder_due_minutes"] > 0:
            self.reminder_due_minutes = kwargs["reminder_due_minutes"]


# 全局通知配置单例
notification_config = NotificationConfig()


# ============================================================
# 邮件发送
# ============================================================

async def send_email(subject: str, body_html: str) -> dict:
    """
    发送 HTML 邮件通知。

    使用 asyncio.to_thread() 避免 SMTP 阻塞事件循环。
    根据端口号自动选择 SMTP_SSL (465) 或 SMTP + STARTTLS。
    """
    if not notification_config.is_configured():
        return {"status": "error", "message": "通知未配置"}

    full_subject = f"[LocalCommandCenter] {subject}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = full_subject
    msg["From"] = notification_config.smtp_user
    msg["To"] = notification_config.notify_email
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    def _send():
        try:
            if notification_config.smtp_port == 465:
                server = smtplib.SMTP_SSL(
                    notification_config.smtp_host,
                    notification_config.smtp_port,
                    timeout=30,
                )
            else:
                server = smtplib.SMTP(
                    notification_config.smtp_host,
                    notification_config.smtp_port,
                    timeout=30,
                )
                server.ehlo()
                server.starttls()
                server.ehlo()

            server.login(notification_config.smtp_user, notification_config.smtp_password)
            server.sendmail(
                notification_config.smtp_user,
                notification_config.notify_email,
                msg.as_string(),
            )
            server.quit()
            return {"status": "success"}
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return {"status": "error", "message": str(e)}

    return await asyncio.to_thread(_send)


async def send_test_email() -> dict:
    """发送测试邮件，验证通知配置是否正确"""
    return await send_email(
        "测试邮件",
        "<h3>通知测试</h3><p>如果你收到这封邮件，说明通知配置正确！</p>",
    )


# ============================================================
# 任务格式化辅助
# ============================================================

_PRIORITY_LABELS = {0: "紧急", 1: "高", 2: "中", 3: "低"}


def _format_task_line(task: dict) -> str:
    """
    将任务字典格式化为显示行。

    有开始/结束时间时显示时间范围，否则显示截止时间。
    优先级映射：0=紧急, 1=高, 2=中, 3=低
    """
    name = task.get("task_name", "未命名任务")
    priority = task.get("priority", 2)
    priority_label = _PRIORITY_LABELS.get(priority, "中")

    start_time = task.get("start_time")
    end_time = task.get("end_time")
    due_time = task.get("due_time")

    if start_time and end_time:
        # 截取时间部分（HH:MM）
        try:
            st = datetime.fromisoformat(start_time).strftime("%H:%M")
            et = datetime.fromisoformat(end_time).strftime("%H:%M")
            time_str = f"{st}-{et}"
        except (ValueError, TypeError):
            time_str = f"{start_time}-{end_time}"
        return f"  {time_str}  {name}  [{priority_label}优先级]"
    elif due_time:
        try:
            dt = datetime.fromisoformat(due_time).strftime("%H:%M")
            time_str = dt
        except (ValueError, TypeError):
            time_str = str(due_time)
        return f"  {time_str}  {name}  [{priority_label}优先级]"
    else:
        return f"  {name}  [{priority_label}优先级]"


# ============================================================
# 任务提醒调度
# ============================================================

def schedule_task_reminders(task_id: str, start_time: str = None, due_time: str = None, task_name: str = ""):
    """为任务注册开始前和截止前的提醒 job"""
    global _scheduler
    if not _scheduler or not notification_config.is_configured():
        return

    from datetime import datetime, timedelta

    # 开始前提醒
    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time)
            remind_at = start_dt - timedelta(minutes=notification_config.reminder_minutes_before)
            if remind_at > datetime.now(start_dt.tzinfo):
                _scheduler.add_job(
                    send_start_reminder,
                    'date',
                    run_date=remind_at,
                    id=f'reminder_start_{task_id}',
                    args=[task_name, start_time],
                    replace_existing=True,
                )
        except (ValueError, TypeError):
            pass

    # 截止前提醒
    if due_time:
        try:
            due_dt = datetime.fromisoformat(due_time)
            remind_at = due_dt - timedelta(minutes=notification_config.reminder_due_minutes)
            if remind_at > datetime.now(due_dt.tzinfo):
                _scheduler.add_job(
                    send_due_reminder,
                    'date',
                    run_date=remind_at,
                    id=f'reminder_due_{task_id}',
                    args=[task_name, due_time],
                    replace_existing=True,
                )
        except (ValueError, TypeError):
            pass


def cancel_task_reminders(task_id: str):
    """取消任务的提醒 job"""
    global _scheduler
    if not _scheduler:
        return

    for suffix in ['start', 'due']:
        job_id = f'reminder_{suffix}_{task_id}'
        try:
            _scheduler.remove_job(job_id)
        except Exception:
            pass


async def send_start_reminder(task_name: str, start_time: str):
    """发送任务开始前提醒"""
    time_range = ""
    try:
        time_range = start_time[11:16]
    except Exception:
        pass

    body = f"<p>「{task_name}」将在 {notification_config.reminder_minutes_before} 分钟后开始 ({time_range})</p>"
    await send_email(f"⏰ 任务提醒：{task_name} 即将开始", body)


async def send_due_reminder(task_name: str, due_time: str):
    """发送截止前提醒"""
    time_str = ""
    try:
        time_str = due_time[11:16]
    except Exception:
        pass

    body = f"<p>「{task_name}」将在 {notification_config.reminder_due_minutes} 分钟后截止 (截止时间: {time_str})</p>"
    await send_email(f"⚠️ 截止提醒：{task_name} 即将到期", body)


async def restore_all_reminders():
    """服务重启时，从数据库恢复所有 pending 任务的提醒"""
    import aiosqlite
    from config import DB_PATH

    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT task_id, task_name, start_time, due_time FROM tasks WHERE status = 'pending'",
        )
        rows = await cursor.fetchall()

    count = 0
    for row in rows:
        schedule_task_reminders(
            task_id=row["task_id"],
            start_time=row["start_time"],
            due_time=row["due_time"],
            task_name=row["task_name"],
        )
        count += 1

    if count > 0:
        logger.info(f"已恢复 {count} 个任务的提醒")


# ============================================================
# 三时报 — 数据查询辅助
# ============================================================

async def _get_today_tasks() -> list[dict]:
    """获取今日任务列表"""
    import aiosqlite
    from config import DB_PATH
    from datetime import datetime

    today = datetime.now().strftime("%Y-%m-%d")

    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT task_id, task_name, due_time, start_time, end_time, priority, status
               FROM tasks
               WHERE status = 'pending'
               AND (substr(start_time, 1, 10) = ? OR substr(due_time, 1, 10) = ?)
               ORDER BY start_time ASC, priority ASC""",
            (today, today),
        )
        return [dict(row) for row in await cursor.fetchall()]


async def _get_overdue_tasks() -> list[dict]:
    """获取逾期任务列表"""
    import aiosqlite
    from config import DB_PATH
    from datetime import datetime

    now = datetime.now().isoformat()

    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT task_id, task_name, due_time, start_time, end_time, priority
               FROM tasks
               WHERE status = 'pending' AND due_time < ?
               ORDER BY due_time ASC
               LIMIT 10""",
            (now,),
        )
        return [dict(row) for row in await cursor.fetchall()]


async def _get_tomorrow_tasks() -> list[dict]:
    """获取明日任务列表"""
    import aiosqlite
    from config import DB_PATH
    from datetime import datetime, timedelta

    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT task_id, task_name, due_time, start_time, end_time, priority
               FROM tasks
               WHERE status = 'pending'
               AND (substr(start_time, 1, 10) = ? OR substr(due_time, 1, 10) = ?)
               ORDER BY start_time ASC, priority ASC""",
            (tomorrow, tomorrow),
        )
        return [dict(row) for row in await cursor.fetchall()]


def _overdue_days(due_time: str) -> int:
    """计算逾期天数"""
    try:
        from datetime import datetime
        due = datetime.fromisoformat(due_time)
        now = datetime.now(due.tzinfo)
        return max(0, (now - due).days)
    except Exception:
        return 0


# ============================================================
# 三时报 — 晨报 / 午报 / 晚报
# ============================================================

async def send_morning_report():
    """晨报：今日任务 + 逾期任务 + streak"""
    if not notification_config.is_configured():
        return

    from datetime import datetime
    from services.streak_service import get_streak_info

    today_tasks = await _get_today_tasks()
    overdue_tasks = await _get_overdue_tasks()
    streak_info = await get_streak_info()

    date_str = datetime.now().strftime("%Y年%m月%d日")

    lines = [f"🌤 早上好！\n"]

    # Streak 数据
    lines.append("📊 你的数据")
    lines.append(f"  连续完成: 🔥 {streak_info['current_streak']} 天")
    lines.append(f"  本周完成率: {streak_info['weekly_rate']}%\n")

    # 逾期任务
    if overdue_tasks:
        lines.append(f"⚠️ 逾期任务（{len(overdue_tasks)}项）")
        for t in overdue_tasks[:5]:
            days = _overdue_days(t['due_time'])
            lines.append(f"  - {t['task_name']}（逾期 {days}天）")
        lines.append("")

    # 今日任务
    if today_tasks:
        lines.append(f"📋 今日任务（{len(today_tasks)}项）")
        for t in today_tasks:
            lines.append(_format_task_line(t))
    else:
        lines.append("📋 今日暂无任务安排")

    lines.append("\n祝高效的一天！")

    body = "<pre style='font-family: sans-serif; font-size: 14px; line-height: 1.6;'>" + "\n".join(lines) + "</pre>"
    await send_email(f"🌤 晨报 - {date_str} 今日任务", body)


async def send_noon_report():
    """午报：上午进度 + 下午安排"""
    if not notification_config.is_configured():
        return

    from datetime import datetime

    today = datetime.now().strftime("%Y-%m-%d")
    now_str = datetime.now().isoformat()

    import aiosqlite
    from config import DB_PATH

    # 上午任务（start_time < 13:00 或无 start_time 但 due_time 在今天）
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        # 上午已完成
        cursor = await db.execute(
            """SELECT task_name FROM tasks
               WHERE status = 'completed' AND completed_at IS NOT NULL
               AND (substr(start_time, 1, 10) = ? OR substr(due_time, 1, 10) = ?)
               AND (start_time IS NULL OR substr(start_time, 12, 2) < '13')""",
            (today, today),
        )
        morning_done = [dict(row) for row in await cursor.fetchall()]

        # 上午未完成
        cursor = await db.execute(
            """SELECT task_name, start_time, end_time FROM tasks
               WHERE status = 'pending'
               AND (substr(start_time, 1, 10) = ? OR substr(due_time, 1, 10) = ?)
               AND (start_time IS NULL OR substr(start_time, 12, 2) < '13')""",
            (today, today),
        )
        morning_pending = [dict(row) for row in await cursor.fetchall()]

        # 下午待执行
        cursor = await db.execute(
            """SELECT task_name, start_time, end_time, priority FROM tasks
               WHERE status = 'pending'
               AND start_time IS NOT NULL AND substr(start_time, 12, 2) >= '13'
               AND substr(start_time, 1, 10) = ?
               ORDER BY start_time ASC""",
            (today,),
        )
        afternoon_tasks = [dict(row) for row in await cursor.fetchall()]

    lines = ["☀️ 下午好！\n"]

    # 上午进度
    morning_total = len(morning_done) + len(morning_pending)
    if morning_total > 0:
        rate = round(len(morning_done) / morning_total * 100)
        lines.append("📈 上午进度")
        lines.append(f"  已完成: {len(morning_done)}/{morning_total} 项")
        if rate >= 80:
            lines.append("  上午效率很高，继续保持！")
        elif rate >= 50:
            lines.append("  上午完成了一半以上，下午继续加油！")
        else:
            lines.append("  上午的任务还没完成，下午抓紧哦！")
        lines.append("")
    else:
        lines.append("📈 今天上午没有安排任务，下午有安排。\n")

    # 上午未完成
    if morning_pending:
        lines.append(f"⚠️ 上午未完成（{len(morning_pending)}项）")
        for t in morning_pending[:5]:
            time_info = ""
            if t.get("start_time"):
                start_h = t["start_time"][11:16]
                end_h = t["end_time"][11:16] if t.get("end_time") else ""
                time_info = f"（原定 {start_h}-{end_h}）"
            lines.append(f"  - {t['task_name']}{time_info}")
        lines.append("")

    # 下午待执行
    if afternoon_tasks:
        lines.append(f"📋 下午待执行（{len(afternoon_tasks)}项）")
        for t in afternoon_tasks:
            lines.append(_format_task_line(t))

    lines.append("\n💡 提示：逾期任务请优先处理。")

    body = "<pre style='font-family: sans-serif; font-size: 14px; line-height: 1.6;'>" + "\n".join(lines) + "</pre>"
    await send_email("☀️ 午报 - 下午安排", body)


async def send_evening_report():
    """晚报：今日总结 + 明日预览"""
    if not notification_config.is_configured():
        return

    from datetime import datetime
    from services.streak_service import get_streak_info

    today_tasks = await _get_today_tasks()
    tomorrow_tasks = await _get_tomorrow_tasks()
    streak_info = await get_streak_info()

    # 获取今日已完成
    import aiosqlite
    from config import DB_PATH

    today = datetime.now().strftime("%Y-%m-%d")
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT task_name, start_time, end_time, completed_at FROM tasks
               WHERE status = 'completed' AND completed_at IS NOT NULL
               AND (substr(completed_at, 1, 10) = ? OR substr(start_time, 1, 10) = ? OR substr(due_time, 1, 10) = ?)""",
            (today, today, today),
        )
        completed_today = [dict(row) for row in await cursor.fetchall()]

    total_today = len(today_tasks) + len(completed_today)
    completed_count = len(completed_today)
    rate = round(completed_count / total_today * 100) if total_today > 0 else 0

    lines = ["🌙 晚上好！\n"]

    # 今日总结
    lines.append("📊 今日总结")
    lines.append(f"  完成率: {completed_count}/{total_today} ({rate}%)")
    lines.append(f"  连续天数: 🔥 {streak_info['current_streak']} 天")
    lines.append(f"  最长纪录: {streak_info['longest_streak']} 天\n")

    # 已完成
    if completed_today:
        lines.append(f"✅ 已完成（{completed_count}项）")
        for t in completed_today:
            time_info = ""
            if t.get("start_time") and t.get("end_time"):
                time_info = f"（{t['start_time'][11:16]}-{t['end_time'][11:16]}）"
            lines.append(f"  ✓ {t['task_name']}{time_info}")
        lines.append("")

    # 未完成
    if today_tasks:
        lines.append(f"❌ 未完成（{len(today_tasks)}项）→ 已转为逾期")
        for t in today_tasks:
            lines.append(f"  ✗ {t['task_name']}（截止 {t['due_time'][11:16] if t.get('due_time') else '无'}）")
        lines.append("")

    # 明日预览
    if tomorrow_tasks:
        lines.append(f"📅 明日预览（{len(tomorrow_tasks)}项）")
        for t in tomorrow_tasks:
            lines.append(_format_task_line(t))
        lines.append("")

    # 结束语
    if rate == 100 and total_today > 0:
        lines.append("完美的一天！明天继续！🔥")
    elif rate >= 70:
        lines.append("今天大部分任务都完成了，很棒！未完成的明天优先处理。💪")
    elif total_today > 0:
        lines.append("今天的完成率不太理想，明天重新规划一下？目标小一点，完成率高一点。")
    else:
        lines.append("今天没有安排任务，明天试试规划一下？")

    # 里程碑检测
    from services.streak_service import check_milestones, get_milestone_message
    milestones = check_milestones(streak_info['current_streak'], streak_info.get('_prev_streak', 0))
    for m in milestones:
        lines.append(f"\n🏆 {get_milestone_message(m)}")

    body = "<pre style='font-family: sans-serif; font-size: 14px; line-height: 1.6;'>" + "\n".join(lines) + "</pre>"
    date_str = datetime.now().strftime("%Y年%m月%d日")
    await send_email(f"🌙 晚报 - {date_str} 今日总结", body)

    # 如果达到里程碑，额外发送祝贺邮件
    for m in milestones:
        congrats_body = (
            f"<div style='text-align:center; padding:40px; font-family:sans-serif;'>"
            f"<h1 style='font-size:2em;'>🏆</h1>"
            f"<h2>{get_milestone_message(m)}</h2>"
            f"<p style='color:#666;'>你已连续 {streak_info['current_streak']} 天完成所有任务</p>"
            f"</div>"
        )
        await send_email(f"🏆 里程碑达成！连续 {streak_info['current_streak']} 天", congrats_body)


# ============================================================
# APScheduler 调度器 — 三时报注册/注销
# ============================================================

def setup_scheduler():
    """初始化 APScheduler，注册三时报 cron 任务"""
    global _scheduler
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    _scheduler = AsyncIOScheduler()

    if notification_config.is_configured():
        _scheduler.add_job(send_morning_report, 'cron', hour=8, minute=0, id='morning_report')
        _scheduler.add_job(send_noon_report, 'cron', hour=13, minute=0, id='noon_report')
        _scheduler.add_job(send_evening_report, 'cron', hour=21, minute=0, id='evening_report')

    _scheduler.start()
    logger.info("APScheduler 已启动（三时报）")


def shutdown_scheduler():
    """关闭调度器"""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown()
        logger.info("APScheduler 已关闭")


def reschedule_reports():
    """配置变更后重新注册三时报任务"""
    global _scheduler
    if not _scheduler:
        return

    # 移除旧的
    for job_id in ['morning_report', 'noon_report', 'evening_report']:
        try:
            _scheduler.remove_job(job_id)
        except Exception:
            pass

    # 如果已配置，重新注册
    if notification_config.is_configured():
        _scheduler.add_job(send_morning_report, 'cron', hour=8, minute=0, id='morning_report')
        _scheduler.add_job(send_noon_report, 'cron', hour=13, minute=0, id='noon_report')
        _scheduler.add_job(send_evening_report, 'cron', hour=21, minute=0, id='evening_report')
        logger.info("三时报任务已重新注册")

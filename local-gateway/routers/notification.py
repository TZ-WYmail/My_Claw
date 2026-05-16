"""通知配置 API"""
from fastapi import APIRouter
from services.notification_service import notification_config, send_email, send_test_email
from services.mail_service import ensure_mail_account_from_notification_config

router = APIRouter()


@router.get("/notification/config")
async def get_notification_config():
    return {"status": "success", "config": notification_config.to_dict()}


@router.post("/notification/config")
async def save_notification_config(request: dict):
    notification_config.update(
        smtp_host=request.get("smtp_host", ""),
        smtp_port=request.get("smtp_port", 465),
        smtp_user=request.get("smtp_user", ""),
        smtp_password=request.get("smtp_password", ""),
        notify_email=request.get("notify_email", ""),
        reminder_minutes_before=request.get("reminder_minutes_before", 15),
        reminder_due_minutes=request.get("reminder_due_minutes", 30),
    )
    saved = notification_config.save()
    from services.notification_service import reschedule_reports
    reschedule_reports()
    from services.notification_service import restore_all_reminders
    await restore_all_reminders()
    await ensure_mail_account_from_notification_config()
    return {
        "status": "success" if saved else "error",
        "config": notification_config.to_dict(),
        "message": "通知配置已保存" if saved else "配置保存失败",
    }


@router.post("/notification/test")
async def test_notification():
    result = await send_test_email()
    return result

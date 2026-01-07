import logging
from asgiref.sync import async_to_sync
from celery import Celery
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from pydantic import EmailStr
from twilio.rest import Client

from app.config import db_settings, notification_settings
from app.utils import TEMPLATE_DIR

logger = logging.getLogger(__name__)

fast_mail = FastMail(
    ConnectionConfig(
        **notification_settings.model_dump(
            exclude=["TWILIO_SID", "TWILIO_AUTH_TOKEN", "TWILIO_NUMBER"]
        ),
        TEMPLATE_FOLDER=TEMPLATE_DIR,
    )
)

twilio_client = Client(
    notification_settings.TWILIO_SID,
    notification_settings.TWILIO_AUTH_TOKEN,
)

send_message = async_to_sync(fast_mail.send_message)


app = Celery(
    "api_tasks",
    broker=db_settings.REDIS_URL(9),
    backend=db_settings.REDIS_URL(9),
    broker_connection_retry_on_startup=True,
)


@app.task
def send_mail(
    recipients: list[str],
    subject: str,
    body: str,
):
    try:
        send_message(
            message=MessageSchema(
                recipients=recipients,
                subject=subject,
                body=body,
                subtype=MessageType.plain,
            ),
        )
        logger.info(f"Email sent successfully to {recipients}")
        return "Message Sent!"
    except Exception as e:
        # Log warning instead of error, don't show full traceback
        logger.warning(f"Email service unavailable: failed to send to {recipients}. Error: {str(e)}")
        # Don't raise exception to prevent task failure - email is not critical
        return f"Failed to send message: {e}"


@app.task
def send_email_with_template(
    recipients: list[EmailStr],
    subject: str,
    context: dict,
    template_name: str,
):
    try:
        send_message(
            message=MessageSchema(
                recipients=recipients,
                subject=subject,
                template_body=context,
                subtype=MessageType.html,
            ),
            template_name=template_name,
        )
        logger.info(f"Email sent successfully to {recipients}")
    except Exception as e:
        # Log warning instead of error, don't show full traceback
        logger.warning(f"Email service unavailable: failed to send to {recipients}. Error: {str(e)}")
        # Don't raise exception to prevent task failure - email is not critical


@app.task
def send_sms(to: str, body: str):
    try:
        twilio_client.messages.create(
            from_=notification_settings.TWILIO_NUMBER,
            to=to,
            body=body,
        )
        logger.info(f"SMS sent successfully to {to}")
    except Exception as e:
        # Log warning instead of error, don't show full traceback
        logger.warning(f"SMS service unavailable: failed to send to {to}. Error: {str(e)}")
        # Don't raise exception to prevent task failure - SMS is not critical
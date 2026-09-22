"""Outbound channels. Push (Firebase) and SMS (Twilio) are MOCKED: they are logged, and each SMS is also
stored as a Notification row (channel=sms) so the demo UI can show it. Wire real providers here."""
import logging

log = logging.getLogger("lifeline.notify")


def send_push(user_id: int, title: str, body: str) -> None:
    log.info("[MOCK FCM push] user=%s title=%r body=%r", user_id, title, body)


def send_sms(phone: str | None, body: str) -> None:
    log.info("[MOCK Twilio SMS] to=%s body=%r", phone or "n/a", body)

import logging
from urllib import request as urllib_request, parse as urllib_parse
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def send_sms_bulksmsbd(message, phone_number):
    api_key = getattr(settings, "BULKSMSBD_API_KEY", "")
    sender_id = getattr(settings, "BULKSMSBD_SENDER_ID", "8809617611470")

    phone_number = phone_number.strip()

    if phone_number.startswith("+88"):
        pass
    elif phone_number.startswith("88"):
        phone_number = "+" + phone_number
    else:
        phone_number = "+88" + phone_number

    if not api_key:
        logger.error("BULKSMSBD_API_KEY is not configured.")
        return False

    # API URL (GET & POST) : http://bulksmsbd.net/api/smsapi?api_key=(APIKEY)&type=text&number=(NUMBER)&senderid=(Approved Sender ID)&message=(Message Content)
    url = "https://bulksmsbd.net/api/smsapi"
    payload = {
        "api_key": api_key,
        "type": "text",
        "number": phone_number,
        "senderid": sender_id,
        "message": message,
    }
    print("ok----------------")
    try:
        data = urllib_parse.urlencode(payload).encode()
        req = urllib_request.Request(url, data=data, method="POST")
        with urllib_request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode()
            logger.info("BulkSMSBD response: %s", body)
            return "success" in body.lower() or "OK" in body
    except Exception as exc:
        logger.error("Failed to send SMS via BulkSMSBD: %s", exc, exc_info=True)
        return False


def send_otp_sms(code, phone_number):
    message = f"Your verification code is {code}. It will expire in 15 minutes."
    return send_sms_bulksmsbd(message, phone_number)

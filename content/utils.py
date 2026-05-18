import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .models import UserRole

logger = logging.getLogger(__name__)


def _salutation(role: str) -> str:
    return 'Dear Student'


def render_verification_email(user, code: str):
    """Return (subject, text_body, html_body) for account verification email."""
    role = getattr(user, 'profile', None)
    role_choice = role.role if role else UserRole.STUDENT
    sal = _salutation(role_choice)

    subject = 'Verify your account — Teaching Platform'
    site = getattr(settings, 'SITE_URL', 'http://localhost:8000')

    html_body = f"""
    <div style="font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial; color:#111827;">
      <p>{sal},</p>
      <p>Thank you for signing up at Teaching Platform. Use the following verification code to complete your registration:</p>
      <p style="font-size:20px; font-weight:700; letter-spacing:2px;">{code}</p>
      <p>This code will expire in 15 minutes.</p>
      <p>If you did not sign up, please ignore this email.</p>
      <hr>
      <p style="font-size:13px; color:#6b7280;">{site} — Teaching Platform</p>
    </div>
    """

    text_body = strip_tags(html_body)
    return subject, text_body, html_body


def render_password_reset_email(user, token: str):
    """Return (subject, text_body, html_body) for password reset email.

    Expects `settings.SITE_URL` to be set (falls back to localhost).
    The reset URL will be <SITE_URL>/accounts/password-reset-confirm/?token=... (adjust if you have a different flow).
    """
    role = getattr(user, 'profile', None)
    role_choice = role.role if role else UserRole.STUDENT
    sal = _salutation(role_choice)

    subject = 'Password reset instructions — Teaching Platform'
    site = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    # Default path; adjust if you have a named URL for password reset confirm
    reset_path = '/accounts/password-reset-confirm/'
    reset_url = f"{site.rstrip('/')}{reset_path}?token={token}"

    html_body = f"""
    <div style="font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial; color:#111827;">
      <p>{sal},</p>
      <p>We received a request to reset your password. Click the button below to set a new password. If you didn't request this, please ignore this email.</p>
      <p style="margin:18px 0;"><a href="{reset_url}" style="display:inline-block;padding:10px 18px;background:#2563eb;color:#fff;border-radius:8px;text-decoration:none;font-weight:600;">Reset password</a></p>
      <p>If the button doesn't work, paste this link into your browser:</p>
      <p style="font-size:13px;color:#6b7280;word-break:break-all;">{reset_url}</p>
      <hr>
      <p style="font-size:13px; color:#6b7280;">{site} — Teaching Platform</p>
    </div>
    """

    text_body = strip_tags(html_body)
    return subject, text_body, html_body


def send_email(subject: str, text_body: str, html_body: str, to_email: str, from_email: str = None) -> bool:
    """Send an email with both text and HTML parts. Returns True on success, False otherwise."""
    from_email = from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', None) or getattr(settings, 'EMAIL_HOST_USER', None)
    
    if not from_email:
        logger.error(f"Cannot send email to {to_email}: DEFAULT_FROM_EMAIL not configured")
        return False
    
    try:
        msg = EmailMultiAlternatives(subject=subject, body=text_body, from_email=from_email, to=[to_email])
        if html_body:
            msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=False)
        logger.info(f"Email sent successfully: {subject} → {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {subject} → {to_email}. Error: {str(e)}", exc_info=True)
        return False


def send_verification_email(user, code: str) -> bool:
    subject, text_body, html_body = render_verification_email(user, code)
    return send_email(subject, text_body, html_body, to_email=user.email)


def send_password_reset_email(user, token: str) -> bool:
    subject, text_body, html_body = render_password_reset_email(user, token)
    return send_email(subject, text_body, html_body, to_email=user.email)


def render_payment_submission_email(user, course, amount, payment_method: str, transaction_id: str, note: str):
        """Return (subject, text_body, html_body) for admin notification when a student submits payment details."""
        site = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        student_name = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip() or user.get_username()
        subject = f"Payment submission — {course.name} — {student_name}"

        html_body = f"""
        <div style="font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial; color:#111827;">
            <p>Admin,</p>
            <p>The following payment details were submitted by a student on <strong>{site}</strong>:</p>
            <ul>
                <li><strong>Course:</strong> {course.name}</li>
                <li><strong>Amount:</strong> ৳{amount}</li>
                <li><strong>Payment method:</strong> {payment_method or 'N/A'}</li>
                <li><strong>Transaction ID:</strong> {transaction_id}</li>
                <li><strong>Student name:</strong> {student_name}</li>
                <li><strong>Student email:</strong> {getattr(user, 'email', '')}</li>
            </ul>
            <p><strong>Phone (profile):</strong> {getattr(getattr(user, 'profile', None), 'phone_number', '')}</p>
            <p><strong>Note:</strong> {note or '(none)'}</p>
            <hr>
            <p style="font-size:13px; color:#6b7280;">{site} — Teaching Platform</p>
        </div>
        """

        text_body = strip_tags(html_body)
        return subject, text_body, html_body


def send_payment_submission_email(user, course, amount, payment_method: str, transaction_id: str, note: str) -> bool:
        subject, text_body, html_body = render_payment_submission_email(user, course, amount, payment_method, transaction_id, note)
        to_email = getattr(settings, 'SERVER_EMAIL', None) or getattr(settings, 'DEFAULT_FROM_EMAIL', None) or getattr(settings, 'EMAIL_HOST_USER', None)
        if not to_email:
                logger.error("Cannot send payment notification email: SERVER_EMAIL, DEFAULT_FROM_EMAIL, and EMAIL_HOST_USER are all not configured")
                return False
        return send_email(subject, text_body, html_body, to_email=to_email)

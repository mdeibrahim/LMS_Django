# apps/teacher_dashboard/utils.py

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags


def send_verification_email(user, otp_code):
    """
    Send account verification email.
    """

    subject = "Verify your Teacher Account"
    html_message = f"""
            Hello {user.get_full_name() or user.email},

            Welcome!

            Your email verification OTP is:

            {otp_code}

            This OTP is valid for 10 minutes.

            If you did not create this account, please ignore this email.

            Thanks,
            {settings.SITE_NAME}
            """

    plain_message = strip_tags(html_message)

    return send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def forgot_password_email(user, otp_code):
    """
    Send password reset email.
    """

    subject = "Reset Your Password"

    html_message = f"""
            Hello {user.get_full_name() or user.email},

            Your password reset OTP is:

            {otp_code}

            This OTP is valid for 10 minutes.

            If you did not request this, please ignore this email.

            Thanks,
            {settings.SITE_NAME}
            """

    plain_message = strip_tags(html_message)

    return send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )
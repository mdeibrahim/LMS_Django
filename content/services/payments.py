from django.utils import timezone

from content.models import CourseEnrollment, EnrollmentStatus, PaymentSubmission, PaymentSubmissionStatus


def ensure_enrollment(user, course, granted_by=None):
    enrollment, _ = CourseEnrollment.objects.update_or_create(
        user=user,
        course=course,
        defaults={
            "status": EnrollmentStatus.ACTIVE,
            "granted_by": granted_by,
        },
    )
    return enrollment


def create_or_update_payment_submission(user, course, payment_method, transaction_id, note=""):
    return PaymentSubmission.objects.create(
        user=user,
        course=course,
        payment_method=payment_method or "other",
        transaction_id=transaction_id,
        note=note or "",
        status=PaymentSubmissionStatus.PENDING,
    )


def approve_payment_submission(submission, reviewed_by=None):
    submission.status = PaymentSubmissionStatus.APPROVED
    submission.reviewed_by = reviewed_by
    submission.reviewed_at = timezone.now()
    submission.rejection_reason = ""
    submission.save(update_fields=["status", "reviewed_by", "reviewed_at", "rejection_reason", "updated_at"])
    return ensure_enrollment(submission.user, submission.course, granted_by=reviewed_by)

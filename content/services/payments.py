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
    submission = PaymentSubmission.objects.create(
        user=user,
        course=course,
        payment_method=payment_method or "other",
        transaction_id=transaction_id,
        note=note or "",
        status=PaymentSubmissionStatus.PENDING,
    )

    # Payment submit হওয়ার সাথে সাথে enrollment তৈরি করো (status=pending)
    # যদি আগে থেকে active enrollment থাকে, সেটা পরিবর্তন করা হবে না।
    enrollment, created = CourseEnrollment.objects.get_or_create(
        user=user,
        course=course,
        defaults={"status": EnrollmentStatus.PENDING},
    )
    if not created and enrollment.status == EnrollmentStatus.REVOKED:
        # revoked হলে pending-এ ফিরিয়ে আনো
        enrollment.status = EnrollmentStatus.PENDING
        enrollment.save(update_fields=["status", "updated_at"])

    return submission


def approve_payment_submission(submission, reviewed_by=None):
    submission.status = PaymentSubmissionStatus.APPROVED
    submission.reviewed_by = reviewed_by
    submission.reviewed_at = timezone.now()
    submission.rejection_reason = ""
    submission.save(update_fields=["status", "reviewed_by", "reviewed_at", "rejection_reason", "updated_at"])
    return ensure_enrollment(submission.user, submission.course, granted_by=reviewed_by)

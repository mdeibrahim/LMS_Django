from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from content.models import (
    Course,
    CourseEnrollment,
    Module,
    PaymentSubmission,
    PaymentSubmissionStatus,
    UserRole,
)
from apps.student_dashboard.models import StudentProfile
from apps.teacher_dashboard.models import TeacherProfile


User = get_user_model()


def _currency(value):
    return f"৳{Decimal(value or 0):,.2f}"


@require_http_methods(["GET"])
def admin_dashboard(request):
    courses_count = Course.objects.count()
    modules_count = Module.objects.count()
    confirmed_purchase_count = CourseEnrollment.objects.filter(status="active").count()
    pending_purchase_count = PaymentSubmission.objects.filter(status=PaymentSubmissionStatus.PENDING).count()
    total_users = User.objects.count()
    student_profiles_count = StudentProfile.objects.count()
    teacher_profiles_count = TeacherProfile.objects.count()
    confirmed_revenue = (
        CourseEnrollment.objects.filter(status="active").aggregate(total=Sum("course__price")).get("total")
        or Decimal("0")
    )

    overview_metrics = [
        {
            "label": "Revenue",
            "value": _currency(confirmed_revenue),
            "note": f"{confirmed_purchase_count} active enrollments",
            "tone": "emerald",
        },
        {
            "label": "Courses",
            "value": courses_count,
            "note": f"{modules_count} total modules",
            "tone": "blue",
        },
        {
            "label": "Students",
            "value": student_profiles_count,
            "note": f"{total_users} total users",
            "tone": "violet",
        },
        {
            "label": "Teachers",
            "value": teacher_profiles_count+1,
            "note": f"{total_users} total users",
            "tone": "amber",
        },
    ]

    priority_queue = [
        {
            "label": "Pending purchases",
            "value": pending_purchase_count,
            "tone": "amber" if pending_purchase_count else "emerald",
            "note": "Review payments awaiting approval.",
            "url": reverse("admin:content_paymentsubmission_changelist"),
        },
        {
            "label": "Courses",
            "value": courses_count,
            "tone": "slate",
            "note": "Manage catalog structure.",
            "url": reverse("admin:content_course_changelist"),
        },
    ]

    quick_actions = [
        {"label": "Create Course", "url": reverse("admin:content_course_add"), "tone": "primary"},
        {"label": "Review Payments", "url": reverse("admin:content_paymentsubmission_changelist"), "tone": "secondary"},
        {"label": "Manage Users", "url": reverse("admin:content_user_changelist"), "tone": "secondary"},
    ]

    context = {
        **admin.site.each_context(request),
        "title": "Dashboard",
        "subtitle": None,
        "overview_metrics": overview_metrics,
        "priority_queue": priority_queue,
        "quick_actions": quick_actions,
        "recent_purchases": PaymentSubmission.objects.select_related("user", "course").order_by("-submitted_at")[:5],
    }

    request.current_app = admin.site.name
    return render(request, "admin/dashboard.html", context)


@require_http_methods(["GET"])
def admin_root_redirect(request):
    return redirect("admin_dashboard")

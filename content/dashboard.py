from datetime import timedelta
from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from content.models import (
    Category,
    Course,
    CourseCertificate,
    CourseContent,
    CourseQuiz,
    EmailOTP,
    Module,
    ModulePurchase,
    PaymentInstruction,
    QuizAttempt,
    StudentDeviceSession,
    Subcategory,
    UserProfile,
    UserRole,
)


User = get_user_model()


def _percent(part, whole):
    if not whole:
        return 0
    return round((part / whole) * 100)


def _currency(value):
    return f"৳{Decimal(value or 0):,.2f}"


@require_http_methods(["GET"])
def admin_dashboard(request):
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    courses_count = Course.objects.count()
    modules_count = Module.objects.count()
    interactive_content_count = CourseContent.objects.filter(is_inline_reference=False).count()
    quiz_count = CourseQuiz.objects.count()
    purchase_count = ModulePurchase.objects.count()
    confirmed_purchase_count = ModulePurchase.objects.filter(is_purchased=True).count()
    pending_purchase_count = ModulePurchase.objects.filter(is_purchased=False).count()
    certificate_count = CourseCertificate.objects.count()
    total_users = User.objects.count()
    staff_users = User.objects.filter(is_staff=True).count()
    student_profiles_count = UserProfile.objects.filter(role=UserRole.STUDENT).count()
    teacher_profiles_count = UserProfile.objects.filter(role=UserRole.TEACHER).count()
    active_device_sessions = StudentDeviceSession.objects.filter(expires_at__gt=now).count()
    expired_device_sessions = StudentDeviceSession.objects.filter(expires_at__lte=now).count()
    payment_instruction_count = PaymentInstruction.objects.count()
    active_quiz_count = CourseQuiz.objects.filter(is_active=True).count()
    available_otp_count = EmailOTP.objects.filter(is_used=False, expires_at__gt=now).count()

    confirmed_revenue = (
        ModulePurchase.objects.filter(is_purchased=True).aggregate(total=Sum("course__price")).get("total")
        or Decimal("0")
    )

    courses_without_modules_qs = Course.objects.annotate(total_modules=Count("modules")).filter(total_modules=0)
    modules_without_content_qs = Module.objects.annotate(
        total_content=Count("course_contents", filter=Q(course_contents__is_inline_reference=False), distinct=True)
    ).filter(total_content=0)
    modules_without_quiz_qs = Module.objects.annotate(total_quizzes=Count("course_quizzes", distinct=True)).filter(
        total_quizzes=0
    )
    courses_with_subcategory = Course.objects.filter(subcategory__isnull=False).count()
    free_course_count = Course.objects.filter(price=0).count()
    paid_course_count = courses_count - free_course_count

    stats = {
        "courses_count": courses_count,
        "modules_count": modules_count,
        "interactive_content_count": interactive_content_count,
        "quiz_count": quiz_count,
        "purchase_count": purchase_count,
        "confirmed_purchase_count": confirmed_purchase_count,
        "pending_purchase_count": pending_purchase_count,
        "certificate_count": certificate_count,
        "total_users": total_users,
        "staff_users": staff_users,
        "student_profiles_count": student_profiles_count,
        "teacher_profiles_count": teacher_profiles_count,
        "active_device_sessions": active_device_sessions,
        "expired_device_sessions": expired_device_sessions,
        "payment_instruction_count": payment_instruction_count,
        "confirmed_revenue": _currency(confirmed_revenue),
        "free_course_count": free_course_count,
        "paid_course_count": paid_course_count,
        "active_quiz_count": active_quiz_count,
        "available_otp_count": available_otp_count,
    }

    health = {
        "courses_without_modules": courses_without_modules_qs.count(),
        "modules_without_content": modules_without_content_qs.count(),
        "modules_without_quiz": modules_without_quiz_qs.count(),
        "course_structure_coverage": _percent(courses_count - courses_without_modules_qs.count(), courses_count),
        "content_coverage": _percent(modules_count - modules_without_content_qs.count(), modules_count),
        "quiz_coverage": _percent(modules_count - modules_without_quiz_qs.count(), modules_count),
        "courses_with_subcategory": courses_with_subcategory,
        "subcategory_assignment_coverage": _percent(courses_with_subcategory, courses_count),
        "active_quiz_coverage": _percent(active_quiz_count, quiz_count),
    }

    primary_metrics = [
        {
            "label": "Confirmed Revenue",
            "value": stats["confirmed_revenue"],
            "note": f"{confirmed_purchase_count} confirmed enrollments",
            "tone": "emerald",
        },
        {
            "label": "Catalog Depth",
            "value": courses_count,
            "note": f"{modules_count} modules and {interactive_content_count} interactive items",
            "tone": "blue",
        },
        {
            "label": "Learner Accounts",
            "value": student_profiles_count,
            "note": f"{teacher_profiles_count} teacher profiles and {staff_users} staff users",
            "tone": "violet",
        },
        {
            "label": "Purchase Queue",
            "value": pending_purchase_count,
            "note": f"{purchase_count} total orders, {confirmed_purchase_count} approved",
            "tone": "amber",
        },
    ]

    secondary_metrics = [
        {
            "label": "Course Mix",
            "value": f"{paid_course_count} paid / {free_course_count} free",
            "note": "Pricing coverage across the catalog",
        },
        {
            "label": "Quiz Readiness",
            "value": f"{active_quiz_count} active",
            "note": f"{health['quiz_coverage']}% of modules have quiz support",
        },
        {
            "label": "Session Activity",
            "value": active_device_sessions,
            "note": f"{expired_device_sessions} expired sessions can be cleaned up",
        },
        {
            "label": "Verification Queue",
            "value": available_otp_count,
            "note": "Available email OTP records awaiting use or expiry",
        },
    ]

    priority_queue = [
        {
            "label": "Pending purchases",
            "value": pending_purchase_count,
            "tone": "amber" if pending_purchase_count else "emerald",
            "note": "Review payments that still need confirmation.",
            "url": reverse("admin:content_modulepurchase_changelist"),
        },
        {
            "label": "Courses without modules",
            "value": health["courses_without_modules"],
            "tone": "rose" if health["courses_without_modules"] else "emerald",
            "note": "Catalog entries that do not yet have lesson structure.",
            "url": reverse("admin:content_course_changelist"),
        },
        {
            "label": "Modules missing content",
            "value": health["modules_without_content"],
            "tone": "amber" if health["modules_without_content"] else "emerald",
            "note": "Modules published without interactive learning material.",
            "url": reverse("admin:content_module_changelist"),
        },
        {
            "label": "Modules missing quizzes",
            "value": health["modules_without_quiz"],
            "tone": "amber" if health["modules_without_quiz"] else "emerald",
            "note": "Learning units missing comprehension checks.",
            "url": reverse("admin:content_coursequiz_changelist"),
        },
        {
            "label": "Payment instructions",
            "value": payment_instruction_count,
            "tone": "emerald" if payment_instruction_count else "rose",
            "note": "Operational payment methods exposed to students.",
            "url": reverse("admin:content_paymentinstruction_changelist"),
        },
    ]

    quick_actions = [
        {"label": "Create Course", "url": reverse("admin:content_course_add"), "tone": "primary"},
        {"label": "Create Module", "url": reverse("admin:content_module_add"), "tone": "secondary"},
        {"label": "Add Quiz", "url": reverse("admin:content_coursequiz_add"), "tone": "secondary"},
        {"label": "Review Purchases", "url": reverse("admin:content_modulepurchase_changelist"), "tone": "secondary"},
    ]

    management_sections = [
        {
            "title": "Curriculum",
            "note": "Build and maintain the learning catalog.",
            "items": [
                {"label": "Categories", "count": Category.objects.count(), "url": reverse("admin:content_category_changelist")},
                {"label": "Subcategories", "count": Subcategory.objects.count(), "url": reverse("admin:content_subcategory_changelist")},
                {"label": "Courses", "count": courses_count, "url": reverse("admin:content_course_changelist")},
                {"label": "Modules", "count": modules_count, "url": reverse("admin:content_module_changelist")},
                {"label": "Content Items", "count": interactive_content_count, "url": reverse("admin:content_coursecontent_changelist")},
                {"label": "Quizzes", "count": quiz_count, "url": reverse("admin:content_coursequiz_changelist")},
            ],
        },
        {
            "title": "Commerce",
            "note": "Approve purchases and manage learner entitlements.",
            "items": [
                {"label": "Purchases", "count": purchase_count, "url": reverse("admin:content_modulepurchase_changelist")},
                {"label": "Certificates", "count": certificate_count, "url": reverse("admin:content_coursecertificate_changelist")},
                {"label": "Payment Instructions", "count": payment_instruction_count, "url": reverse("admin:content_paymentinstruction_changelist")},
            ],
        },
        {
            "title": "People",
            "note": "Support admin, teacher, and student account operations.",
            "items": [
                {"label": "Users", "count": total_users, "url": reverse("admin:auth_user_changelist")},
                {"label": "Profiles", "count": UserProfile.objects.count(), "url": reverse("admin:content_userprofile_changelist")},
                {"label": "Sessions", "count": active_device_sessions, "url": reverse("admin:content_studentdevicesession_changelist")},
                {"label": "Email OTPs", "count": EmailOTP.objects.count(), "url": reverse("admin:content_emailotp_changelist")},
                {"label": "Groups", "count": None, "url": reverse("admin:auth_group_changelist")},
            ],
        },
    ]

    latest_modules = Module.objects.select_related("course").order_by("-created_at")[:6]
    recent_purchases = ModulePurchase.objects.select_related("user", "course").order_by("-purchased_at")[:6]
    recent_attempts = QuizAttempt.objects.select_related("user", "quiz", "quiz__module").order_by("-submitted_at")[:6]
    recent_signups = User.objects.order_by("-date_joined")[:6]
    recent_content = (
        CourseContent.objects.filter(is_inline_reference=False)
        .select_related("module", "module__course")
        .order_by("-created_at")[:6]
    )

    top_courses = (
        Course.objects.select_related("subcategory", "subcategory__category")
        .annotate(
            module_total=Count("modules", distinct=True),
            content_total=Count(
                "modules__course_contents",
                filter=Q(modules__course_contents__is_inline_reference=False),
                distinct=True,
            ),
            confirmed_sales=Count("purchases", filter=Q(purchases__is_purchased=True), distinct=True),
        )
        .order_by("-confirmed_sales", "-module_total", "name")[:5]
    )

    content_type_breakdown = list(
        CourseContent.objects.filter(is_inline_reference=False)
        .values("content_type")
        .annotate(total=Count("id"))
        .order_by("-total", "content_type")
    )

    learning_mix = [
        {
            "label": item["content_type"].replace("_", " ").title(),
            "total": item["total"],
            "share": _percent(item["total"], interactive_content_count),
        }
        for item in content_type_breakdown
    ]

    signup_summary = {
        "last_7_days": User.objects.filter(date_joined__gte=week_ago).count(),
        "last_30_days": User.objects.filter(date_joined__gte=month_ago).count(),
        "recent_purchase_count": ModulePurchase.objects.filter(purchased_at__gte=week_ago).count(),
        "recent_attempt_count": QuizAttempt.objects.filter(submitted_at__gte=week_ago).count(),
    }

    context = {
        **admin.site.each_context(request),
        "title": "Dashboard",
        "subtitle": None,
        "stats": stats,
        "health": health,
        "primary_metrics": primary_metrics,
        "secondary_metrics": secondary_metrics,
        "priority_queue": priority_queue,
        "quick_actions": quick_actions,
        "management_sections": management_sections,
        "latest_modules": latest_modules,
        "recent_purchases": recent_purchases,
        "recent_attempts": recent_attempts,
        "recent_signups": recent_signups,
        "recent_content": recent_content,
        "top_courses": top_courses,
        "learning_mix": learning_mix,
        "signup_summary": signup_summary,
        "courses_without_modules_sample": courses_without_modules_qs.order_by("name")[:5],
        "modules_without_content_sample": modules_without_content_qs.select_related("course").order_by("course__name", "title")[:5],
        "modules_without_quiz_sample": modules_without_quiz_qs.select_related("course").order_by("course__name", "title")[:5],
        "now": now,
    }

    request.current_app = admin.site.name
    return render(request, "admin/dashboard.html", context)


@require_http_methods(["GET"])
def admin_root_redirect(request):
    return redirect("admin_dashboard")

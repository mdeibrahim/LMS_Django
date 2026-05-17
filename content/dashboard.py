from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from django.apps import apps
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch

from content.models import (
    Course,
    CourseCertificate,
    CourseContent,
    CourseQuiz,
    Module,
    ModulePurchase,
    PaymentInstruction,
    QuizAttempt,
    StudentDeviceSession,
    UserProfile,
    UserRole,
)


User = get_user_model()


def _percent(part, whole):
    if not whole:
        return 0
    return round((part / whole) * 100)


@require_http_methods(["GET"])
def admin_dashboard(request):
    """
    Admin dashboard with overview statistics and content health insights.
    """
    courses_count = Course.objects.count()
    modules_count = Module.objects.count()
    content_count = CourseContent.objects.count()
    quiz_count = CourseQuiz.objects.count()
    purchase_count = ModulePurchase.objects.count()
    confirmed_purchase_count = ModulePurchase.objects.filter(is_purchased=True).count()
    pending_purchase_count = purchase_count - confirmed_purchase_count
    certificate_count = CourseCertificate.objects.count()
    total_users = User.objects.count()
    staff_users = User.objects.filter(is_staff=True).count()
    student_profiles_count = UserProfile.objects.filter(role=UserRole.STUDENT).count()
    teacher_profiles_count = UserProfile.objects.filter(role=UserRole.TEACHER).count()
    active_device_sessions = StudentDeviceSession.objects.filter(expires_at__gt=timezone.now()).count()
    payment_instruction_count = PaymentInstruction.objects.count()

    stats = {
        "courses_count": courses_count,
        "modules_count": modules_count,
        "content_count": content_count,
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
        "payment_instruction_count": payment_instruction_count,
    }

    courses_without_modules = Course.objects.annotate(
        total_modules=Count("modules")
    ).filter(total_modules=0).count()
    modules_without_content = Module.objects.annotate(
        total_content=Count("course_contents")
    ).filter(total_content=0).count()
    modules_without_quiz = Module.objects.annotate(
        total_quizzes=Count("course_quizzes")
    ).filter(total_quizzes=0).count()
    courses_with_subcategory = Course.objects.filter(subcategory__isnull=False).count()

    health = {
        "courses_without_modules": courses_without_modules,
        "modules_without_content": modules_without_content,
        "modules_without_quiz": modules_without_quiz,
        "course_structure_coverage": _percent(courses_count - courses_without_modules, courses_count),
        "content_coverage": _percent(modules_count - modules_without_content, modules_count),
        "quiz_coverage": _percent(modules_count - modules_without_quiz, modules_count),
        "courses_with_subcategory": courses_with_subcategory,
        "subcategory_assignment_coverage": _percent(courses_with_subcategory, courses_count),
    }

    latest_modules = Module.objects.select_related("course").order_by("-created_at")[:6]
    recent_purchases = ModulePurchase.objects.select_related("user", "course").order_by("-purchased_at")[:6]
    recent_attempts = QuizAttempt.objects.select_related("user", "quiz", "quiz__module").order_by("-submitted_at")[:6]
    content_type_breakdown = list(
        CourseContent.objects.values("content_type").annotate(total=Count("id")).order_by("-total", "content_type")
    )

    # Build a dynamic list of admin-managed models for the sidebar
    admin_models = []
    try:
        app_config = apps.get_app_config('content')
    except LookupError:
        app_config = None

    if app_config:
        for model in app_config.get_models():
            # only show models that are registered in the admin site
            if model not in admin.site._registry:
                continue
            meta = model._meta
            try:
                changelist = reverse('admin:%s_%s_changelist' % (meta.app_label, meta.model_name))
            except NoReverseMatch:
                changelist = None
            try:
                obj_count = model._default_manager.count()
            except Exception:
                obj_count = None

            label = str(getattr(meta, 'verbose_name_plural', None) or meta.model_name).title()
            admin_models.append({
                'label': label,
                'url': changelist,
                'count': obj_count,
            })
    admin_models.sort(key=lambda item: item["label"])

    context = {
        **admin.site.each_context(request),
        "stats": stats,
        "health": health,
        "latest_modules": latest_modules,
        "recent_purchases": recent_purchases,
        "recent_attempts": recent_attempts,
        "content_type_breakdown": content_type_breakdown,
        "admin_models": admin_models,
        "title": "Dashboard",
        "subtitle": None,
    }

    request.current_app = admin.site.name
    return render(request, "admin/dashboard.html", context)


@require_http_methods(["GET"])
def admin_root_redirect(request):
    return redirect("admin_dashboard")

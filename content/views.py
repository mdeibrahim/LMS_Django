import json
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST, require_http_methods

from .forms import ProfileUpdateForm
from .models import (
    Category,
    Course,
    CourseCertificate,
    CourseEnrollment,
    CourseQuiz,
    Lesson,
    LessonResource,
    LessonResourceType,
    Module,
    PaymentInstruction,
    PaymentSubmission,
    PaymentSubmissionStatus,
    QuizAttempt,
)
from .services import (
    create_or_update_payment_submission,
    ensure_enrollment,
    ensure_primary_lesson,
    ensure_profile,
    get_owned_course_ids,
    has_course_access,
    visible_lessons_qs,
)
from .utils import send_payment_submission_email


def home(request):
    courses = Course.objects.select_related("subcategory__category").prefetch_related("modules").all()
    owned_course_ids = get_owned_course_ids(request.user)
    categories = Category.objects.filter(subcategories__courses__isnull=False).distinct().order_by("name")
    return render(
        request,
        "content/home.html",
        {
            "courses": courses,
            "owned_course_ids": owned_course_ids,
            "categories": categories,
        },
    )


def course_detail(request, course_slug):
    course = get_object_or_404(Course.objects.select_related("subcategory__category"), slug=course_slug)
    has_access = has_course_access(request.user, course)
    modules = list(
        course.modules.prefetch_related(
            Prefetch("lessons", queryset=visible_lessons_qs()),
        ).all()
    )

    for module in modules:
        module_lessons = list(module.lessons.all())
        module.lesson_count = len(module_lessons)
        module.resource_count = 0
        module.quiz_count = 0
        module.lesson_items = []
        module.quiz_items = []

        for lesson in module_lessons:
            resources = list(lesson.resources.all())
            quizzes = list(getattr(lesson, "quizzes").all())
            module.resource_count += len(resources)
            module.quiz_count += len(quizzes)
            module.lesson_items.append(
                {
                    "lesson": lesson,
                    "resource_count": len(resources),
                    "is_accessible": has_access or lesson.is_preview,
                }
            )
            for quiz in quizzes:
                module.quiz_items.append(
                    {
                        "quiz": quiz,
                        "lesson": lesson,
                        "is_accessible": has_access or lesson.is_preview,
                    }
                )

        module_quizzes = list(module.course_quizzes.all())
        module.quiz_count += len(module_quizzes)
        for quiz in module_quizzes:
            module.quiz_items.append(
                {
                    "quiz": quiz,
                    "lesson": None,
                    "is_accessible": has_access,
                }
            )

    related_courses = Course.objects.exclude(id=course.id).prefetch_related("modules")[:3]
    owned_course_ids = get_owned_course_ids(request.user)

    return render(
        request,
        "content/course_detail.html",
        {
            "course": course,
            "modules": modules,
            "has_access": has_access,
            "related_courses": related_courses,
            "owned_course_ids": owned_course_ids,
        },
    )


def module_detail(request, course_slug, module_slug):
    course = get_object_or_404(Course, slug=course_slug)
    module = get_object_or_404(Module, course=course, slug=module_slug)
    return redirect(f"{reverse('content:course_detail', args=[course.slug])}#module-{module.id}")


@staff_member_required
def module_editor(request, course_slug, module_slug):
    course = get_object_or_404(Course, slug=course_slug)
    module = get_object_or_404(
        Module.objects.prefetch_related(
            Prefetch("lessons", queryset=Lesson.objects.order_by("order", "created_at")),
        ),
        course=course,
        slug=module_slug,
    )
    lesson = ensure_primary_lesson(module)
    resources = list(lesson.resources.order_by("order", "created_at").all())
    first_content = resources[0] if resources else None
    return render(
        request,
        "content/subject_editor.html",
        {
            "course": course,
            "module": module,
            "lesson": lesson,
            "editor_label": "Module",
            "editor_title": module.title,
            "editor_body_content": module.body_content,
            "resources": resources,
            "resources_payload": [_serialize_resource(resource) for resource in resources],
            "preview_url": (
                reverse("content:lesson_detail", args=[course.slug, module.slug, lesson.slug])
                if first_content
                else reverse("content:course_detail", args=[course.slug])
            ),
            "save_url": reverse("content:api_subject_save", args=[module.id]),
            "ic_create_url": reverse("content:api_ic_create", args=[module.id]),
        },
    )


@staff_member_required
def lesson_editor(request, course_slug, module_slug, lesson_slug):
    course = get_object_or_404(Course, slug=course_slug)
    module = get_object_or_404(
        Module.objects.prefetch_related(
        ),
        course=course,
        slug=module_slug,
    )
    lesson = get_object_or_404(
        Lesson.objects.prefetch_related(
            Prefetch("resources", queryset=LessonResource.objects.order_by("order", "created_at")),
        ),
        module=module,
        slug=lesson_slug,
    )
    resources = list(lesson.resources.all())
    return render(
        request,
        "content/subject_editor.html",
        {
            "course": course,
            "module": module,
            "lesson": lesson,
            "editor_label": "Lesson",
            "editor_title": lesson.title,
            "editor_body_content": lesson.body_content,
            "resources": resources,
            "resources_payload": [_serialize_resource(resource) for resource in resources],
            "preview_url": reverse("content:lesson_detail", args=[course.slug, module.slug, lesson.slug]),
            "save_url": reverse("content:api_lesson_save", args=[lesson.id]),
            "ic_create_url": reverse("content:api_lesson_ic_create", args=[lesson.id]),
        },
    )


def play_video(request, course_slug, module_slug, video_id):
    resource = get_object_or_404(
        LessonResource.objects.select_related("lesson", "lesson__module", "lesson__module__course"),
        id=video_id,
        lesson__module__slug=module_slug,
        lesson__module__course__slug=course_slug,
    )
    return redirect(
        "content:lesson_detail",
        course_slug=resource.lesson.module.course.slug,
        module_slug=resource.lesson.module.slug,
        lesson_slug=resource.lesson.slug,
    )


def lesson_detail(request, course_slug, module_slug, lesson_slug):
    course = get_object_or_404(Course, slug=course_slug)
    module = get_object_or_404(
        Module.objects.prefetch_related(
            Prefetch("lessons", queryset=visible_lessons_qs()),
        ),
        course=course,
        slug=module_slug,
    )
    lesson = get_object_or_404(
        Lesson.objects.prefetch_related(
            Prefetch("resources", queryset=LessonResource.objects.filter(is_published=True).order_by("order", "created_at")),
            Prefetch("quizzes", queryset=CourseQuiz.objects.filter(is_active=True).prefetch_related("questions")),
        ),
        module=module,
        slug=lesson_slug,
        is_published=True,
    )

    has_access = has_course_access(request.user, course) or lesson.is_preview
    if not has_access:
        return redirect("content:course_detail", course.slug)

    module_lessons = list(module.lessons.all())
    lesson_navigation = [
        {
            "lesson": sibling,
            "is_current": sibling.id == lesson.id,
        }
        for sibling in module_lessons
    ]
    quizzes = list(lesson.quizzes.all())

    return render(
        request,
        "content/lesson_detail.html",
        {
            "course": course,
            "module": module,
            "lesson": lesson,
            "resources": list(lesson.resources.all()),
            "lesson_navigation": lesson_navigation,
            "quizzes": quizzes,
            "has_access": has_access,
        },
    )


@require_http_methods(["GET", "POST"])
def quiz_detail(request, course_slug, module_slug, quiz_id, lesson_slug=None):
    course = get_object_or_404(Course, slug=course_slug)
    module = get_object_or_404(Module, course=course, slug=module_slug)
    
    if lesson_slug:
        lesson = get_object_or_404(Lesson, module=module, slug=lesson_slug, is_published=True)
        quiz = get_object_or_404(
            CourseQuiz.objects.prefetch_related("questions"),
            id=quiz_id,
            lesson=lesson,
            is_active=True,
        )
        has_access = has_course_access(request.user, course) or lesson.is_preview
    else:
        lesson = None
        quiz = get_object_or_404(
            CourseQuiz.objects.prefetch_related("questions"),
            id=quiz_id,
            module=module,
            is_active=True,
        )
        has_access = has_course_access(request.user, course)

    if not has_access:
        return redirect("content:course_detail", course.slug)

    questions = list(quiz.questions.all())
    submission = None
    score = None
    passed = None

    if request.method == "POST":
        total = len(questions)
        correct = 0
        for question in questions:
            answer = (request.POST.get(f"question_{question.id}") or "").upper()
            question.selected_option = answer
            question.is_correct = answer == question.correct_option
            if question.is_correct:
                correct += 1

        score = round((correct / total) * 100) if total else 0
        passed = score >= quiz.pass_score
        submission = {
            "score": score,
            "correct": correct,
            "total": total,
            "passed": passed,
        }
        if request.user.is_authenticated:
            QuizAttempt.objects.create(user=request.user, quiz=quiz, score=score)

    return render(
        request,
        "content/quiz_detail.html",
        {
            "course": course,
            "module": module,
            "lesson": lesson,
            "quiz": quiz,
            "questions": questions,
            "submission": submission,
        },
    )


@login_required
def my_modules(request):
    enrollments = CourseEnrollment.objects.filter(
        user=request.user,
        status="active",
    ).select_related("course")
    return render(request, "content/my_modules.html", {"purchases": enrollments})


@login_required
def profile_page(request):
    profile = ensure_profile(request.user)
    form = ProfileUpdateForm(request.POST or None, request.FILES or None, user=request.user, profile=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated successfully.")
        return redirect("content:profile")
    return render(request, "content/profile.html", {"form": form, "profile": profile})


@login_required
def student_dashboard(request):
    enrollments = CourseEnrollment.objects.filter(
        user=request.user,
        # status="active",
    ).select_related("course")
    purchased_course_ids = set(enrollments.values_list("course_id", flat=True))
    available_courses = Course.objects.exclude(id__in=purchased_course_ids)
    certificate_map = {
        certificate.course_id: certificate
        for certificate in CourseCertificate.objects.filter(user=request.user).select_related("course")
    }

    purchased_cards = [
        {
            "purchase": enrollment,
            "progress": 0,
            "is_completed": False,
            "has_access": has_course_access(request.user, enrollment.course),
            "certificate": certificate_map.get(enrollment.course_id),
            "status": enrollment.status,
            "course_cover_image": enrollment.course.cover_image,
        }
        for enrollment in enrollments
    ]

    return render(
        request,
        "content/student_dashboard.html",
        {
            "purchased_cards": purchased_cards,
            "available_courses": available_courses[:12],
            "certificates": list(certificate_map.values()),
        },
    )


@login_required
@require_POST
def claim_certificate(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    if not has_course_access(request.user, course):
        messages.error(request, "You do not have access to this course.")
        return redirect("content:student_dashboard")

    if not course.modules.exists():
        messages.error(request, "No modules are available for this course yet.")
        return redirect("content:student_dashboard")

    certificate, created = CourseCertificate.objects.get_or_create(
        user=request.user,
        course=course,
        defaults={"certificate_code": _generate_certificate_code()},
    )
    if created:
        messages.success(request, f"Certificate issued successfully: {certificate.certificate_code}")
    else:
        messages.info(request, f"Certificate already issued: {certificate.certificate_code}")
    return redirect("content:student_dashboard")


# def login_selector(request):
#     if request.user.is_authenticated:
#         return redirect("content:home")
#     return render(request, "registration/login.html")


# def signup_selector(request):
#     if request.user.is_authenticated:
#         return redirect("content:home")
#     return render(request, "registration/signup.html")


# def login_selector(request):
#     if request.user.is_authenticated:
#         return redirect("content:home")
#     return render(request, "registration/login.html")


# def signup_selector(request):
#     if request.user.is_authenticated:
#         return redirect("content:home")
#     return render(request, "registration/signup.html")


@login_required
@require_POST
def buy_module(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug)
    if course.is_free:
        ensure_enrollment(request.user, course)
        messages.success(request, f'"{course.name}" is now added to your account (free course).')
        return redirect("content:course_detail", course_slug=course.slug)

    messages.info(request, "Paid courses require payment review before access is granted.")
    return redirect("content:course_purchase", course_slug=course.slug)


@login_required
def start_purchase(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug)

    if course.is_free:
        ensure_enrollment(request.user, course)
        messages.success(request, f'"{course.name}" is now added to your account (free course).')
        return redirect("content:course_detail", course_slug=course.slug)

    if has_course_access(request.user, course):
        messages.info(request, f'You already have access to "{course.name}".')
        return redirect("content:course_detail", course_slug=course.slug)

    return redirect("content:course_purchase", course_slug=course.slug)


@login_required
def course_purchase(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug)
    payment_instructions = PaymentInstruction.objects.order_by("payment_method_name").all()
    latest_submission = (
        PaymentSubmission.objects.filter(user=request.user, course=course).order_by("-submitted_at").first()
    )
    return render(
        request,
        "content/course_purchase.html",
        {
            "course": course,
            "payment_instructions": payment_instructions,
            "latest_submission": latest_submission,
            "has_access": has_course_access(request.user, course),
        },
    )


@login_required
@require_POST
def submit_payment_details(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug)
    transaction_id = (request.POST.get("transaction_id") or "").strip()
    bkash_phone_number = (request.POST.get("bkash_phone_number") or "").strip()
    note = (request.POST.get("note") or "").strip()
    payment_method = (request.POST.get("payment_method") or request.POST.get("payment_method_display") or "").strip()

    if course.is_free:
        ensure_enrollment(request.user, course)
        messages.success(request, f'"{course.name}" is free and has been added to your account.')
        return redirect("content:course_detail", course_slug=course.slug)

    if not transaction_id:
        messages.error(request, "Please provide a transaction ID.")
        return redirect("content:course_purchase", course_slug=course.slug)

    if not bkash_phone_number:
        messages.error(request, "Please provide your Bkash Number")
        return redirect("content:course_purchase", course_slug=course.slug)

    submission = create_or_update_payment_submission(
        user=request.user,
        course=course,
        payment_method=payment_method or "other",
        transaction_id=transaction_id,
        bkash_phone_number = bkash_phone_number,
        note=note,
    )

    sent = send_payment_submission_email(
        user=request.user,
        course=course,
        amount=getattr(course, "price", 0),
        payment_method=payment_method,
        bkash_phone_number = bkash_phone_number,
        transaction_id=transaction_id,
        note=note,
    )

    if sent:
        messages.success(request, "Payment details submitted. Access will be granted after admin approval.")
    else:
        messages.warning(
            request,
            "Payment details were saved for review, but notification email could not be sent automatically.",
        )

    return redirect("content:student_dashboard")


def _generate_certificate_code():
    return f"CERT-{uuid.uuid4().hex[:12].upper()}"


def get_course_content(request, content_id):
    content = get_object_or_404(LessonResource.objects.select_related("lesson", "lesson__module", "lesson__module__course"), id=content_id)

    if not (
        has_course_access(request.user, content.lesson.module.course)
        or content.is_preview
        or content.lesson.is_preview
    ):
        return JsonResponse({"detail": "Access denied."}, status=403)

    return JsonResponse(_serialize_resource(content))


def get_lesson_resource(request, content_id):
    return get_course_content(request, content_id)


def _serialize_resource(resource):
    file_url = resource.file.url if resource.file else ""
    youtube_embed_url = resource.get_youtube_embed_url()
    content_type = resource.content_type
    if content_type == LessonResourceType.VIDEO and youtube_embed_url:
        content_type = "youtube"

    external_url = resource.external_url or ""

    if resource.content_type == LessonResourceType.IMAGE:
        image_url = file_url or external_url
    else:
        image_url = ""

    if resource.content_type == LessonResourceType.AUDIO:
        audio_url = file_url or external_url
    else:
        audio_url = ""

    if resource.content_type == LessonResourceType.VIDEO:
        video_url = file_url or external_url
    else:
        video_url = ""

    return {
        "ok": True,
        "id": resource.id,
        "lesson_id": resource.lesson_id,
        "module_id": resource.lesson.module_id,
        "title": resource.title,
        "content_type": content_type,
        "text_content": resource.text_content or "",
        "file_url": file_url,
        "image_url": image_url,
        "audio_url": audio_url,
        "video_url": video_url,
        "youtube_url": external_url if resource.get_youtube_embed_url() else "",
        "youtube_embed_url": youtube_embed_url,
        "external_url": external_url,
        "embed_url": resource.embed_url or "",
        "duration_seconds": resource.duration_seconds,
        "created_at": resource.created_at.isoformat(),
    }


def _serialize_accordion(section):
    return {
        "id": section.id,
        "module_id": section.module_id,
        "title": section.title,
        "content": section.content or "",
        "order": section.order,
        "is_open_by_default": section.is_open_by_default,
        "created_at": section.created_at.isoformat(),
    }


def _parse_api_payload(request):
    if request.content_type and "multipart" in request.content_type:
        return request.POST, request.FILES, None
    try:
        data = json.loads(request.body or "{}")
        return data, {}, None
    except Exception:
        return None, None, JsonResponse({"ok": False, "error": "Invalid body"}, status=400)


@staff_member_required
@require_http_methods(["POST"])
def api_subject_save(request, module_id):
    module = get_object_or_404(Module, id=module_id)
    data, _, error = _parse_api_payload(request)
    if error:
        return error

    lesson = ensure_primary_lesson(module)
    module.title = (data.get("title") or module.title).strip() or module.title
    module.body_content = data.get("body_content", module.body_content or "")
    lesson.title = module.title
    lesson.body_content = module.body_content
    module.save(update_fields=["title", "body_content", "updated_at"])
    lesson.save(update_fields=["title", "body_content", "updated_at"])

    return JsonResponse(
        {
            "ok": True,
            "module": {
                "id": module.id,
                "title": module.title,
                "body_content": module.body_content,
                "updated_at": module.updated_at.isoformat() if module.updated_at else "",
            },
        }
    )


@staff_member_required
@require_http_methods(["POST"])
def api_lesson_save(request, lesson_id):
    lesson = get_object_or_404(Lesson.objects.select_related("module"), id=lesson_id)
    data, _, error = _parse_api_payload(request)
    if error:
        return error

    lesson.title = (data.get("title") or lesson.title).strip() or lesson.title
    lesson.body_content = data.get("body_content", lesson.body_content or "")
    lesson.save(update_fields=["title", "body_content", "updated_at"])

    return JsonResponse(
        {
            "ok": True,
            "lesson": {
                "id": lesson.id,
                "title": lesson.title,
                "body_content": lesson.body_content,
                "updated_at": lesson.updated_at.isoformat() if lesson.updated_at else "",
            },
        }
    )


@staff_member_required
@require_http_methods(["POST"])
def api_ic_create(request, module_id):
    module = get_object_or_404(Module, id=module_id)
    lesson = ensure_primary_lesson(module)
    data, files, error = _parse_api_payload(request)
    if error:
        return error

    resource = LessonResource(
        lesson=lesson,
        title=(data.get("title") or "Untitled").strip() or "Untitled",
        content_type=data.get("content_type", LessonResourceType.TEXT),
        order=lesson.resources.count() + 1,
        is_preview=lesson.is_preview,
        is_published=True,
        text_content=data.get("text_content", ""),
        external_url=data.get("youtube_url") or data.get("external_url") or "",
        embed_url=data.get("embed_url") or "",
    )

    uploaded_file = files.get("image") or files.get("audio") or files.get("video") or files.get("file")
    if uploaded_file:
        resource.file = uploaded_file

    if resource.content_type == LessonResourceType.VIDEO and data.get("video_url"):
        resource.external_url = data.get("video_url")

    resource.slug = _build_resource_slug(resource.title, lesson)
    resource.save()
    return JsonResponse(_serialize_resource(resource), status=201)


@staff_member_required
@require_http_methods(["POST"])
def api_lesson_ic_create(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    data, files, error = _parse_api_payload(request)
    if error:
        return error

    resource = LessonResource(
        lesson=lesson,
        title=(data.get("title") or "Untitled").strip() or "Untitled",
        content_type=data.get("content_type", LessonResourceType.TEXT),
        order=lesson.resources.count() + 1,
        is_preview=lesson.is_preview,
        is_published=True,
        text_content=data.get("text_content", ""),
        external_url=data.get("youtube_url") or data.get("external_url") or "",
        embed_url=data.get("embed_url") or "",
    )

    uploaded_file = files.get("image") or files.get("audio") or files.get("video") or files.get("file")
    if uploaded_file:
        resource.file = uploaded_file

    if resource.content_type == LessonResourceType.VIDEO and data.get("video_url"):
        resource.external_url = data.get("video_url")

    resource.slug = _build_resource_slug(resource.title, lesson)
    resource.save()
    return JsonResponse(_serialize_resource(resource), status=201)


@staff_member_required
@require_http_methods(["POST"])
def api_ic_update(request, ic_id):
    resource = get_object_or_404(LessonResource, id=ic_id)
    data, files, error = _parse_api_payload(request)
    if error:
        return error

    if "content_type" in data:
        resource.content_type = data["content_type"]
    if "title" in data:
        resource.title = (data.get("title") or resource.title).strip() or resource.title
    if "text_content" in data:
        resource.text_content = data["text_content"]
    if "youtube_url" in data:
        resource.external_url = data["youtube_url"]
    if "external_url" in data:
        resource.external_url = data["external_url"]
    if "embed_url" in data:
        resource.embed_url = data["embed_url"]
    if "video_url" in data and data["video_url"]:
        resource.external_url = data["video_url"]

    uploaded_file = files.get("image") or files.get("audio") or files.get("video") or files.get("file")
    if uploaded_file:
        resource.file = uploaded_file

    if not resource.slug:
        resource.slug = _build_resource_slug(resource.title, resource.lesson)
    resource.save()
    return JsonResponse(_serialize_resource(resource))


@staff_member_required
@require_http_methods(["POST"])
def api_ic_delete(request, ic_id):
    resource = get_object_or_404(LessonResource, id=ic_id)
    resource.delete()
    return JsonResponse({"ok": True})



def _build_resource_slug(title, lesson):
    base = (title or "resource").strip().lower().replace(" ", "-")
    base = "".join(ch for ch in base if ch.isalnum() or ch == "-").strip("-") or "resource"
    slug = base
    counter = 2
    while lesson.resources.exclude(pk=getattr(lesson, "pk", None)).filter(slug=slug).exists():
        slug = f"{base}-{counter}"
        counter += 1
    return slug


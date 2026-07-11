import json
import random
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods

from .forms import EmailLoginForm, ProfileUpdateForm, StudentSignupForm
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
    UserRole,
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
from .firebase import verify_id_token
from .utils import send_payment_submission_email, send_verification_email


User = get_user_model()


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
    # accordion_sections = list(module.accordion_sections.all())
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
            # "accordion_sections": accordion_sections,
            "resources_payload": [_serialize_resource(resource) for resource in resources],
            # "accordion_sections_payload": [_serialize_accordion(section) for section in accordion_sections],
            "preview_url": reverse("content:lesson_detail", args=[course.slug, module.slug, lesson.slug]),
            "save_url": reverse("content:api_lesson_save", args=[lesson.id]),
            "ic_create_url": reverse("content:api_lesson_ic_create", args=[lesson.id]),
            # "acc_create_url": reverse("content:api_accordion_create", args=[module.id]),
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
            # Prefetch("accordion_sections", queryset=ModuleAccordionSection.objects.order_by("order", "created_at")),
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
            # "accordion_sections": list(module.accordion_sections.all()),
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
        # Module quizzes require course access or we can check if module is somehow free
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


def login_selector(request):
    if request.user.is_authenticated:
        return redirect("content:home")
    return render(request, "registration/login.html")


def signup_selector(request):
    if request.user.is_authenticated:
        return redirect("content:home")
    return render(request, "registration/signup.html")


def student_login(request):
    return _role_login(request, template_name="registration/student_login.html")


def student_signup(request):
    return _role_signup(request, template_name="registration/student_signup.html")


def signup(request):
    return signup_selector(request)


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


def _role_login(request, template_name):
    if request.user.is_authenticated:
        return redirect("content:home")

    form = EmailLoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email_or_phone = form.cleaned_data["email"].strip()
        password = form.cleaned_data["password"]
        
        # Check if it looks like a phone number (digits and optional '+' prefix)
        looks_like_phone = email_or_phone.replace('+', '').isdigit()

        if looks_like_phone:
            matched_users = User.objects.filter(phone_number=email_or_phone)
        else:
            matched_users = User.objects.filter(email__iexact=email_or_phone)
            
        if matched_users.count() > 1:
            form.add_error("email", "Multiple accounts found with this credential. Please contact support.")
            return render(request, template_name, {"form": form})

        user_obj = matched_users.first()
        if not user_obj:
            form.add_error("email", "No account found with this credential.")
            return render(request, template_name, {"form": form})

        user = authenticate(request=request, email=user_obj.email, password=password)
        if not user:
            form.add_error("password", "Invalid credentials.")
            return render(request, template_name, {"form": form})

        profile = ensure_profile(user)
        if profile.role != UserRole.STUDENT and not (user.is_staff or user.is_superuser):
            form.add_error("email", "This login flow is only available for student accounts.")
            return render(request, template_name, {"form": form})

        login(request, user)
        messages.success(request, f"Welcome back, {user.get_full_name() or user.email}!")
        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url:
            return redirect(next_url)
        return redirect("content:student_dashboard" if profile.role == UserRole.STUDENT else "content:home")

    return render(
        request,
        template_name,
        {
            "form": form,
            "firebase_config": _firebase_web_config(),
        },
    )


def generate_otp(user):
    from .models import EmailOTP

    # delete previous all otp then generate
    EmailOTP.objects.filter(user=user).delete()

    code = f"{random.randint(100000, 999999)}"
    expires = timezone.now() + timedelta(minutes=15)
    EmailOTP.objects.create(user=user, code=code, expires_at=expires)
    return code

    
def _role_signup(request, template_name):
    if request.user.is_authenticated:
        return redirect("content:home")

    form = StudentSignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        form.save_profile(user=user, role=UserRole.STUDENT)

        code = generate_otp(user)

        sent = send_verification_email(user, code)
        if not sent:
            messages.info(request, f"OTP for verification: {code}")

        request.session["pending_otp_user"] = user.id
        return redirect("content:otp_verify")

    return render(
        request,
        template_name,
        {
            "form": form,
            "firebase_config": _firebase_web_config(),
        },
    )


def otp_verify(request):
    from .forms import OTPForm
    from .models import EmailOTP

    user_id = request.session.get("pending_otp_user")
    if not user_id:
        messages.error(request, "No pending verification found. Please sign up first.")
        return redirect("content:signup")

    user = get_object_or_404(User, id=user_id)
    profile = ensure_profile(user)
    lock_key = f"otp:lockout:{user.id}"
    if cache.get(lock_key):
        messages.error(request, "Too many failed attempts. Please try again later.")
        return redirect("content:signup")

    form = OTPForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        code = form.cleaned_data["code"].strip()
        otp_qs = EmailOTP.objects.filter(user=user, code=code, is_used=False, expires_at__gte=timezone.now())
        if otp_qs.exists():
            otp = otp_qs.first()
            otp.is_used = True
            otp.save(update_fields=["is_used"])
            cache.delete(f"otp:attempt:{user.id}")
            login(request, user)
            request.session.pop("pending_otp_user", None)
            user.is_verified = True
            user.is_active = True
            user.save(update_fields=["is_verified", "is_active"])
            messages.success(request, "Your account is verified and you are now logged in.")
            return redirect("content:student_dashboard" if profile.role == UserRole.STUDENT else "content:home")

        attempt_key = f"otp:attempt:{user.id}"
        try:
            if cache.get(attempt_key) is None:
                cache.add(attempt_key, 1, timeout=getattr(settings, "OTP_ATTEMPT_WINDOW", 300))
            else:
                cache.incr(attempt_key)
        except Exception:
            pass

        attempts = cache.get(attempt_key) or 0
        if attempts >= getattr(settings, "OTP_ATTEMPT_LIMIT", 5):
            try:
                cache.set(lock_key, True, timeout=getattr(settings, "OTP_LOCKOUT_SECONDS", 600))
            except Exception:
                pass
            messages.error(request, "Too many failed attempts. Please try again later.")
            return redirect("content:signup")

        form.add_error("code", "Invalid or expired code.")

    return render(request, "registration/otp_verify.html", {"form": form, "email": user.email})


def otp_resend(request):
    user_id = request.session.get("pending_otp_user")
    if not user_id:
        messages.error(request, "No pending verification found. Please sign up first.")
        return redirect("content:signup")
        
    user = get_object_or_404(User, id=user_id)

    resend_key = f"otp:resend:{user.id}"
    try:
        cnt = cache.get(resend_key) or 0
        if cnt >= getattr(settings, "OTP_RESEND_LIMIT", 3):
            messages.error(request, "Too many resend requests. Please try again later.")
            return redirect("content:otp_verify")

        if cache.get(resend_key) is None:
            cache.add(resend_key, 1, timeout=getattr(settings, "OTP_RESEND_WINDOW", 900))
        else:
            cache.incr(resend_key)
    except Exception:
        pass

    code = generate_otp(user)
    sent = send_verification_email(user, code)
    if sent:
        messages.success(request, "A verification code has been sent to your email.")
    else:
        messages.info(request, f"OTP for verification: {code}")
    return redirect("content:otp_verify")


def _firebase_web_config():
    return {
        "apiKey": getattr(settings, "FIREBASE_WEB_API_KEY", ""),
        "authDomain": getattr(settings, "FIREBASE_AUTH_DOMAIN", ""),
        "projectId": getattr(settings, "FIREBASE_PROJECT_ID", ""),
        "appId": getattr(settings, "FIREBASE_APP_ID", ""),
    }


@require_POST
def firebase_phone_auth(request):
    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON payload."}, status=400)

    id_token = (payload.get("id_token") or "").strip()
    if not id_token:
        return JsonResponse({"ok": False, "error": "id_token is required."}, status=400)

    try:
        decoded_token = verify_id_token(id_token)
    except Exception as exc:
        return JsonResponse({"ok": False, "error": "Invalid Firebase token.", "detail": str(exc)}, status=400)

    phone_number = (decoded_token.get("phone_number") or "").strip()
    if not phone_number:
        return JsonResponse({"ok": False, "error": "Phone number not found in Firebase token."}, status=400)

    full_name = (payload.get("full_name") or decoded_token.get("name") or "").strip()
    password = (payload.get("password") or "").strip()

    user = User.objects.filter(phone_number=phone_number).first()
    created = False

    if user is None:
        user = User.objects.create_user(
            phone_number=phone_number,
            password=password or None,
            full_name=full_name,
            role=UserRole.STUDENT,
            is_active=True,
            is_verified=True,
        )
        if not password:
            user.set_unusable_password()
            user.save(update_fields=["password"])
        created = True
    else:
        if password and user.has_usable_password() and not user.check_password(password):
            return JsonResponse({"ok": False, "error": "Invalid password for this phone number."}, status=400)
        if password and not user.has_usable_password():
            user.set_password(password)
        if full_name and not user.full_name:
            user.full_name = full_name
        if not user.is_active:
            user.is_active = True
        if not user.is_verified:
            user.is_verified = True
        update_fields = ["full_name", "is_active", "is_verified"]
        if password:
            update_fields.append("password")
        user.save(update_fields=update_fields)

    profile = ensure_profile(user)
    login(request, user)
    return JsonResponse(
        {
            "ok": True,
            "is_new_user": created,
            "user": {
                "id": user.id,
                "email": user.email,
                "phone_number": user.phone_number,
                "full_name": user.full_name,
                "role": user.role,
            },
            "profile_role": profile.role,
        }
    )


@login_required
@require_POST
def firebase_link_phone(request):
    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON payload."}, status=400)

    id_token = (payload.get("id_token") or "").strip()
    if not id_token:
        return JsonResponse({"ok": False, "error": "id_token is required."}, status=400)

    try:
        decoded_token = verify_id_token(id_token)
    except Exception as exc:
        return JsonResponse({"ok": False, "error": "Invalid Firebase token.", "detail": str(exc)}, status=400)

    phone_number = (decoded_token.get("phone_number") or "").strip()
    if not phone_number:
        return JsonResponse({"ok": False, "error": "Phone number not found in Firebase token."}, status=400)

    if User.objects.filter(phone_number=phone_number).exclude(pk=request.user.pk).exists():
        return JsonResponse({"ok": False, "error": "This phone number is already linked to another account."}, status=400)

    request.user.phone_number = phone_number
    request.user.is_active = True
    request.user.is_verified = True
    request.user.save(update_fields=["phone_number", "is_active", "is_verified"])

    return JsonResponse({"ok": True, "phone_number": phone_number})


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
    return {
        "ok": True,
        "id": resource.id,
        "lesson_id": resource.lesson_id,
        "module_id": resource.lesson.module_id,
        "title": resource.title,
        "content_type": content_type,
        "text_content": resource.text_content or "",
        "file_url": file_url,
        "image_url": file_url if resource.content_type == LessonResourceType.IMAGE else "",
        "audio_url": file_url if resource.content_type == LessonResourceType.AUDIO else "",
        "video_url": file_url if resource.content_type == LessonResourceType.VIDEO and not youtube_embed_url else "",
        "youtube_url": resource.external_url if resource.get_youtube_embed_url() else "",
        "youtube_embed_url": youtube_embed_url,
        "external_url": resource.external_url or "",
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


@require_POST
def firebase_google_auth(request):
    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON payload."}, status=400)

    id_token = (payload.get("id_token") or "").strip()
    if not id_token:
        return JsonResponse({"ok": False, "error": "id_token is required."}, status=400)

    try:
        decoded_token = verify_id_token(id_token)
    except Exception as exc:
        return JsonResponse({"ok": False, "error": "Invalid Firebase token.", "detail": str(exc)}, status=400)

    email = (decoded_token.get("email") or "").strip()
    if not email:
        return JsonResponse({"ok": False, "error": "Email not found in Firebase token."}, status=400)

    full_name = (payload.get("full_name") or decoded_token.get("name") or "").strip()

    user = User.objects.filter(email=email).first()
    created = False

    if user is None:
        user = User.objects.create_user(
            email=email,
            phone_number="",
            full_name=full_name,
            role=UserRole.STUDENT,
            is_active=True,
            is_verified=True,
        )
        user.set_unusable_password()
        user.save()
        created = True
    else:
        if not user.is_active:
            user.is_active = True
        if not user.is_verified:
            user.is_verified = True
        user.save()

    StudentProfile.objects.get_or_create(user=user)

    login(request, user)
    return JsonResponse({"ok": True, "created": created, "message": "Successfully logged in via Google."})


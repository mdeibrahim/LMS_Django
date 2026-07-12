import json
import random
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods

from content.forms import EmailLoginForm, StudentSignupForm, OTPForm
from content.models import UserRole
from content.services.profiles import ensure_profile
from content.firebase import verify_id_token
from content.utils import send_verification_email

from apps.authentication.models import EmailOTP, User
from apps.student_dashboard.models import StudentProfile


def _role_login(request, template_name):
    if request.user.is_authenticated:
        return redirect("content:home")

    form = EmailLoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email_or_phone = form.cleaned_data["email"].strip()
        password = form.cleaned_data["password"]
        
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


def student_login(request):
    return _role_login(request, template_name="registration/student_login.html")


def generate_otp(user):
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
        return redirect("authentication:otp_verify")

    return render(
        request,
        template_name,
        {
            "form": form,
            "firebase_config": _firebase_web_config(),
        },
    )


def student_signup(request):
    return _role_signup(request, template_name="registration/student_signup.html")


def otp_verify(request):
    form = OTPForm(request.POST or None)
    user_id = request.session.get("pending_otp_user")
    if not user_id:
        messages.error(request, "No pending verification found. Please sign up first.")
        return redirect("authentication:signup")

    user = get_object_or_404(User, id=user_id)
    profile = ensure_profile(user)
    lock_key = f"otp:lockout:{user.id}"
    if cache.get(lock_key):
        messages.error(request, "Too many failed attempts. Please try again later.")
        return redirect("authentication:signup")

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
            return redirect("authentication:signup")

        form.add_error("code", "Invalid or expired code.")

    return render(request, "registration/otp_verify.html", {"form": form, "email": user.email})


def otp_resend(request):
    user_id = request.session.get("pending_otp_user")
    if not user_id:
        messages.error(request, "No pending verification found. Please sign up first.")
        return redirect("authentication:signup")
        
    user = get_object_or_404(User, id=user_id)

    resend_key = f"otp:resend:{user.id}"
    try:
        cnt = cache.get(resend_key) or 0
        if cnt >= getattr(settings, "OTP_RESEND_LIMIT", 3):
            messages.error(request, "Too many resend requests. Please try again later.")
            return redirect("authentication:otp_verify")

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
    return redirect("authentication:otp_verify")


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

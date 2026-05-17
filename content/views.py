import uuid
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Avg, Count, OuterRef, Q, Subquery, Prefetch
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
from django.http import JsonResponse
from .utils import send_verification_email
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_http_methods
from .models import (
    Category,
    CourseCertificate,
    CourseContent,
    Course,
    Module,
    ModuleAccordionSection,
    ModulePurchase,
    UserProfile,
    UserRole,
    PaymentInstruction,
)
from .forms import (
    EmailLoginForm,
    ProfileUpdateForm,
    StudentSignupForm,
)


User = get_user_model()


VISIBLE_COURSE_CONTENTS = CourseContent.objects.filter(is_inline_reference=False).order_by('order', 'created_at')


# ─────────────────────────────────────────────────────────
#   PAGE VIEWS
# ─────────────────────────────────────────────────────────

def home(request):
    """Home page — show courses."""
    courses = Course.objects.select_related('subcategory__category').prefetch_related('modules').all()
    owned_course_ids = _get_owned_course_ids(request.user)
    categories = Category.objects.filter(subcategories__courses__isnull=False).distinct().order_by('name')
    return render(request, 'content/home.html', {
        'courses': courses,
        'owned_course_ids': owned_course_ids,
        'categories': categories,
    })



def course_detail(request, course_slug):
    """Course detail page with module list."""
    course = get_object_or_404(Course, slug=course_slug)
    modules_qs = course.modules.prefetch_related(
        Prefetch('course_contents', queryset=VISIBLE_COURSE_CONTENTS)
    ).all()
    modules = list(modules_qs)
    # attach first_content attribute to each module (useful in templates)
    for m in modules:
        contents = list(m.course_contents.all())
        m.first_content = contents[0] if contents else None
        m.visible_content_count = len(contents)
        # attach quiz count to avoid template relying on related manager in ambiguous contexts
        try:
            m.quiz_count = m.course_quizzes.count()
        except Exception:
            m.quiz_count = 0

    has_access = _has_module_access(request.user, course)
    related_courses = Course.objects.exclude(id=course.id).prefetch_related('modules')[:3]
    owned_course_ids = _get_owned_course_ids(request.user)
    # find first available content to use for "Start" CTA
    first_content = None
    for m in modules:
        if getattr(m, 'first_content', None):
            first_content = m.first_content
            break
    return render(request, 'content/course_detail.html', {
        'course': course,
        'modules': modules,
        'has_access': has_access,
        'related_courses': related_courses,
        'owned_course_ids': owned_course_ids,
        'first_content': first_content,
    })


def module_detail(request, course_slug, module_slug):
    course = get_object_or_404(Course, slug=course_slug)
    module = get_object_or_404(
        Module.objects.prefetch_related(
            Prefetch('course_contents', queryset=VISIBLE_COURSE_CONTENTS),
            Prefetch('accordion_sections', queryset=ModuleAccordionSection.objects.order_by('order', 'created_at')),
        ),
        course=course,
        slug=module_slug,
    )
    first_content = module.course_contents.order_by('order', 'created_at').first()
    if first_content:
        return redirect('content:play_video', course.slug, module.slug, first_content.id)
    return redirect('content:course_detail', course.slug)


@staff_member_required
def module_editor(request, course_slug, module_slug):
    course = get_object_or_404(Course, slug=course_slug)
    module = get_object_or_404(
        Module.objects.prefetch_related(
            Prefetch('accordion_sections', queryset=ModuleAccordionSection.objects.order_by('order', 'created_at')),
        ),
        course=course,
        slug=module_slug,
    )
    interactive_contents = list(module.course_contents.filter(is_inline_reference=False).order_by('order', 'created_at').all())
    accordion_sections = list(module.accordion_sections.all())
    first_content = module.course_contents.filter(is_inline_reference=False).order_by('order', 'created_at').first()
    return render(request, 'content/subject_editor.html', {
        'course': course,
        'module': module,
        'interactive_contents': interactive_contents,
        'accordion_sections': accordion_sections,
        'interactive_contents_payload': [_serialize_ic(ic) for ic in interactive_contents],
        'accordion_sections_payload': [_serialize_accordion(section) for section in accordion_sections],
        'preview_url': (
            reverse('content:play_video', args=[course.slug, module.slug, first_content.id])
            if first_content else reverse('content:course_detail', args=[course.slug])
        ),
    })


def play_video(request, course_slug, module_slug, video_id):
    """Play a video inside a module with a right-side video list"""
    course = get_object_or_404(Course, slug=course_slug)
    module = get_object_or_404(Module, course=course, slug=module_slug)
    video = get_object_or_404(CourseContent, id=video_id, module=module)

    has_access = _has_module_access(request.user, course)
    videos = module.course_contents.filter(is_inline_reference=False).order_by('order', 'created_at').all()
    interactive_contents = list(videos)
    accordion_sections = list(module.accordion_sections.order_by('order', 'created_at'))

    # derive embed info for youtube/mp4
    def _get_embed(url):
        from urllib.parse import urlparse, parse_qs
        import re
        if not url:
            return {'type': 'link', 'url': ''}
        host = urlparse(url).netloc.lower()
        if 'youtube.com' in host or 'youtu.be' in host:
            # extract video id
            video_id = None
            try:
                parsed = urlparse(url)
                host2 = (parsed.netloc or '').lower().replace('www.', '')
                if host2 in ('youtube.com', 'm.youtube.com') and parsed.path == '/watch':
                    video_id = (parse_qs(parsed.query).get('v') or [None])[0]
                elif 'shorts' in parsed.path:
                    video_id = parsed.path.split('/shorts/', 1)[1].split('/', 1)[0]
                elif parsed.path.startswith('/embed/'):
                    video_id = parsed.path.split('/embed/', 1)[1].split('/', 1)[0]
                elif host2 == 'youtu.be':
                    video_id = parsed.path.lstrip('/').split('/', 1)[0]
            except Exception:
                video_id = None
            if not video_id:
                m = re.search(r'(?:v=|youtu\.be/|/embed/|/shorts/|/live/)([a-zA-Z0-9_-]{11})', url)
                if m:
                    video_id = m.group(1)
            if video_id:
                return {
                    'type': 'youtube',
                    'video_id': video_id,
                    'embed_url': f'https://www.youtube.com/embed/{video_id}'
                }
            return {'type': 'link', 'url': url}

        if url.lower().endswith('.mp4'):
            return {'type': 'mp4', 'url': url}

        return {'type': 'link', 'url': url}

    # prefer explicit youtube_url field, then URL field, then uploaded FileField
    file_url = ''
    try:
        if getattr(video, 'video') and hasattr(video.video, 'url'):
            file_url = video.video.url or ''
    except Exception:
        file_url = ''

    # If a youtube/video URL (or uploaded mp4) exists, derive embed from it
    if video.youtube_url or video.video_url or file_url:
        embed = _get_embed(video.youtube_url or video.video_url or file_url)
    else:
        # fallback to image if present
        img_url = ''
        try:
            if getattr(video, 'image') and hasattr(video.image, 'url'):
                img_url = video.image.url or ''
        except Exception:
            img_url = ''

        if img_url:
            embed = {'type': 'image', 'url': img_url}
        else:
            embed = {'type': 'link', 'url': ''}

    return render(request, 'content/video_player.html', {
        'course': course,
        'module': module,
        'video': video,
        'videos': videos,
        'interactive_contents': interactive_contents,
        'accordion_sections': accordion_sections,
        'has_access': has_access,
        'embed': embed,
    })

@login_required
def my_modules(request):
    purchases = ModulePurchase.objects.filter(
        user=request.user,
        is_purchased=True,
    ).select_related('course')
    return render(request, 'content/my_modules.html', {'purchases': purchases})


@login_required
def profile_page(request):
    profile, _ = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={'role': UserRole.STUDENT},
    )
    form = ProfileUpdateForm(request.POST or None, request.FILES or None, user=request.user, profile=profile)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('content:profile')
    return render(request, 'content/profile.html', {'form': form, 'profile': profile})


@login_required
def student_dashboard(request):
    purchases = ModulePurchase.objects.filter(
        user=request.user,
        is_purchased=True,
    ).select_related('course')
    purchased_course_ids = set(purchases.values_list('course_id', flat=True))
    available_courses = Course.objects.exclude(id__in=purchased_course_ids)

    purchased_cards = []
    for purchase in purchases:
        progress = 0
        purchased_cards.append({
            'purchase': purchase,
            'progress': progress,
            'is_completed': False,
            'has_access': _has_module_access(request.user, purchase.course),
            'certificate': CourseCertificate.objects.filter(user=request.user, course=purchase.course).first(),
        })

    certificates = CourseCertificate.objects.filter(user=request.user).select_related('course')

    return render(request, 'content/student_dashboard.html', {
        'purchased_cards': purchased_cards,
        'available_courses': available_courses[:12],
        'certificates': certificates,
    })

@login_required
@require_POST
def claim_certificate(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    if not _has_module_access(request.user, course):
        messages.error(request, 'You do not have access to this course.')
        return redirect('content:student_dashboard')

    if not course.modules.exists():
        messages.error(request, 'No modules are available for this course yet.')
        return redirect('content:student_dashboard')

    certificate, created = CourseCertificate.objects.get_or_create(
        user=request.user,
        course=course,
        defaults={'certificate_code': _generate_certificate_code()},
    )
    if created:
        messages.success(request, f'Certificate issued successfully: {certificate.certificate_code}')
    else:
        messages.info(request, f'Certificate already issued: {certificate.certificate_code}')
    return redirect('content:student_dashboard')


def login_selector(request):
    if request.user.is_authenticated:
        return redirect('content:home')
    return render(request, 'registration/login.html')


def signup_selector(request):
    if request.user.is_authenticated:
        return redirect('content:home')
    return render(request, 'registration/signup.html')


def student_login(request):
    return _role_login(request, template_name='registration/student_login.html')


def student_signup(request):
    return _role_signup(request, template_name='registration/student_signup.html')


def signup(request):
    return signup_selector(request)


@login_required
@require_POST
def buy_module(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug)

    purchase, created = ModulePurchase.objects.get_or_create(user=request.user, course=course)
    # mark as purchased when user goes through the buy flow
    if not purchase.is_purchased:
        purchase.is_purchased = True
        purchase.save()

    if course.is_free:
        messages.success(request, f'"{course.name}" is now added to your account (free course).')
    else:
        messages.success(request, f'Success! You now have access to "{course.name}".')

    next_url = request.POST.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('content:course_detail', course_slug=course.slug)


@login_required
def start_purchase(request, course_slug):
    """Initialize purchase when user clicks 'এখনই কিনুন'.

    - If course is free (is_free or price == 0): create ModulePurchase and mark is_purchased=True then redirect to course details.
    - If course is paid (>0): create ModulePurchase relation (is_purchased=False) if not exists, then redirect to `course_purchase` page.
    """
    course = get_object_or_404(Course, slug=course_slug)

    purchase, created = ModulePurchase.objects.get_or_create(user=request.user, course=course)

    # Free course: immediately mark as purchased
    is_free = getattr(course, 'is_free', False) or (getattr(course, 'price', 0) == 0)
    if is_free:
        if not purchase.is_purchased:
            purchase.is_purchased = True
            purchase.save()
        messages.success(request, f'"{course.name}" is now added to your account (free course).')
        return redirect('content:course_detail', course_slug=course.slug)

    # Paid course: ensure relation exists but keep is_purchased False, then show purchase page
    if purchase.is_purchased:
        messages.info(request, f'You already have access to "{course.name}".')
        return redirect('content:course_detail', course_slug=course.slug)

    if created:
        purchase.is_purchased = False
        purchase.save()

    return redirect('content:course_purchase', course_slug=course.slug)


@login_required
def course_purchase(request, course_slug):
    """Modern purchase / course detail page showing price and payment options."""
    course = get_object_or_404(Course, slug=course_slug)

    # Render a friendly purchase page. The actual purchase action posts to `buy_module`.
    payment_instructions = PaymentInstruction.objects.order_by('payment_method_name').all()
    return render(request, 'content/course_purchase.html', {
        'course': course,
        'payment_instructions': payment_instructions,
    })


@login_required
@require_POST
def submit_payment_details(request, course_slug):
    """Accepts transaction_id, note and payment_method from student and emails admin."""
    course = get_object_or_404(Course, slug=course_slug)
    transaction_id = (request.POST.get('transaction_id') or '').strip()
    note = (request.POST.get('note') or '').strip()
    # prefer explicit posted payment_method (hidden/select), fallback to older field
    payment_method = (request.POST.get('payment_method') or request.POST.get('payment_method_display') or '').strip()

    if not transaction_id:
        messages.error(request, 'Please provide a transaction ID.')
        return redirect('content:course_purchase', course_slug=course.slug)

    from .utils import send_payment_submission_email

    sent = send_payment_submission_email(
        user=request.user,
        course=course,
        amount=getattr(course, 'price', 0),
        payment_method=payment_method,
        transaction_id=transaction_id,
        note=note,
    )

    if sent:
        messages.success(request, 'Payment details submitted. Admin has been notified.')
    else:
        messages.error(request, 'Could not send notification email. Please contact support.')

    return redirect('content:course_purchase', course_slug=course.slug)

def _get_owned_course_ids(user):
    if not user.is_authenticated:
        return set()
    if user.is_staff or user.is_superuser:
        return set(Course.objects.values_list('id', flat=True))
    return set(
        ModulePurchase.objects.filter(user=user, is_purchased=True).values_list('course_id', flat=True)
    )


def _has_module_access(user, course):
    if course.is_free:
        return True
    if not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return ModulePurchase.objects.filter(
        user=user,
        course=course,
        is_purchased=True,
    ).exists()

def _generate_certificate_code():
    return f"CERT-{uuid.uuid4().hex[:12].upper()}"


def _role_login(request, template_name):
    if request.user.is_authenticated:
        return redirect('content:home')

    form = EmailLoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email'].strip().lower()
        password = form.cleaned_data['password']

        matched_users = User.objects.filter(email__iexact=email)
        if matched_users.count() > 1:
            form.add_error('email', 'Multiple accounts found with this email. Please contact support.')
            return render(request, template_name, {'form': form})

        user_obj = matched_users.first()
        if not user_obj:
            form.add_error('email', 'No account found with this email.')
            return render(request, template_name, {'form': form})

        user = authenticate(request=request, username=user_obj.get_username(), password=password)
        if not user:
            form.add_error('password', 'Invalid email or password.')
            return render(request, template_name, {'form': form})

        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={'role': UserRole.STUDENT},
        )

        if profile.role != UserRole.STUDENT:
            profile.role = UserRole.STUDENT
            profile.teacher_institution = ''
            profile.teacher_subject = ''
            profile.teacher_experience_years = None
            profile.save(update_fields=['role', 'teacher_institution', 'teacher_subject', 'teacher_experience_years'])

        login(request, user)
        messages.success(request, f'Welcome back, {user.username}!')
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url:
            return redirect(next_url)
        return redirect('content:student_dashboard')

    return render(request, template_name, {'form': form})


def _role_signup(request, template_name):
    if request.user.is_authenticated:
        return redirect('content:home')

    form = StudentSignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        form.save_profile(user=user, role=UserRole.STUDENT)

        # Create OTP and redirect to verification
        from django.utils import timezone
        from datetime import timedelta
        from .models import EmailOTP
        import random

        code = f"{random.randint(100000, 999999)}"
        expires = timezone.now() + timedelta(minutes=15)
        EmailOTP.objects.create(user=user, code=code, expires_at=expires)

        # Send verification email (falls back to showing OTP in messages if send fails)
        sent = send_verification_email(user, code)
        if not sent:
            # fallback: surface OTP in messages for debugging or if email send fails
            messages.info(request, f'OTP for verification: {code}')

        request.session['pending_otp_user'] = user.id
        return redirect('content:otp_verify')

    return render(request, template_name, {'form': form})


def otp_verify(request):
    from .forms import OTPForm
    from .models import EmailOTP
    from django.utils import timezone

    user_id = request.session.get('pending_otp_user')
    if not user_id:
        messages.error(request, 'No pending verification found. Please sign up first.')
        return redirect('content:signup')

    user = get_object_or_404(User, id=user_id)

    # Check lockout
    lock_key = f"otp:lockout:{user.id}"
    if cache.get(lock_key):
        messages.error(request, 'Too many failed attempts. Please try again later.')
        return redirect('content:signup')
    form = OTPForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        code = form.cleaned_data['code'].strip()
        otp_qs = EmailOTP.objects.filter(user=user, code=code, is_used=False, expires_at__gte=timezone.now())
        if otp_qs.exists():
            otp = otp_qs.first()
            otp.is_used = True
            otp.save()
            # login user and cleanup
            # reset attempt counter
            attempt_key = f"otp:attempt:{user.id}"
            try:
                cache.delete(attempt_key)
            except Exception:
                pass
            login(request, user)
            request.session.pop('pending_otp_user', None)
            messages.success(request, 'Your account is verified and you are now logged in.')
            profile = UserProfile.objects.get_or_create(user=user)[0]
            if profile.role != UserRole.STUDENT:
                profile.role = UserRole.STUDENT
                profile.teacher_institution = ''
                profile.teacher_subject = ''
                profile.teacher_experience_years = None
                profile.save(update_fields=['role', 'teacher_institution', 'teacher_subject', 'teacher_experience_years'])
            return redirect('content:student_dashboard')
        else:
            # increment attempt counter
            attempt_key = f"otp:attempt:{user.id}"
            try:
                if cache.get(attempt_key) is None:
                    cache.add(attempt_key, 1, timeout=settings.OTP_ATTEMPT_WINDOW)
                else:
                    cache.incr(attempt_key)
            except Exception:
                pass

            # lockout if exceeded
            attempts = cache.get(attempt_key) or 0
            if attempts >= settings.OTP_ATTEMPT_LIMIT:
                lock_key = f"otp:lockout:{user.id}"
                try:
                    cache.set(lock_key, True, timeout=settings.OTP_LOCKOUT_SECONDS)
                except Exception:
                    pass
                messages.error(request, 'Too many failed attempts. Please try again later.')
                return redirect('content:signup')

            form.add_error('code', 'Invalid or expired code.')

    return render(request, 'registration/otp_verify.html', {'form': form, 'email': user.email})


def otp_resend(request):
    from django.utils import timezone
    from datetime import timedelta
    import random
    from .models import EmailOTP

    user_id = request.session.get('pending_otp_user')
    if not user_id:
        messages.error(request, 'No pending verification found.')
        return redirect('content:signup')

    user = get_object_or_404(User, id=user_id)
    code = f"{random.randint(100000, 999999)}"
    expires = timezone.now() + timedelta(minutes=15)
    # rate-limit resends per user
    resend_key = f"otp:resend:{user.id}"
    try:
        cnt = cache.get(resend_key) or 0
        if cnt >= settings.OTP_RESEND_LIMIT:
            messages.error(request, 'Too many resend requests. Please try again later.')
            return redirect('content:otp_verify')

        if cache.get(resend_key) is None:
            cache.add(resend_key, 1, timeout=settings.OTP_RESEND_WINDOW)
        else:
            cache.incr(resend_key)
    except Exception:
        # if cache fails, continue without rate-limiting
        pass

    EmailOTP.objects.create(user=user, code=code, expires_at=expires)
    sent = send_verification_email(user, code)
    if sent:
        messages.success(request, 'A verification code has been sent to your email.')
    else:
        messages.info(request, f'OTP for verification: {code}')
    return redirect('content:otp_verify')


def get_course_content(request, content_id):
    """Return course content payload for modal rendering."""
    content = get_object_or_404(CourseContent, id=content_id)

    if content.module and not _has_module_access(request.user, content.module.course):
        return JsonResponse({'detail': 'Access denied.'}, status=403)

    image_url = content.image.url if content.image else ''
    audio_url = content.audio.url if content.audio else ''
    video_url = ''
    try:
        video_url = content.video.url if content.video else (content.video_url or '')
    except Exception:
        video_url = content.video_url or ''
    youtube_embed_url = content.get_youtube_embed_url() or _youtube_embed_from_url(video_url)

    return JsonResponse({
        'id': content.id,
        'module_id': content.module_id,
        'title': content.title,
        'content_type': content.content_type,
        'is_inline_reference': content.is_inline_reference,
        'text_content': content.text_content or '',
        'image_url': image_url,
        'audio_url': audio_url,
        'video_url': video_url,
        'youtube_url': content.youtube_url or '',
        'youtube_embed_url': youtube_embed_url,
        'created_at': content.created_at.isoformat(),
    })


def get_interactive_content(request, content_id):
    return get_course_content(request, content_id)


def _youtube_embed_from_url(raw_url):
    from urllib.parse import urlparse, parse_qs
    import re

    if not raw_url:
        return ''

    video_id = None
    try:
        parsed = urlparse(raw_url.strip())
        host = (parsed.netloc or '').lower().replace('www.', '')
        if host in ('youtube.com', 'm.youtube.com'):
            if parsed.path == '/watch':
                video_id = (parse_qs(parsed.query).get('v') or [None])[0]
            elif parsed.path.startswith('/shorts/'):
                video_id = parsed.path.split('/shorts/', 1)[1].split('/', 1)[0]
            elif parsed.path.startswith('/live/'):
                video_id = parsed.path.split('/live/', 1)[1].split('/', 1)[0]
            elif parsed.path.startswith('/embed/'):
                video_id = parsed.path.split('/embed/', 1)[1].split('/', 1)[0]
        elif host == 'youtu.be':
            video_id = parsed.path.lstrip('/').split('/', 1)[0]
    except Exception:
        video_id = None

    if not video_id:
        match = re.search(r'(?:v=|youtu\.be/|/embed/|/shorts/|/live/)([a-zA-Z0-9_-]{11})', raw_url)
        if match:
            video_id = match.group(1)

    if video_id and re.fullmatch(r'[a-zA-Z0-9_-]{11}', video_id):
        return f"https://www.youtube.com/embed/{video_id}"
    return ''


def _serialize_ic(ic):
    video_url = ''
    try:
        video_url = ic.video.url if ic.video else (ic.video_url or '')
    except Exception:
        video_url = ic.video_url or ''
    return {
        'id': ic.id,
        'module_id': ic.module_id,
        'title': ic.title,
        'content_type': ic.content_type,
        'is_inline_reference': ic.is_inline_reference,
        'text_content': ic.text_content or '',
        'youtube_url': ic.youtube_url or '',
        'youtube_embed_url': ic.get_youtube_embed_url() or _youtube_embed_from_url(video_url),
        'image_url': ic.image.url if ic.image else '',
        'audio_url': ic.audio.url if ic.audio else '',
        'video_url': video_url,
        'created_at': ic.created_at.isoformat(),
    }


def _serialize_accordion(section):
    return {
        'id': section.id,
        'module_id': section.module_id,
        'title': section.title,
        'content': section.content or '',
        'order': section.order,
        'is_open_by_default': section.is_open_by_default,
        'created_at': section.created_at.isoformat(),
    }


def _parse_api_payload(request):
    if request.content_type and 'multipart' in request.content_type:
        return request.POST, request.FILES, None
    try:
        data = json.loads(request.body or '{}')
        return data, {}, None
    except Exception:
        return None, None, JsonResponse({'ok': False, 'error': 'Invalid body'}, status=400)


@csrf_exempt
@staff_member_required
@require_http_methods(["POST"])
def api_subject_save(request, module_id):
    module = get_object_or_404(Module, id=module_id)
    data, _, error = _parse_api_payload(request)
    if error:
        return error

    module.title = (data.get('title') or module.title).strip() or module.title
    module.body_content = data.get('body_content', module.body_content or '')
    module.save(update_fields=['title', 'body_content', 'updated_at'])

    return JsonResponse({
        'ok': True,
        'module': {
            'id': module.id,
            'title': module.title,
            'body_content': module.body_content,
            'updated_at': module.updated_at.isoformat() if module.updated_at else '',
        }
    })


@csrf_exempt
@staff_member_required
@require_http_methods(["POST"])
def api_ic_create(request, module_id):
    """Create a new InteractiveContent item"""
    module = get_object_or_404(Module, id=module_id)
    # Handle multipart (file uploads) or JSON
    if request.content_type and 'multipart' in request.content_type:
        data = request.POST
        files = request.FILES
    else:
        try:
            data = json.loads(request.body)
        except Exception:
            return JsonResponse({'error': 'Invalid body'}, status=400)
        files = {}

    content_type = data.get('content_type', 'text')
    title = data.get('title', 'Untitled')
    is_inline_reference = str(data.get('is_inline_reference', '')).lower() in ('1', 'true', 'yes', 'on')

    ic = CourseContent(module=module, content_type=content_type, title=title)
    ic.is_inline_reference = is_inline_reference

    if content_type == 'text':
        ic.text_content = data.get('text_content', '')
    elif content_type == 'image' and 'image' in files:
        ic.image = files['image']
    elif content_type == 'audio' and 'audio' in files:
        ic.audio = files['audio']
    elif content_type == 'video':
        if 'video' in files:
            ic.video = files['video']
        ic.video_url = data.get('video_url', '')
    elif content_type == 'youtube':
        ic.youtube_url = data.get('youtube_url', '')
    ic.save()

    return JsonResponse({'ok': True, 'ic': _serialize_ic(ic)}, status=201)


@csrf_exempt
@staff_member_required
@require_http_methods(["POST"])
def api_ic_update(request, ic_id):
    """Update an existing InteractiveContent item"""
    ic = get_object_or_404(CourseContent, id=ic_id)

    if request.content_type and 'multipart' in request.content_type:
        data = request.POST
        files = request.FILES
    else:
        try:
            data = json.loads(request.body)
        except Exception:
            return JsonResponse({'error': 'Invalid body'}, status=400)
        files = {}

    if 'content_type' in data:
        ic.content_type = data['content_type']
    if 'title' in data:
        ic.title = data['title']
    if 'is_inline_reference' in data:
        ic.is_inline_reference = str(data['is_inline_reference']).lower() in ('1', 'true', 'yes', 'on')
    if 'text_content' in data:
        ic.text_content = data['text_content']
    if 'youtube_url' in data:
        ic.youtube_url = data['youtube_url']
    if 'video_url' in data:
        ic.video_url = data['video_url']
    if 'image' in files:
        ic.image = files['image']
    if 'audio' in files:
        ic.audio = files['audio']
    if 'video' in files:
        ic.video = files['video']
    ic.save()

    return JsonResponse({'ok': True, 'ic': _serialize_ic(ic)})


@csrf_exempt
@staff_member_required
@require_http_methods(["DELETE", "POST"])
def api_ic_delete(request, ic_id):
    """Delete an InteractiveContent item"""
    ic = get_object_or_404(CourseContent, id=ic_id)
    ic.delete()
    return JsonResponse({'ok': True})


@csrf_exempt
@staff_member_required
@require_http_methods(["POST"])
def api_accordion_create(request, module_id):
    module = get_object_or_404(Module, id=module_id)
    data, _, error = _parse_api_payload(request)
    if error:
        return error

    section = ModuleAccordionSection.objects.create(
        module=module,
        title=(data.get('title') or 'Untitled Section').strip(),
        content=data.get('content', ''),
        order=int(data.get('order') or module.accordion_sections.count() + 1),
        is_open_by_default=bool(data.get('is_open_by_default')),
    )
    return JsonResponse({'ok': True, 'section': _serialize_accordion(section)}, status=201)


@csrf_exempt
@staff_member_required
@require_http_methods(["POST"])
def api_accordion_update(request, section_id):
    section = get_object_or_404(ModuleAccordionSection, id=section_id)
    data, _, error = _parse_api_payload(request)
    if error:
        return error

    if 'title' in data:
        section.title = (data.get('title') or section.title).strip() or section.title
    if 'content' in data:
        section.content = data.get('content', '')
    if 'order' in data and str(data.get('order')).strip():
        section.order = int(data.get('order'))
    if 'is_open_by_default' in data:
        section.is_open_by_default = bool(data.get('is_open_by_default'))
    section.save()
    return JsonResponse({'ok': True, 'section': _serialize_accordion(section)})


@csrf_exempt
@staff_member_required
@require_http_methods(["DELETE", "POST"])
def api_accordion_delete(request, section_id):
    section = get_object_or_404(ModuleAccordionSection, id=section_id)
    section.delete()
    return JsonResponse({'ok': True})

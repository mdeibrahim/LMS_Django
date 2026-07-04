from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.is_active = False

        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", "teacher")

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class UserRole(models.TextChoices):
    TEACHER = "teacher", "Teacher"
    STUDENT = "student", "Student"
    

class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=160, blank=True, default="")
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.STUDENT)
    phone_number = models.CharField(max_length=20, blank=True, default="")
    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    EMAIL_FIELD = "email"

    class Meta:
        ordering = ["email"]

    def __str__(self):
        return self.email

    def get_full_name(self):
        return (self.full_name or "").strip() or self.email

    def get_short_name(self):
        return (self.full_name or "").strip() or self.email

    @property
    def profile(self):
        profile = None
        if self.role == UserRole.TEACHER:
            profile = getattr(self, "teacher_profile", None)
        elif self.role == UserRole.STUDENT:
            profile = getattr(self, "student_profile", None)

        if profile is None:
            profile = getattr(self, "legacy_profile", None)
        return profile


class EmailOTP(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="email_otps")
    code = models.CharField(max_length=6)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_used", "expires_at"]),
        ]

    def __str__(self):
        return f"OTP for {self.user.email} - {self.code}"
    

import uuid
class PasswordResetSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)


class Category(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True, allow_unicode=True)
    description = models.TextField(default="", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def ensure_default_subcategory(self):
        return Subcategory.objects.get_or_create(
            category=self,
            slug="all",
            defaults={
                "name": "all",
                "description": "",
            },
        )[0]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name, allow_unicode=True) or "category"
            slug = base_slug
            counter = 2
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)
        self.ensure_default_subcategory()


class Subcategory(models.Model):
    category = models.ForeignKey(
        "Category",
        on_delete=models.CASCADE,
        related_name="subcategories"
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True, allow_unicode=True)
    description = models.TextField(default="", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("category", "name")

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name, allow_unicode=True) or "subcategory"
            slug = base_slug
            counter = 2
            while Subcategory.objects.filter(category=self.category, slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.category.name} -> {self.name}"


class Course(models.Model):
    subcategory = models.ForeignKey("Subcategory", on_delete=models.CASCADE, related_name="courses")
    teacher = models.ForeignKey(
        "teacher_dashboard.TeacherProfile",
        on_delete=models.CASCADE,
        related_name="teacher_courses",
        limit_choices_to={"user__role": UserRole.TEACHER},
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True, allow_unicode=True)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to="course_covers/", blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    enrollment_count = models.PositiveIntegerField(default=0, blank=True, null=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name, allow_unicode=True) or "course"
            slug = base_slug
            counter = 2
            while Course.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def is_free(self):
        return (self.price or 0) == 0


class Module(models.Model):
    course = models.ForeignKey("Course", on_delete=models.CASCADE, related_name="modules")
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True, allow_unicode=True)
    body_content = models.TextField(
        blank=True,
        default="",
        help_text=(
            "Legacy module body. New content should live on Lesson.body_content. "
            "Highlight links still work with lesson resource ids."
        ),
    )
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        verbose_name = "Module"
        verbose_name_plural = "Modules"
        ordering = ["order", "title"]
        unique_together = [("course", "slug")]
        indexes = [
            models.Index(fields=["course", "order"]),
        ]

    def __str__(self):
        return f"{self.course.name} -> {self.title}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title, allow_unicode=True) or "module"
            slug = base_slug
            counter = 2
            while Module.objects.filter(course=self.course, slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        if not self.pk and self.order == 0:
            max_order = Module.objects.filter(course=self.course).aggregate(models.Max('order'))['order__max']
            self.order = (max_order or 0) + 1
        super().save(*args, **kwargs)

    @property
    def primary_lesson(self):
        return self.lessons.order_by("order", "created_at").first()


class Lesson(models.Model):
    module = models.ForeignKey("Module", on_delete=models.CASCADE, related_name="lessons")
    title = models.CharField(max_length=255)
    slug = models.SlugField(blank=True, allow_unicode=True)
    description = models.TextField(blank=True, default="")
    body_content = models.TextField(
        blank=True,
        default="",
        help_text=(
            "Rich text lesson body. Use "
            "<span class='highlight-link' data-content-id='ID'>text</span> "
            "to link lesson resources."
        ),
    )
    order = models.PositiveIntegerField(default=0)
    is_preview = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "created_at"]
        constraints = [
            models.UniqueConstraint(fields=["module", "slug"], name="uniq_lesson_slug_per_module"),
        ]
        indexes = [
            models.Index(fields=["module", "order"]),
            models.Index(fields=["module", "is_published", "order"]),
        ]

    def __str__(self):
        return f"{self.module.title} -> {self.title}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title, allow_unicode=True) or "lesson"
            slug = base_slug
            counter = 2
            while Lesson.objects.filter(module=self.module, slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        if not self.pk and self.order == 0:
            max_order = Lesson.objects.filter(module=self.module).aggregate(models.Max('order'))['order__max']
            self.order = (max_order or 0) + 1
        super().save(*args, **kwargs)

    @property
    def duration(self):
        secs = int(self.duration_seconds or 0)
        if secs < 60:
            return f"0:{secs:02d}"
        minutes, seconds = divmod(secs, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    @property
    def primary_resource(self):
        return self.resources.order_by("order", "created_at").first()


# class ModuleAccordionSection(models.Model):
#     module = models.ForeignKey("Module", on_delete=models.CASCADE, related_name="accordion_sections")
#     title = models.CharField(max_length=255)
#     content = models.TextField(blank=True)
#     order = models.PositiveIntegerField(default=0)
#     is_open_by_default = models.BooleanField(default=False)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         ordering = ["order", "created_at"]

#     def save(self, *args, **kwargs):
#         if not self.pk and self.order == 0:
#             max_order = ModuleAccordionSection.objects.filter(module=self.module).aggregate(models.Max('order'))['order__max']
#             self.order = (max_order or 0) + 1
#         super().save(*args, **kwargs)

#     def __str__(self):
#         return f"{self.module.title} - {self.title}"


PAYMENT_METHOD_CHOICES = [
    ("bkash", "Bkash"),
    ("nagad", "Nagad"),
    ("rocket", "Rocket"),
    ("bank_transfer", "Bank Transfer"),
]


class EnrollmentStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    REVOKED = "revoked", "Revoked"


class PaymentSubmissionStatus(models.TextChoices):
    PENDING = "pending", "Pending review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class CourseEnrollment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="course_enrollments")
    course = models.ForeignKey("Course", on_delete=models.CASCADE, related_name="enrollments")
    status = models.CharField(max_length=20, choices=EnrollmentStatus.choices, default=EnrollmentStatus.ACTIVE)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="granted_course_enrollments",
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-granted_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "course"], name="uniq_enrollment_per_user_course"),
        ]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["course", "status"]),
        ]

    def __str__(self):
        return f"{self.user} enrolled in {self.course.name}"


class PaymentSubmission(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payment_submissions")
    course = models.ForeignKey("Course", on_delete=models.CASCADE, related_name="payment_submissions")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default="other")
    transaction_id = models.CharField(max_length=255)
    note = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=PaymentSubmissionStatus.choices, default=PaymentSubmissionStatus.PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="reviewed_payment_submissions",
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True, default="")
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-submitted_at"]
        indexes = [
            models.Index(fields=["course", "status", "submitted_at"]),
            models.Index(fields=["user", "status", "submitted_at"]),
            models.Index(fields=["transaction_id"]),
        ]

    def __str__(self):
        return f"{self.user} payment for {self.course.name} ({self.status})"


class ModulePurchase(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="module_purchases")
    course = models.ForeignKey("Course", on_delete=models.CASCADE, related_name="legacy_purchases")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default="other", blank=True, null=True)
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    is_purchased = models.BooleanField(default=False)
    purchased_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-purchased_at"]
        unique_together = [("user", "course")]
        indexes = [
            models.Index(fields=["user", "is_purchased"]),
        ]

    def __str__(self):
        return f"{self.user} purchased {self.course.name}"


class LessonResourceType(models.TextChoices):
    TEXT = "text", "Text / Rich HTML"
    VIDEO = "video", "Video"
    PDF = "pdf", "PDF"
    QUIZ = "quiz", "Quiz"
    AUDIO = "audio", "Audio"
    ATTACHMENT = "attachment", "Attachment"
    EXTERNAL_LINK = "external_link", "External Link"
    EMBED = "embed", "Embedded Content"
    IMAGE = "image", "Image"


class LessonResource(models.Model):
    lesson = models.ForeignKey("Lesson", on_delete=models.CASCADE, related_name="resources")
    title = models.CharField(max_length=255,null=True, blank=True)
    slug = models.SlugField(blank=True, allow_unicode=True)
    content_type = models.CharField(max_length=30, choices=LessonResourceType.choices, default=LessonResourceType.TEXT)
    order = models.PositiveIntegerField(default=0)
    is_preview = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    text_content = models.TextField(blank=True, default="")
    file = models.FileField(upload_to="lesson_resources/", blank=True, null=True)
    external_url = models.URLField(blank=True, default="")
    embed_url = models.URLField(blank=True, default="")
    duration_seconds = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "created_at"]
        constraints = [
            models.UniqueConstraint(fields=["lesson", "slug"], name="uniq_resource_slug_per_lesson"),
        ]
        indexes = [
            models.Index(fields=["lesson", "order"]),
            models.Index(fields=["lesson", "content_type", "order"]),
            models.Index(fields=["lesson", "is_published", "order"]),
        ]

    def __str__(self):
        return f"{self.lesson.title} - {self.title}"

    @property
    def module(self):
        return self.lesson.module

    @property
    def course(self):
        return self.lesson.module.course

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title, allow_unicode=True) or "resource"
            slug = base_slug
            counter = 2
            while LessonResource.objects.filter(lesson=self.lesson, slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        if not self.pk and self.order == 0:
            max_order = LessonResource.objects.filter(lesson=self.lesson).aggregate(models.Max('order'))['order__max']
            self.order = (max_order or 0) + 1
        super().save(*args, **kwargs)

    @property
    def duration(self):
        secs = int(self.duration_seconds or 0)
        if secs < 60:
            return f"0:{secs:02d}"
        minutes, seconds = divmod(secs, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    @property
    def youtube_url(self):
        if self.content_type != LessonResourceType.VIDEO:
            return ""
        return self.embed_url or self.external_url

    def get_youtube_embed_url(self):
        from urllib.parse import parse_qs, urlparse
        import re

        raw_url = (self.embed_url or self.external_url or "").strip()
        if not raw_url:
            return ""

        video_id = None

        try:
            parsed = urlparse(raw_url)
            host = (parsed.netloc or "").lower().replace("www.", "")

            if host in ("youtube.com", "m.youtube.com"):
                if parsed.path == "/watch":
                    video_id = (parse_qs(parsed.query).get("v") or [None])[0]
                elif parsed.path.startswith("/shorts/"):
                    video_id = parsed.path.split("/shorts/", 1)[1].split("/", 1)[0]
                elif parsed.path.startswith("/live/"):
                    video_id = parsed.path.split("/live/", 1)[1].split("/", 1)[0]
                elif parsed.path.startswith("/embed/"):
                    video_id = parsed.path.split("/embed/", 1)[1].split("/", 1)[0]
            elif host == "youtu.be":
                video_id = parsed.path.lstrip("/").split("/", 1)[0]
        except Exception:
            video_id = None

        if not video_id:
            match = re.search(r"(?:v=|youtu\.be/|/embed/|/shorts/|/live/)([a-zA-Z0-9_-]{11})", raw_url)
            if match:
                video_id = match.group(1)

        if video_id and re.fullmatch(r"[a-zA-Z0-9_-]{11}", video_id):
            return f"https://www.youtube.com/embed/{video_id}"
        return ""


class CourseQuiz(models.Model):
    module = models.ForeignKey("Module", on_delete=models.CASCADE, related_name="course_quizzes", blank=True, null=True)
    lesson = models.ForeignKey("Lesson", on_delete=models.SET_NULL, related_name="quizzes", blank=True, null=True)
    title = models.CharField(max_length=255)
    pass_score = models.PositiveSmallIntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["lesson", "is_active"]),
            models.Index(fields=["module", "is_active"]),
        ]

    def __str__(self):
        source = None
        if self.lesson_id:
            source = self.lesson.title
        elif self.module_id:
            source = self.module.title
        return f"{source or 'Quiz'} - {self.title}"


class CourseQuizQuestion(models.Model):
    quiz = models.ForeignKey(CourseQuiz, on_delete=models.CASCADE, related_name="questions")
    question = models.TextField()
    option_a = models.CharField(max_length=255)
    option_b = models.CharField(max_length=255)
    option_c = models.CharField(max_length=255)
    option_d = models.CharField(max_length=255)
    correct_option = models.CharField(max_length=1, choices=[("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")])
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def save(self, *args, **kwargs):
        if not self.pk and self.order == 0:
            max_order = CourseQuizQuestion.objects.filter(quiz=self.quiz).aggregate(models.Max('order'))['order__max']
            self.order = (max_order or 0) + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quiz.title} Q{self.id}"

    def get_options(self):
        return [
            ("A", self.option_a),
            ("B", self.option_b),
            ("C", self.option_c),
            ("D", self.option_d),
        ]


class QuizAttempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quiz_attempts")
    quiz = models.ForeignKey(CourseQuiz, on_delete=models.CASCADE, related_name="attempts")
    score = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at"]
        indexes = [
            models.Index(fields=["user", "submitted_at"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.quiz.title} ({self.score}%)"


class CourseCertificate(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="course_certificates")
    course = models.ForeignKey("Course", on_delete=models.CASCADE, related_name="certificates")
    certificate_code = models.CharField(max_length=40, unique=True)
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_at"]
        unique_together = [("user", "course")]

    def __str__(self):
        return f"{self.user.email} - {self.course.name} certificate"


class PaymentInstruction(models.Model):
    payment_method_name = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default="other", blank=True, null=True)
    details = models.TextField(blank=True, default="")
    image = models.ImageField(upload_to="payment_instructions/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["payment_method_name", "-created_at"]

    def __str__(self):
        return self.get_payment_method_name_display() if self.payment_method_name else "Payment instruction"

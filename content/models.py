from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify


User = get_user_model()


class UserRole(models.TextChoices):
    TEACHER = "teacher", "Teacher"
    STUDENT = "student", "Student"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.STUDENT)
    profile_picture = models.ImageField(upload_to="profile_pictures/", blank=True, null=True)
    full_name = models.CharField(max_length=160, blank=True, default="")
    phone_number = models.CharField(max_length=20, blank=True, default="")
    student_institution = models.CharField(max_length=180, blank=True, default="")
    student_level = models.CharField(max_length=80, blank=True, default="")
    teacher_institution = models.CharField(max_length=180, blank=True, default="")
    teacher_subject = models.CharField(max_length=120, blank=True, default="")
    teacher_experience_years = models.PositiveSmallIntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__username"]

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class EmailOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="email_otps")
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


class StudentDeviceSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="student_device_sessions")
    jti = models.CharField(max_length=64, unique=True)
    user_agent = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "expires_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} device session ({self.jti})"


class Category(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(default="", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Subcategory(models.Model):
    category = models.ForeignKey("Category", on_delete=models.CASCADE, related_name="subcategories")
    name = models.CharField(max_length=255)
    slug = models.SlugField()
    description = models.TextField(default="", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        unique_together = [("category", "slug")]

    def __str__(self):
        return f"{self.category.name} -> {self.name}"


class Course(models.Model):
    subcategory = models.ForeignKey("Subcategory", on_delete=models.CASCADE, related_name="courses")
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def is_free(self):
        return (self.price or 0) == 0


class Module(models.Model):
    course = models.ForeignKey("Course", on_delete=models.CASCADE, related_name="modules")
    title = models.CharField(max_length=255)
    slug = models.SlugField()
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

    @property
    def primary_lesson(self):
        return self.lessons.order_by("order", "created_at").first()


class Lesson(models.Model):
    module = models.ForeignKey("Module", on_delete=models.CASCADE, related_name="lessons")
    title = models.CharField(max_length=255)
    slug = models.SlugField()
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
    duration_seconds = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    thumbnail = models.ImageField(upload_to="lesson_thumbnails/", blank=True, null=True)
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
            base_slug = slugify(self.title) or "lesson"
            slug = base_slug
            counter = 2
            while Lesson.objects.filter(module=self.module, slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
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


class ModuleAccordionSection(models.Model):
    module = models.ForeignKey("Module", on_delete=models.CASCADE, related_name="accordion_sections")
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_open_by_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "created_at"]

    def __str__(self):
        return f"{self.module.title} - {self.title}"


PAYMENT_METHOD_CHOICES = [
    ("bkash", "Bkash"),
    ("nagad", "Nagad"),
    ("rocket", "Rocket"),
    ("card", "Credit/Debit Card"),
    ("other", "Other"),
]


class EnrollmentStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    REVOKED = "revoked", "Revoked"


class PaymentSubmissionStatus(models.TextChoices):
    PENDING = "pending", "Pending review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class CourseEnrollment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="course_enrollments")
    course = models.ForeignKey("Course", on_delete=models.CASCADE, related_name="enrollments")
    status = models.CharField(max_length=20, choices=EnrollmentStatus.choices, default=EnrollmentStatus.ACTIVE)
    granted_by = models.ForeignKey(
        User,
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
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payment_submissions")
    course = models.ForeignKey("Course", on_delete=models.CASCADE, related_name="payment_submissions")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default="other")
    transaction_id = models.CharField(max_length=255)
    note = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=PaymentSubmissionStatus.choices, default=PaymentSubmissionStatus.PENDING)
    reviewed_by = models.ForeignKey(
        User,
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
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="module_purchases")
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
    title = models.CharField(max_length=255)
    slug = models.SlugField(blank=True)
    content_type = models.CharField(max_length=30, choices=LessonResourceType.choices, default=LessonResourceType.TEXT)
    order = models.PositiveIntegerField(default=0)
    is_preview = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    text_content = models.TextField(blank=True, default="")
    file = models.FileField(upload_to="lesson_resources/", blank=True, null=True)
    external_url = models.URLField(blank=True, default="")
    embed_url = models.URLField(blank=True, default="")
    metadata = models.JSONField(blank=True, default=dict)
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
            base_slug = slugify(self.title) or "resource"
            slug = base_slug
            counter = 2
            while LessonResource.objects.filter(lesson=self.lesson, slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
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


CONTENT_TYPE_CHOICES = [
    ("text", "Text / Rich HTML"),
    ("image", "Image"),
    ("audio", "Audio"),
    ("video", "Video (Upload)"),
    ("youtube", "YouTube Video"),
]


# class CourseContent(models.Model):
#     module = models.ForeignKey("Module", on_delete=models.CASCADE, related_name="course_contents", blank=True, null=True)
#     lesson = models.ForeignKey("Lesson", on_delete=models.SET_NULL, related_name="legacy_contents", blank=True, null=True)
#     title = models.CharField(max_length=255)
#     content_type = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES, default="text")
#     is_inline_reference = models.BooleanField(default=False)
#     order = models.PositiveIntegerField(default=0)
#     video_url = models.URLField(blank=True, null=True)
#     duration_seconds = models.PositiveIntegerField(blank=True, null=True, default=0)
#     text_content = models.TextField(blank=True, help_text="Plain text or HTML for text items.")
#     image = models.ImageField(upload_to="interactive/images/", blank=True, null=True)
#     audio = models.FileField(upload_to="interactive/audio/", blank=True, null=True)
#     video = models.FileField(upload_to="interactive/videos/", blank=True, null=True)
#     youtube_url = models.URLField(blank=True, help_text="Full YouTube URL e.g. https://www.youtube.com/watch?v=...")
#     created_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         ordering = ["order", "created_at"]
#         indexes = [
#             models.Index(fields=["module", "is_inline_reference", "order"]),
#         ]

#     def __str__(self):
#         source = self.module.title if self.module_id else "Content"
#         return f"{source} - {self.title}"

#     def get_youtube_embed_url(self):
#         from urllib.parse import parse_qs, urlparse
#         import re

#         if not self.youtube_url:
#             return ""

#         raw_url = self.youtube_url.strip()
#         video_id = None

#         try:
#             parsed = urlparse(raw_url)
#             host = (parsed.netloc or "").lower().replace("www.", "")

#             if host in ("youtube.com", "m.youtube.com"):
#                 if parsed.path == "/watch":
#                     video_id = (parse_qs(parsed.query).get("v") or [None])[0]
#                 elif parsed.path.startswith("/shorts/"):
#                     video_id = parsed.path.split("/shorts/", 1)[1].split("/", 1)[0]
#                 elif parsed.path.startswith("/live/"):
#                     video_id = parsed.path.split("/live/", 1)[1].split("/", 1)[0]
#                 elif parsed.path.startswith("/embed/"):
#                     video_id = parsed.path.split("/embed/", 1)[1].split("/", 1)[0]
#             elif host == "youtu.be":
#                 video_id = parsed.path.lstrip("/").split("/", 1)[0]
#         except Exception:
#             video_id = None

#         if not video_id:
#             match = re.search(r"(?:v=|youtu\.be/|/embed/|/shorts/|/live/)([a-zA-Z0-9_-]{11})", raw_url)
#             if match:
#                 video_id = match.group(1)

#         if video_id and re.fullmatch(r"[a-zA-Z0-9_-]{11}", video_id):
#             return f"https://www.youtube.com/embed/{video_id}"

#         return ""

#     @property
#     def duration(self):
#         secs = int(self.duration_seconds or 0)
#         if secs < 60:
#             return f"0:{secs:02d}"
#         minutes, seconds = divmod(secs, 60)
#         hours, minutes = divmod(minutes, 60)
#         if hours:
#             return f"{hours}:{minutes:02d}:{seconds:02d}"
#         return f"{minutes}:{seconds:02d}"


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

    def __str__(self):
        return f"{self.quiz.title} Q{self.id}"


class QuizAttempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="quiz_attempts")
    quiz = models.ForeignKey(CourseQuiz, on_delete=models.CASCADE, related_name="attempts")
    score = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at"]
        indexes = [
            models.Index(fields=["user", "submitted_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.quiz.title} ({self.score}%)"


class CourseCertificate(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="course_certificates")
    course = models.ForeignKey("Course", on_delete=models.CASCADE, related_name="certificates")
    certificate_code = models.CharField(max_length=40, unique=True)
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_at"]
        unique_together = [("user", "course")]

    def __str__(self):
        return f"{self.user.username} - {self.course.name} certificate"


class PaymentInstruction(models.Model):
    payment_method_name = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default="other", blank=True, null=True)
    details = models.TextField(blank=True, default="")
    image = models.ImageField(upload_to="payment_instructions/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["payment_method_name", "-created_at"]

    def __str__(self):
        return self.get_payment_method_name_display() if self.payment_method_name else "Payment instruction"

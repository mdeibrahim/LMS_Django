from django.db import models
from django.contrib.auth import get_user_model


User = get_user_model()


class UserRole(models.TextChoices):
    TEACHER = 'teacher', 'Teacher'
    STUDENT = 'student', 'Student'


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.STUDENT)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    full_name = models.CharField(max_length=160, blank=True, default='')
    phone_number = models.CharField(max_length=20, blank=True, default='')
    student_institution = models.CharField(max_length=180, blank=True, default='')
    student_level = models.CharField(max_length=80, blank=True, default='')
    teacher_institution = models.CharField(max_length=180, blank=True, default='')
    teacher_subject = models.CharField(max_length=120, blank=True, default='')
    teacher_experience_years = models.PositiveSmallIntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['user__username']

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class EmailOTP(models.Model):
    """One-time code for email verification after signup."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_otps')
    code = models.CharField(max_length=6)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"OTP for {self.user.email} — {self.code}"


class StudentDeviceSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='student_device_sessions')
    jti = models.CharField(max_length=64, unique=True)
    user_agent = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} device session ({self.jti})"
    

class Category(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(default='', blank=True,null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class Subcategory(models.Model):
    category = models.ForeignKey('Category', on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=255)
    slug = models.SlugField()
    description = models.TextField(default='', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('category', 'slug')
        ordering = ['name']

    def __str__(self):
        return f"{self.category.name} → {self.name}"


class Course(models.Model):
    subcategory = models.ForeignKey('Subcategory', on_delete=models.CASCADE, related_name='courses')
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        

    def __str__(self):
        return self.name

    @property
    def is_free(self):
        return (self.price or 0) == 0


class Module(models.Model):
    """A logical module inside a Course. A course can have many modules."""
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=255)
    slug = models.SlugField()
    body_content = models.TextField(
        help_text="Plain text or HTML. Use <span class='highlight-link' data-content-id='ID'>text</span> to add interactive highlights."
    )
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        verbose_name = 'Module'
        verbose_name_plural = 'Modules'
        unique_together = ('course', 'slug')
        ordering = ['order', 'title']

    def __str__(self):
        return f"{self.course.name} → {self.title}"


class ModuleAccordionSection(models.Model):
    module = models.ForeignKey('Module', on_delete=models.CASCADE, related_name='accordion_sections')
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_open_by_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.module.title} - {self.title}"


PAYMENT_METHOD_CHOICES = [
    ('bkash', 'Bkash'),
    ('nagad', 'Nagad'),
    ('rocket', 'Rocket'),
    ('card', 'Credit/Debit Card'),
    ('other', 'Other'),
]

class ModulePurchase(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='module_purchases')
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='purchases')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='other', blank=True, null=True)
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    is_purchased = models.BooleanField(default=False)
    purchased_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'course')
        ordering = ['-purchased_at']

    def __str__(self):
        return f"{self.user} purchased {self.course.name}"


CONTENT_TYPE_CHOICES = [
    ('text', 'Text / Rich HTML'),
    ('image', 'Image'),
    ('audio', 'Audio'),
    ('video', 'Video (Upload)'),
    ('youtube', 'YouTube Video'),
]

class CourseContent(models.Model):
    module = models.ForeignKey('Module', on_delete=models.CASCADE, related_name='course_contents', blank=True, null=True)
    title = models.CharField(max_length=255)
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES, default='text')
    is_inline_reference = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    video_url = models.URLField(blank=True, null=True)
    duration_seconds = models.PositiveIntegerField(blank=True, null=True, default=0)

    # Text content
    text_content = models.TextField(blank=True, help_text="Plain text or HTML for text items.")

    # Media files
    image = models.ImageField(upload_to='interactive/images/', blank=True, null=True)
    audio = models.FileField(upload_to='interactive/audio/', blank=True, null=True)
    video = models.FileField(upload_to='interactive/videos/', blank=True, null=True)

    # YouTube
    youtube_url = models.URLField(blank=True, help_text="Full YouTube URL e.g. https://www.youtube.com/watch?v=...")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.get_content_type_display()}] {self.title}"

    def get_youtube_embed_url(self):
        """Convert a YouTube URL (watch/shorts/youtu.be/embed) to embed URL."""
        from urllib.parse import urlparse, parse_qs
        import re

        if not self.youtube_url:
            return ''

        raw_url = self.youtube_url.strip()
        video_id = None

        try:
            parsed = urlparse(raw_url)
            host = (parsed.netloc or '').lower().replace('www.', '')

            # https://youtube.com/watch?v=VIDEO_ID
            if host in ('youtube.com', 'm.youtube.com'):
                if parsed.path == '/watch':
                    video_id = (parse_qs(parsed.query).get('v') or [None])[0]
                elif parsed.path.startswith('/shorts/'):
                    video_id = parsed.path.split('/shorts/', 1)[1].split('/', 1)[0]
                elif parsed.path.startswith('/live/'):
                    video_id = parsed.path.split('/live/', 1)[1].split('/', 1)[0]
                elif parsed.path.startswith('/embed/'):
                    video_id = parsed.path.split('/embed/', 1)[1].split('/', 1)[0]

            # https://youtu.be/VIDEO_ID
            elif host == 'youtu.be':
                video_id = parsed.path.lstrip('/').split('/', 1)[0]
        except Exception:
            video_id = None

        # Fallback regex (supports pasted text/HTML containing a YouTube id)
        if not video_id:
            match = re.search(r'(?:v=|youtu\.be/|/embed/|/shorts/|/live/)([a-zA-Z0-9_-]{11})', raw_url)
            if match:
                video_id = match.group(1)

        if video_id and re.fullmatch(r'[a-zA-Z0-9_-]{11}', video_id):
            return f"https://www.youtube.com/embed/{video_id}"

        return ''

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        source = None
        if self.module:
            try:
                source = self.module.title
            except Exception:
                source = None
        source = source or 'Content'
        return f"{source} - {self.title}"

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


class CourseQuiz(models.Model):
    module = models.ForeignKey('Module', on_delete=models.CASCADE, related_name='course_quizzes', blank=True, null=True)
    title = models.CharField(max_length=255)
    pass_score = models.PositiveSmallIntegerField(default=50)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        source = None
        if self.module:
            try:
                source = self.module.title
            except Exception:
                source = None
        source = source or 'Quiz'
        return f"{source} - {self.title}"


class CourseQuizQuestion(models.Model):
    quiz = models.ForeignKey(CourseQuiz, on_delete=models.CASCADE, related_name='questions')
    question = models.TextField()
    option_a = models.CharField(max_length=255)
    option_b = models.CharField(max_length=255)
    option_c = models.CharField(max_length=255)
    option_d = models.CharField(max_length=255)
    correct_option = models.CharField(max_length=1, choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')])
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.quiz.title} Q{self.id}"


class QuizAttempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz = models.ForeignKey(CourseQuiz, on_delete=models.CASCADE, related_name='attempts')
    score = models.PositiveSmallIntegerField(default=0)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.user.username} - {self.quiz.title} ({self.score}%)"




class CourseCertificate(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='course_certificates')
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='certificates')
    certificate_code = models.CharField(max_length=40, unique=True)
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'course')
        ordering = ['-issued_at']

    def __str__(self):
        return f"{self.user.username} - {self.course.name} certificate"


class ApprovalStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'

    

class PaymentInstruction(models.Model):
    payment_method_name = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='other', blank=True, null=True)
    details = models.TextField(blank=True, default='')
    image = models.ImageField(upload_to='payment_instructions/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)




from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
import uuid
from django.conf import settings


class UserManager(BaseUserManager):
    def create_user(self, email=None, password=None, **extra_fields):
        if not email and not extra_fields.get("phone_number"):
            raise ValueError("Either email or phone_number is required")
        if email:
            email = self.normalize_email(email)
        user = self.model(email=email or None, **extra_fields)
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
    email = models.EmailField(unique=True, blank=True, null=True)
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
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email or self.phone_number or f"User {self.pk}"

    def get_full_name(self):
        return (self.full_name or "").strip() or self.email or self.phone_number or "User"

    def get_short_name(self):
        return (self.full_name or "").strip() or self.email or self.phone_number or "User"

    def clean(self):
        if not self.email and not self.phone_number:
            from django.core.exceptions import ValidationError
            raise ValidationError("Provide at least an email address or a phone number.")

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


class OTP(models.Model):
    CHANNEL_EMAIL = "email"
    CHANNEL_SMS = "sms"
    CHANNEL_CHOICES = [
        (CHANNEL_EMAIL, "Email"),
        (CHANNEL_SMS, "SMS"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="otps")
    code = models.CharField(max_length=6)
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default=CHANNEL_EMAIL)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_used", "expires_at"]),
        ]

    def __str__(self):
        return f"OTP for {self.user.get_full_name()} via {self.channel} - {self.code}"


class PasswordResetSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

from django.db import models
from django.conf import settings
from content.models import UserRole


class StudentProfileManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().select_related("user").filter(user__role=UserRole.STUDENT)


class StudentProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
    )
    profile_picture = models.ImageField(upload_to="profile_pictures/", blank=True, null=True)
    full_name = models.CharField(max_length=160, blank=True, default="")
    phone_number = models.CharField(max_length=20, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    student_institution = models.CharField(max_length=180, blank=True, default="")
    student_level = models.CharField(max_length=80, blank=True, default="")

    objects = StudentProfileManager()

    class Meta:
        ordering = ["user__email"]
        verbose_name = "Student profile"
        verbose_name_plural = "Student profiles"

    @property
    def role(self):
        return UserRole.STUDENT

    def save(self, *args, **kwargs):
        if self.user_id and self.user.role != UserRole.STUDENT:
            self.user.role = UserRole.STUDENT
            self.user.save(update_fields=["role"])
        super().save(*args, **kwargs)


class StudentDeviceSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="student_device_sessions")
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
        return f"{self.user.email} device session ({self.jti})"

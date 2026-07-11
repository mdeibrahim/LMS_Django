from django.conf import settings
from django.db import models

from content.models import Category, Subcategory
from apps.authentication.models import UserRole


class TeacherProfileManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().select_related("user").prefetch_related("assigned_categories").filter(user__role=UserRole.TEACHER)


class TeacherProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teacher_profile",
    )
    profile_picture = models.ImageField(upload_to="profile_pictures/", blank=True, null=True)
    full_name = models.CharField(max_length=160, blank=True, default="")
    phone_number = models.CharField(max_length=20, blank=True, default="")
    address = models.TextField(blank=True, default="")
    bio = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    teacher_institution = models.CharField(max_length=180, blank=True, default="")
    teacher_subject = models.CharField(max_length=120, blank=True, default="")
    teacher_experience_years = models.PositiveSmallIntegerField(blank=True, null=True)
    assigned_categories = models.ManyToManyField(
        Category,
        blank=True,
        related_name="assigned_teachers",
        help_text="Categories that this teacher is allowed to manage.",
    )

    objects = TeacherProfileManager()

    class Meta:
        ordering = ["user__email"]
        verbose_name = "Teacher profile"
        verbose_name_plural = "Teacher profiles"

    @property
    def role(self):
        return UserRole.TEACHER

    def save(self, *args, **kwargs):
        if self.user_id and self.user.role != UserRole.TEACHER:
            self.user.role = UserRole.TEACHER
            self.user.save(update_fields=["role"])
        super().save(*args, **kwargs)

    @property
    def assigned_subcategories(self):
        if not self.pk:
            return Subcategory.objects.none()
        return Subcategory.objects.filter(category__in=self.assigned_categories.all()).select_related("category")

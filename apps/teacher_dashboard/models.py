from django.db import models

from content.models import UserProfile, UserRole


class TeacherManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(role=UserRole.TEACHER).select_related("user").prefetch_related("assigned_categories")


class TeacherProfile(UserProfile):
    objects = TeacherManager()

    class Meta:
        proxy = True
        verbose_name = "Teacher"
        verbose_name_plural = "Teachers"

    def save(self, *args, **kwargs):
        self.role = UserRole.TEACHER
        super().save(*args, **kwargs)

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import TeacherProfile
from apps.authentication.models import User, UserRole


@receiver(post_save, sender=User)
def create_teacher_profile(sender, instance, created, **kwargs):
    if created and instance.role == UserRole.TEACHER and not instance.is_staff:
        TeacherProfile.objects.get_or_create(
            user=instance,
            defaults={
                "full_name": instance.full_name,
                "phone_number": instance.phone_number,
            },
        )

from content.models import UserProfile, UserRole


def ensure_profile(user, default_role=UserRole.STUDENT):
    profile, _ = UserProfile.objects.get_or_create(user=user, defaults={"role": default_role})
    return profile

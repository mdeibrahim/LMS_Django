from content.models import UserRole


def ensure_profile(user, default_role=UserRole.STUDENT):
    if user.role == UserRole.TEACHER or default_role == UserRole.TEACHER:
        from apps.teacher_dashboard.models import TeacherProfile

        profile, _ = TeacherProfile.objects.get_or_create(user=user)
        legacy = getattr(user, "legacy_profile", None)
        if legacy:
            profile.full_name = legacy.full_name
            profile.phone_number = legacy.phone_number
            profile.profile_picture = legacy.profile_picture
            profile.teacher_institution = legacy.teacher_institution
            profile.teacher_subject = legacy.teacher_subject
            profile.teacher_experience_years = legacy.teacher_experience_years
            profile.save()
            try:
                profile.assigned_categories.set(legacy.assigned_categories.all())
            except Exception:
                pass
        if user.role != UserRole.TEACHER:
            user.role = UserRole.TEACHER
            user.save(update_fields=["role"])
        return profile

    from apps.student_dashboard.models import StudentProfile

    profile, _ = StudentProfile.objects.get_or_create(user=user)
    legacy = getattr(user, "legacy_profile", None)
    if legacy:
        profile.full_name = legacy.full_name
        profile.phone_number = legacy.phone_number
        profile.profile_picture = legacy.profile_picture
        profile.student_institution = legacy.student_institution
        profile.student_level = legacy.student_level
        profile.save()
    if user.role != UserRole.STUDENT:
        user.role = UserRole.STUDENT
        user.save(update_fields=["role"])
    return profile

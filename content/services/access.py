from content.models import Course, CourseEnrollment


def has_course_access(user, course):
    if course.is_free:
        return True
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return CourseEnrollment.objects.filter(user=user, course=course, status="active").exists()


def get_owned_course_ids(user):
    if not user or not user.is_authenticated:
        return set()
    if user.is_staff or user.is_superuser:
        return set(Course.objects.values_list("id", flat=True))
    return set(
        CourseEnrollment.objects.filter(user=user, status="active").values_list("course_id", flat=True)
    )


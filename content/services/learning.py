from django.db.models import Prefetch

from content.models import Lesson, LessonResource, Module


VISIBLE_LESSON_RESOURCES = LessonResource.objects.filter(is_published=True).order_by("order", "created_at")
VISIBLE_LESSONS = Lesson.objects.filter(is_published=True).order_by("order", "created_at")


def ensure_primary_lesson(module):
    lesson = module.lessons.order_by("order", "created_at").first()
    if lesson:
        return lesson

    return Lesson.objects.create(
        module=module,
        title=module.title,
        slug=module.slug,
        description=module.description or "",
        body_content=module.body_content or "",
        order=1,
        is_published=True,
        is_preview=module.course.is_free,
    )


def visible_lessons_qs():
    return Lesson.objects.filter(is_published=True).order_by("order", "created_at").prefetch_related(
        Prefetch("resources", queryset=VISIBLE_LESSON_RESOURCES),
        "quizzes",
    )


def module_playable_resources_qs(module):
    return LessonResource.objects.filter(
        lesson__module=module,
        is_published=True,
    ).select_related("lesson", "lesson__module", "lesson__module__course").order_by(
        "lesson__order",
        "order",
        "created_at",
    )


def first_playable_resource_for_module(module):
    return module_playable_resources_qs(module).first()


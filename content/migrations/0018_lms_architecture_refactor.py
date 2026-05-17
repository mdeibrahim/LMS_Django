import re

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def _replace_content_ids(raw_text, id_map):
    if not raw_text:
        return raw_text

    def repl(match):
        old_id = int(match.group(1))
        return f'data-content-id="{id_map.get(old_id, old_id)}"'

    return re.sub(r'data-content-id=["\'](\d+)["\']', repl, raw_text)


def migrate_lms_data(apps, schema_editor):
    Course = apps.get_model("content", "Course")
    Module = apps.get_model("content", "Module")
    Lesson = apps.get_model("content", "Lesson")
    LessonResource = apps.get_model("content", "LessonResource")
    CourseContent = apps.get_model("content", "CourseContent")
    ModuleAccordionSection = apps.get_model("content", "ModuleAccordionSection")
    CourseQuiz = apps.get_model("content", "CourseQuiz")
    ModulePurchase = apps.get_model("content", "ModulePurchase")
    CourseEnrollment = apps.get_model("content", "CourseEnrollment")
    PaymentSubmission = apps.get_model("content", "PaymentSubmission")

    lesson_by_module_id = {}
    resource_id_map = {}

    for module in Module.objects.select_related("course").all().order_by("course_id", "order", "id"):
        lesson = Lesson.objects.create(
            module_id=module.id,
            title=module.title,
            slug=module.slug,
            description=module.description or "",
            body_content=module.body_content or "",
            order=1,
            duration_seconds=0,
            is_preview=bool(getattr(module.course, "price", 0) == 0),
            is_published=True,
        )
        lesson_by_module_id[module.id] = lesson

    for content in CourseContent.objects.all().order_by("module_id", "order", "id"):
        lesson = lesson_by_module_id.get(content.module_id)
        if not lesson:
            continue

        content_type_map = {
            "text": "text",
            "image": "image",
            "audio": "audio",
            "video": "video",
            "youtube": "video",
        }
        resource = LessonResource.objects.create(
            lesson_id=lesson.id,
            title=content.title,
            slug=f"legacy-{content.id}",
            content_type=content_type_map.get(content.content_type, "attachment"),
            order=content.order,
            is_preview=lesson.is_preview,
            is_published=True,
            text_content=content.text_content or "",
            external_url=content.youtube_url or content.video_url or "",
            duration_seconds=content.duration_seconds or 0,
            file=content.image or content.audio or content.video,
        )
        resource_id_map[content.id] = resource.id
        content.lesson_id = lesson.id
        content.save(update_fields=["lesson"])

    for module in Module.objects.all():
        lesson = lesson_by_module_id.get(module.id)
        if not lesson:
            continue
        updated_body = _replace_content_ids(module.body_content or "", resource_id_map)
        if updated_body != module.body_content:
            module.body_content = updated_body
            module.save(update_fields=["body_content"])
        lesson.body_content = _replace_content_ids(lesson.body_content or "", resource_id_map)
        lesson.save(update_fields=["body_content"])

    for section in ModuleAccordionSection.objects.all():
        updated_content = _replace_content_ids(section.content or "", resource_id_map)
        if updated_content != section.content:
            section.content = updated_content
            section.save(update_fields=["content"])

    for quiz in CourseQuiz.objects.all():
        if quiz.module_id and quiz.module_id in lesson_by_module_id:
            quiz.lesson_id = lesson_by_module_id[quiz.module_id].id
            quiz.save(update_fields=["lesson"])

    for purchase in ModulePurchase.objects.select_related("user", "course").all():
        if purchase.is_purchased:
            CourseEnrollment.objects.get_or_create(
                user_id=purchase.user_id,
                course_id=purchase.course_id,
                defaults={
                    "status": "active",
                    "granted_at": purchase.purchased_at,
                },
            )
            PaymentSubmission.objects.create(
                user_id=purchase.user_id,
                course_id=purchase.course_id,
                payment_method=purchase.payment_method or "other",
                transaction_id=purchase.transaction_id or f"legacy-{purchase.id}",
                note="Imported from legacy confirmed purchase.",
                status="approved",
                submitted_at=purchase.purchased_at,
                reviewed_at=purchase.purchased_at,
            )
        elif purchase.transaction_id:
            PaymentSubmission.objects.create(
                user_id=purchase.user_id,
                course_id=purchase.course_id,
                payment_method=purchase.payment_method or "other",
                transaction_id=purchase.transaction_id,
                note="Imported from legacy pending purchase.",
                status="pending",
                submitted_at=purchase.purchased_at,
            )

    for lesson in Lesson.objects.all():
        duration_total = LessonResource.objects.filter(lesson_id=lesson.id).aggregate(total=models.Sum("duration_seconds")).get("total") or 0
        lesson.duration_seconds = duration_total
        lesson.save(update_fields=["duration_seconds"])


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0017_alter_category_description"),
    ]

    operations = [
        migrations.AlterField(
            model_name="module",
            name="body_content",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Legacy module body. New content should live on Lesson.body_content. Highlight links still work with lesson resource ids.",
            ),
        ),
        migrations.CreateModel(
            name="CourseEnrollment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("active", "Active"), ("revoked", "Revoked")], default="active", max_length=20)),
                ("granted_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="enrollments", to="content.course")),
                ("granted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="granted_course_enrollments", to=settings.AUTH_USER_MODEL)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="course_enrollments", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-granted_at"]},
        ),
        migrations.CreateModel(
            name="Lesson",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("slug", models.SlugField()),
                ("description", models.TextField(blank=True, default="")),
                ("body_content", models.TextField(blank=True, default="", help_text="Rich text lesson body. Use <span class='highlight-link' data-content-id='ID'>text</span> to link lesson resources.")),
                ("order", models.PositiveIntegerField(default=0)),
                ("duration_seconds", models.PositiveIntegerField(default=0)),
                ("thumbnail", models.ImageField(blank=True, null=True, upload_to="lesson_thumbnails/")),
                ("is_preview", models.BooleanField(default=False)),
                ("is_published", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("module", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lessons", to="content.module")),
            ],
            options={"ordering": ["order", "created_at"]},
        ),
        migrations.CreateModel(
            name="PaymentSubmission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("payment_method", models.CharField(choices=[("bkash", "Bkash"), ("nagad", "Nagad"), ("rocket", "Rocket"), ("card", "Credit/Debit Card"), ("other", "Other")], default="other", max_length=20)),
                ("transaction_id", models.CharField(max_length=255)),
                ("note", models.TextField(blank=True, default="")),
                ("status", models.CharField(choices=[("pending", "Pending review"), ("approved", "Approved"), ("rejected", "Rejected")], default="pending", max_length=20)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("rejection_reason", models.TextField(blank=True, default="")),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payment_submissions", to="content.course")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_payment_submissions", to=settings.AUTH_USER_MODEL)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payment_submissions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-submitted_at"]},
        ),
        migrations.CreateModel(
            name="LessonResource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("slug", models.SlugField(blank=True)),
                ("content_type", models.CharField(choices=[("text", "Text / Rich HTML"), ("video", "Video"), ("pdf", "PDF"), ("quiz", "Quiz"), ("audio", "Audio"), ("attachment", "Attachment"), ("external_link", "External Link"), ("embed", "Embedded Content"), ("image", "Image")], default="text", max_length=30)),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_preview", models.BooleanField(default=False)),
                ("is_published", models.BooleanField(default=True)),
                ("text_content", models.TextField(blank=True, default="")),
                ("file", models.FileField(blank=True, null=True, upload_to="lesson_resources/")),
                ("external_url", models.URLField(blank=True, default="")),
                ("embed_url", models.URLField(blank=True, default="")),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("duration_seconds", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("lesson", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="resources", to="content.lesson")),
            ],
            options={"ordering": ["order", "created_at"]},
        ),
        migrations.AddField(
            model_name="coursecontent",
            name="lesson",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="legacy_contents", to="content.lesson"),
        ),
        migrations.AddField(
            model_name="coursequiz",
            name="lesson",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="quizzes", to="content.lesson"),
        ),
        migrations.AddConstraint(
            model_name="lesson",
            constraint=models.UniqueConstraint(fields=("module", "slug"), name="uniq_lesson_slug_per_module"),
        ),
        migrations.AddConstraint(
            model_name="lessonresource",
            constraint=models.UniqueConstraint(fields=("lesson", "slug"), name="uniq_resource_slug_per_lesson"),
        ),
        migrations.AddConstraint(
            model_name="courseenrollment",
            constraint=models.UniqueConstraint(fields=("user", "course"), name="uniq_enrollment_per_user_course"),
        ),
        migrations.AddIndex(
            model_name="studentdevicesession",
            index=models.Index(fields=["user", "expires_at"], name="content_stud_user_id_0dfa25_idx"),
        ),
        migrations.AddIndex(
            model_name="emailotp",
            index=models.Index(fields=["user", "is_used", "expires_at"], name="content_emai_user_id_240ef7_idx"),
        ),
        migrations.AddIndex(
            model_name="module",
            index=models.Index(fields=["course", "order"], name="content_modu_course__1821f4_idx"),
        ),
        migrations.AddIndex(
            model_name="lesson",
            index=models.Index(fields=["module", "order"], name="content_less_module__2cf218_idx"),
        ),
        migrations.AddIndex(
            model_name="lesson",
            index=models.Index(fields=["module", "is_published", "order"], name="content_less_module__e61801_idx"),
        ),
        migrations.AddIndex(
            model_name="lessonresource",
            index=models.Index(fields=["lesson", "order"], name="content_less_lesson__12ab8e_idx"),
        ),
        migrations.AddIndex(
            model_name="lessonresource",
            index=models.Index(fields=["lesson", "content_type", "order"], name="content_less_lesson__193958_idx"),
        ),
        migrations.AddIndex(
            model_name="lessonresource",
            index=models.Index(fields=["lesson", "is_published", "order"], name="content_less_lesson__731c1c_idx"),
        ),
        migrations.AddIndex(
            model_name="courseenrollment",
            index=models.Index(fields=["user", "status"], name="content_cour_user_id_cf1b42_idx"),
        ),
        migrations.AddIndex(
            model_name="courseenrollment",
            index=models.Index(fields=["course", "status"], name="content_cour_course__7afd74_idx"),
        ),
        migrations.AddIndex(
            model_name="paymentsubmission",
            index=models.Index(fields=["course", "status", "submitted_at"], name="content_paym_course__00fdfe_idx"),
        ),
        migrations.AddIndex(
            model_name="paymentsubmission",
            index=models.Index(fields=["user", "status", "submitted_at"], name="content_paym_user_id_cb8760_idx"),
        ),
        migrations.AddIndex(
            model_name="paymentsubmission",
            index=models.Index(fields=["transaction_id"], name="content_paym_transac_76f2c9_idx"),
        ),
        migrations.AddIndex(
            model_name="coursecontent",
            index=models.Index(fields=["module", "is_inline_reference", "order"], name="content_cour_module__23b1f6_idx"),
        ),
        migrations.AddIndex(
            model_name="coursequiz",
            index=models.Index(fields=["lesson", "is_active"], name="content_cour_lesson__8238cc_idx"),
        ),
        migrations.AddIndex(
            model_name="coursequiz",
            index=models.Index(fields=["module", "is_active"], name="content_cour_module__a94858_idx"),
        ),
        migrations.AddIndex(
            model_name="quizattempt",
            index=models.Index(fields=["user", "submitted_at"], name="content_quiz_user_id_3399c3_idx"),
        ),
        migrations.RunPython(migrate_lms_data, migrations.RunPython.noop),
    ]

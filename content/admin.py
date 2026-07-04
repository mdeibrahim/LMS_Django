from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline

from apps.student_dashboard.models import StudentDeviceSession
from .models import (
    Category,
    Course,
    CourseCertificate,
    CourseEnrollment,
    CourseQuiz,
    CourseQuizQuestion,
    EmailOTP,
    EnrollmentStatus,
    Lesson,
    LessonResource,
    LessonResourceType,
    Module,
    # ModuleAccordionSection,
    PaymentInstruction,
    PaymentSubmission,
    PaymentSubmissionStatus,
    QuizAttempt,
    Subcategory,
    UserRole,
)
from .services import approve_payment_submission


User = get_user_model()


def tone_badge(label, tone="slate"):
    palette = {
        "slate": ("#0f172a", "#f8fafc", "#cbd5e1"),
        "teal": ("#115e59", "#ccfbf1", "#99f6e4"),
        "emerald": ("#166534", "#dcfce7", "#86efac"),
        "amber": ("#92400e", "#fef3c7", "#fcd34d"),
        "rose": ("#9f1239", "#ffe4e6", "#fda4af"),
        "blue": ("#1d4ed8", "#dbeafe", "#93c5fd"),
        "violet": ("#6d28d9", "#ede9fe", "#c4b5fd"),
    }
    text, background, border = palette.get(tone, palette["slate"])
    return format_html(
        '<span style="display:inline-flex;align-items:center;border-radius:999px;'
        'padding:0.3rem 0.65rem;font-size:0.75rem;font-weight:700;line-height:1;'
        'color:{};background:{};border:1px solid {};">{}</span>',
        text,
        background,
        border,
        label,
    )


def object_link(url, label, new_tab=False):
    target = ' target="_blank" rel="noreferrer"' if new_tab else ""
    return format_html(
        '<a href="{}"{} style="display:inline-flex;align-items:center;border-radius:999px;'
        'padding:0.35rem 0.75rem;font-size:0.75rem;font-weight:700;text-decoration:none;'
        'border:1px solid rgba(148,163,184,.35);background:rgba(248,250,252,.92);color:#0f172a;">{}</a>',
        url,
        target,
        label,
    )


class CourseCategoryFilter(admin.SimpleListFilter):
    title = "category"
    parameter_name = "category"

    def lookups(self, request, model_admin):
        return Category.objects.values_list("id", "name")

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(subcategory__category_id=self.value())
        return queryset


class RelatedCourseCategoryFilter(admin.SimpleListFilter):
    title = "course category"
    parameter_name = "course_category"

    def lookups(self, request, model_admin):
        return Category.objects.values_list("id", "name")

    def queryset(self, request, queryset):
        if not self.value():
            return queryset

        lookup_map = {
            "module": "course__subcategory__category_id",
            "lesson": "module__course__subcategory__category_id",
            "lessonresource": "lesson__module__course__subcategory__category_id",
            "courseenrollment": "course__subcategory__category_id",
            "paymentsubmission": "course__subcategory__category_id",
            "coursequiz": "lesson__module__course__subcategory__category_id",
            "quizattempt": "quiz__lesson__module__course__subcategory__category_id",
            "modulepurchase": "course__subcategory__category_id",
        }
        lookup = lookup_map.get(model_admin.model._meta.model_name)
        if lookup:
            return queryset.filter(**{lookup: self.value()})
        return queryset


class ModuleCompletenessFilter(admin.SimpleListFilter):
    title = "module readiness"
    parameter_name = "module_readiness"

    def lookups(self, request, model_admin):
        return (
            ("ready", "Has lessons and quiz"),
            ("missing_lessons", "Missing lessons"),
            ("missing_resources", "Lessons without resources"),
            ("missing_quiz", "Missing quiz"),
        )

    def queryset(self, request, queryset):
        queryset = queryset.annotate(
            lesson_total=Count("lessons", distinct=True),
            resource_total=Count("lessons__resources", filter=Q(lessons__resources__is_published=True), distinct=True),
            quiz_total=Count("lessons__quizzes", distinct=True),
        )
        if self.value() == "ready":
            return queryset.filter(lesson_total__gt=0, resource_total__gt=0, quiz_total__gt=0)
        if self.value() == "missing_lessons":
            return queryset.filter(lesson_total=0)
        if self.value() == "missing_resources":
            return queryset.filter(lesson_total__gt=0, resource_total=0)
        if self.value() == "missing_quiz":
            return queryset.filter(lesson_total__gt=0, quiz_total=0)
        return queryset


class SessionStateFilter(admin.SimpleListFilter):
    title = "session state"
    parameter_name = "session_state"

    def lookups(self, request, model_admin):
        return (("active", "Active"), ("expired", "Expired"))

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == "active":
            return queryset.filter(expires_at__gt=now)
        if self.value() == "expired":
            return queryset.filter(expires_at__lte=now)
        return queryset


class OTPStateFilter(admin.SimpleListFilter):
    title = "OTP state"
    parameter_name = "otp_state"

    def lookups(self, request, model_admin):
        return (("available", "Available"), ("used", "Used"), ("expired", "Expired"))

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == "available":
            return queryset.filter(is_used=False, expires_at__gt=now)
        if self.value() == "used":
            return queryset.filter(is_used=True)
        if self.value() == "expired":
            return queryset.filter(is_used=False, expires_at__lte=now)
        return queryset


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class UserAdmin(DjangoUserAdmin, ModelAdmin):
    readonly_fields = ("last_login", "date_joined")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("full_name",)}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_verified",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "password1", "password2"),
            },
        ),
    )
    list_display = (
        "id",
        "email",
        "full_name",
        "profile_role",
        "is_staff",
        "is_active",
        "last_login",
        "date_joined",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "date_joined")
    search_fields = ("email", "full_name")
    ordering = ("-date_joined",)
    date_hierarchy = "date_joined"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("student_profile", "teacher_profile")
            .annotate(active_enrollment_total=Count("course_enrollments", filter=Q(course_enrollments__status="active")))
        )

    @admin.display(description="Role", ordering="role")
    def profile_role(self, obj):
        role = getattr(obj, "role", None)
        if role == UserRole.TEACHER:
            return tone_badge("Teacher", "blue")
        if role == UserRole.STUDENT:
            return tone_badge("Student", "teal")
        return tone_badge("No profile", "amber")

    @admin.display(description="Enrollments", ordering="active_enrollment_total")
    def active_enrollments(self, obj):
        return obj.active_enrollment_total

    @admin.display(description="Full name", ordering="full_name")
    def full_name(self, obj):
        return getattr(getattr(obj, "profile", None), "full_name", "") or obj.get_full_name() or "—"


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ("id","name", "subcategory_total", "course_total", "created_at")
    search_fields = ("name", "slug", "description")
    readonly_fields = ("slug",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            subcategory_total=Count("subcategories", distinct=True),
            course_total=Count("subcategories__courses", distinct=True),
        )

    @admin.display(description="Subcategories", ordering="subcategory_total")
    def subcategory_total(self, obj):
        return obj.subcategory_total

    @admin.display(description="Courses", ordering="course_total")
    def course_total(self, obj):
        return obj.course_total


@admin.register(Subcategory)
class SubcategoryAdmin(ModelAdmin):
    list_display = ("name", "category", "course_total", "created_at")
    list_filter = ("category",)
    search_fields = ("name", "slug", "category__name", "description")
    autocomplete_fields = ("category",)
    readonly_fields = ("slug",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("category").annotate(course_total=Count("courses"))

    @admin.display(description="Courses", ordering="course_total")
    def course_total(self, obj):
        return obj.course_total


@admin.register(Course)
class CourseAdmin(ModelAdmin):
    list_display = (
        "id",
        "name",
        "subcategory",
        "price_display",
        "module_total",
        "lesson_total",
        "resource_total",
        "enrollment_total",
        "created_at",
    )
    list_filter = (CourseCategoryFilter, "subcategory", "created_at")
    search_fields = ("name", "slug", "description", "subcategory__name", "subcategory__category__name")
    autocomplete_fields = ("subcategory", "teacher")
    readonly_fields = ("slug", "module_total", "lesson_total", "resource_total", "enrollment_count")
    date_hierarchy = "created_at"


    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("subcategory", "subcategory__category")
            .annotate(
                module_total=Count("modules", distinct=True),
                lesson_total=Count("modules__lessons", distinct=True),
                resource_total=Count("modules__lessons__resources", filter=Q(modules__lessons__resources__is_published=True), distinct=True),
                enrollment_total=Count("enrollments", filter=Q(enrollments__status="active"), distinct=True),
            )
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "teacher":
            from apps.teacher_dashboard.models import TeacherProfile

            kwargs["queryset"] = TeacherProfile.objects.select_related("user").all()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description="Price", ordering="price")
    def price_display(self, obj):
        return tone_badge("Free", "emerald") if obj.is_free else tone_badge(f"৳{obj.price}", "violet")

    @admin.display(description="Modules", ordering="module_total")
    def module_total(self, obj):
        return obj.module_total

    @admin.display(description="Lessons", ordering="lesson_total")
    def lesson_total(self, obj):
        return obj.lesson_total

    @admin.display(description="Resources", ordering="resource_total")
    def resource_total(self, obj):
        return obj.resource_total

    @admin.display(description="Enrollments", ordering="enrollment_total")
    def enrollment_total(self, obj):
        return obj.enrollment_total


class LessonInline(TabularInline):
    model = Lesson
    extra = 0
    show_change_link = True
    fields = ("title", "slug", "order", "is_preview", "is_published")
    readonly_fields = ("slug",)


# class ModuleAccordionSectionInline(TabularInline):
#     model = ModuleAccordionSection
#     extra = 0
#     show_change_link = True
#     fields = ("title", "order", "is_open_by_default")


@admin.register(Module)
class ModuleAdmin(ModelAdmin):
    list_display = (
        "id",
        "title",
        "course",
        "order",
        "lesson_total",
        "resource_total",
        "quiz_total",
        "module_health",
        "frontend_editor_link",
    )
    search_fields = ("title", "slug", "course__name", "description")
    autocomplete_fields = ("course",)
    list_filter = (ModuleCompletenessFilter, RelatedCourseCategoryFilter, "updated_at")
    inlines = [LessonInline]
    readonly_fields = ("frontend_editor_link", "module_shortcuts", "created_at", "updated_at", "slug")

    class ModuleForm(forms.ModelForm):
        class Meta:
            model = Module
            fields = "__all__"
            widgets = {
                "body_content": forms.Textarea(attrs={"class": "rte-enabled", "rows": 10}),
                "description": forms.Textarea(attrs={"rows": 4}),
            }

    form = ModuleForm

    class Media:
        js = ("js/admin_rte.js",)
        css = {"all": ("css/admin_rte.css",)}

    fieldsets = (
        ("Basic Info", {"fields": ("course", "title", "slug", "order", "frontend_editor_link")}),
        ("Legacy Module Body", {"fields": ("description", "body_content")}),
        ("Management Shortcuts", {"fields": ("module_shortcuts",)}),
        ("Audit", {"fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("course", "course__subcategory", "course__subcategory__category")
            .annotate(
                lesson_total=Count("lessons", distinct=True),
                resource_total=Count("lessons__resources", filter=Q(lessons__resources__is_published=True), distinct=True),
                quiz_total=Count("lessons__quizzes", distinct=True),
            )
        )

    @admin.display(description="Lessons", ordering="lesson_total")
    def lesson_total(self, obj):
        return obj.lesson_total

    @admin.display(description="Resources", ordering="resource_total")
    def resource_total(self, obj):
        return obj.resource_total

    @admin.display(description="Quizzes", ordering="quiz_total")
    def quiz_total(self, obj):
        return obj.quiz_total

    @admin.display(description="Readiness")
    def module_health(self, obj):
        if obj.lesson_total and obj.resource_total and obj.quiz_total:
            return tone_badge("Ready", "emerald")
        if obj.lesson_total and (obj.resource_total or obj.quiz_total):
            return tone_badge("In progress", "amber")
        return tone_badge("Draft", "rose")

    @admin.display(description="Management")
    def module_shortcuts(self, obj):
        if not obj.pk:
            return "Save first."
        lesson_url = f"{reverse('admin:content_lesson_changelist')}?module__id__exact={obj.id}"
        resource_url = f"{reverse('admin:content_lessonresource_changelist')}?lesson__module__id__exact={obj.id}"
        return format_html("{} {}", object_link(lesson_url, "Lessons"), object_link(resource_url, "Resources"))

    @admin.display(description="Frontend editor")
    def frontend_editor_link(self, obj):
        if not obj.pk:
            return tone_badge("Save first", "amber")
        course_slug = getattr(getattr(obj, "course", None), "slug", "")
        if not course_slug:
            return tone_badge("Set course slug first", "rose")
        if not obj.slug:
            return tone_badge("Set slug first", "rose")
        return object_link(reverse("content:module_editor", args=[course_slug, obj.slug]), "Open editor", new_tab=True)


class LessonResourceInline(TabularInline):
    model = LessonResource
    extra = 0
    show_change_link = True
    fields = ("title", "content_type", "order", "is_preview", "is_published")


@admin.register(Lesson)
class LessonAdmin(ModelAdmin):
    list_display = (
        "id",
        "title",
        "module",
        "order",
        "resource_total",
        "quiz_total",
        "frontend_editor_link",
        "is_preview",
        "is_published",
    )
    list_filter = ("is_preview", "is_published", RelatedCourseCategoryFilter)
    search_fields = ("title", "slug", "module__title", "module__course__name")
    autocomplete_fields = ("module",)
    inlines = [LessonResourceInline]
    readonly_fields = ("frontend_editor_link", "slug")

    class LessonForm(forms.ModelForm):
        class Meta:
            model = Lesson
            fields = "__all__"
            widgets = {
                "body_content": forms.Textarea(attrs={"class": "rte-enabled", "rows": 12}),
                "description": forms.Textarea(attrs={"rows": 4}),
            }

    form = LessonForm

    class Media:
        js = ("js/admin_rte.js",)
        css = {"all": ("css/admin_rte.css",)}

    fieldsets = (
        ("Basic Info", {"fields": ("module", "title", "slug", "order", "frontend_editor_link")}),
        ("Content", {"fields": ("description", "body_content")}),
        ("Visibility", {"fields": ("is_preview", "is_published", )}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("module", "module__course").annotate(
            resource_total=Count("resources", distinct=True),
            quiz_total=Count("quizzes", distinct=True),
        )

    @admin.display(description="Resources", ordering="resource_total")
    def resource_total(self, obj):
        return obj.resource_total

    @admin.display(description="Quizzes", ordering="quiz_total")
    def quiz_total(self, obj):
        return obj.quiz_total

    @admin.display(description="Frontend editor")
    def frontend_editor_link(self, obj):
        if not obj.pk:
            return tone_badge("Save first", "amber")
        course_slug = getattr(getattr(obj.module, "course", None), "slug", "")
        module_slug = getattr(obj.module, "slug", "")
        lesson_slug = getattr(obj, "slug", "")
        if not course_slug or not module_slug or not lesson_slug:
            return tone_badge("Set related slugs first", "rose")
        return object_link(
            reverse("content:lesson_editor", args=[course_slug, module_slug, lesson_slug]),
            "Open editor",
            new_tab=True,
        )


@admin.register(LessonResource)
class LessonResourceAdmin(ModelAdmin):
    list_display = ("id", "title", "lesson", "resource_kind", "order", "is_preview", "is_published", "preview")
    list_filter = ("content_type", "is_preview", "is_published", RelatedCourseCategoryFilter)
    search_fields = ("title", "slug", "lesson__title", "lesson__module__title", "lesson__module__course__name")
    autocomplete_fields = ("lesson",)
    readonly_fields = ("preview", "created_at", "updated_at", "slug")

    fieldsets = (
        ("Basic", {"fields": ("lesson", "title", "slug", "content_type", "order", "is_preview", "is_published")}),
        ("Text", {"fields": ("text_content",), "classes": ("collapse",)}),
        ("File / URL", {"fields": ("file", "external_url", "embed_url", "duration_seconds"), "classes": ("collapse",)}),
        ("Preview", {"fields": ("preview",)}),
        ("Audit", {"fields": ("created_at", "updated_at")}),
    )

    def resource_kind(self, obj):
        tone_map = {
            LessonResourceType.TEXT: "slate",
            LessonResourceType.VIDEO: "emerald",
            LessonResourceType.PDF: "rose",
            LessonResourceType.QUIZ: "amber",
            LessonResourceType.AUDIO: "violet",
            LessonResourceType.ATTACHMENT: "blue",
            LessonResourceType.EXTERNAL_LINK: "blue",
            LessonResourceType.EMBED: "teal",
            LessonResourceType.IMAGE: "blue",
        }
        return tone_badge(obj.get_content_type_display(), tone_map.get(obj.content_type, "slate"))

    resource_kind.short_description = "Type"

    def preview(self, obj):
        if obj.content_type == LessonResourceType.IMAGE and obj.file:
            return format_html('<img src="{}" style="max-height:88px;max-width:160px;border-radius:12px;" />', obj.file.url)
        if obj.content_type == LessonResourceType.AUDIO and obj.file:
            return format_html('<audio controls style="max-width:220px;"><source src="{}"></audio>', obj.file.url)
        if obj.content_type == LessonResourceType.VIDEO and obj.file:
            return format_html('<video controls style="max-height:88px;max-width:160px;"><source src="{}"></video>', obj.file.url)
        if obj.external_url:
            return object_link(obj.external_url, "Open link", new_tab=True)
        if obj.text_content:
            return format_html('<div style="max-width:260px;overflow:hidden;font-size:12px;line-height:1.6;color:#475569;">{}</div>', obj.text_content[:140])
        return "—"


class CourseQuizQuestionInline(TabularInline):
    model = CourseQuizQuestion
    extra = 0
    formfield_overrides = {
        CourseQuizQuestion._meta.get_field("question").__class__: {
            "widget": forms.Textarea(
                attrs={
                    "rows": 6,
                    "placeholder": "Type the question here. Press Enter for a new line, or paste simple HTML if needed.",
                }
            )
        }
    }


@admin.register(CourseQuiz)
class CourseQuizAdmin(ModelAdmin):
    list_display = ("title", "lesson", "pass_score", "question_total", "quiz_state", "created_at")
    list_filter = ("is_active", "created_at", RelatedCourseCategoryFilter)
    search_fields = ("title", "lesson__title", "lesson__module__title", "lesson__module__course__name")
    autocomplete_fields = ("lesson", "module")
    inlines = [CourseQuizQuestionInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("lesson", "lesson__module", "module").annotate(
            question_total=Count("questions", distinct=True)
        )

    @admin.display(description="Questions", ordering="question_total")
    def question_total(self, obj):
        return obj.question_total

    @admin.display(description="State", ordering="is_active")
    def quiz_state(self, obj):
        return tone_badge("Active", "emerald") if obj.is_active else tone_badge("Archived", "amber")


@admin.register(QuizAttempt)
class QuizAttemptAdmin(ModelAdmin):
    list_display = ("user", "quiz", "score_badge", "submitted_at")
    list_filter = ("submitted_at", RelatedCourseCategoryFilter)
    search_fields = ("user__email", "quiz__title")
    autocomplete_fields = ("user", "quiz")

    @admin.display(description="Score", ordering="score")
    def score_badge(self, obj):
        if obj.score >= 80:
            return tone_badge(f"{obj.score}%", "emerald")
        if obj.score >= 50:
            return tone_badge(f"{obj.score}%", "amber")
        return tone_badge(f"{obj.score}%", "rose")


@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(ModelAdmin):
    list_display = ("user", "course", "status_badge", "granted_by", "granted_at")
    list_filter = ("status", RelatedCourseCategoryFilter, "granted_at")
    search_fields = ("user__email", "course__name")
    autocomplete_fields = ("user", "course", "granted_by")

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        return tone_badge(obj.get_status_display(), "emerald" if obj.status == EnrollmentStatus.ACTIVE else "rose")


@admin.action(description="Approve selected payment submissions")
def approve_submissions(modeladmin, request, queryset):
    approved = 0
    for submission in queryset.filter(status=PaymentSubmissionStatus.PENDING):
        approve_payment_submission(submission, reviewed_by=request.user)
        approved += 1
    modeladmin.message_user(request, f"{approved} payment submission(s) approved.", level=messages.SUCCESS)


@admin.action(description="Mark selected payment submissions as rejected")
def reject_submissions(modeladmin, request, queryset):
    updated = queryset.update(
        status=PaymentSubmissionStatus.REJECTED,
        reviewed_by=request.user,
        reviewed_at=timezone.now(),
        rejection_reason="Rejected from bulk admin action.",
    )
    modeladmin.message_user(request, f"{updated} payment submission(s) rejected.", level=messages.WARNING)


@admin.register(PaymentSubmission)
class PaymentSubmissionAdmin(ModelAdmin):
    list_display = ("user", "course", "payment_method", "transaction_id", "status_badge", "submitted_at", "reviewed_at")
    list_filter = ("status", "payment_method", RelatedCourseCategoryFilter, "submitted_at")
    search_fields = ("user__email", "course__name", "transaction_id", "note")
    autocomplete_fields = ("user", "course", "reviewed_by")
    readonly_fields = ("submitted_at", "updated_at", "reviewed_at")
    actions = (approve_submissions, reject_submissions)

    fieldsets = (
        ("Payment", {"fields": ("user", "course", "payment_method", "transaction_id", "note")}),
        ("Review", {"fields": ("status", "reviewed_by", "reviewed_at", "rejection_reason")}),
        ("Audit", {"fields": ("submitted_at", "updated_at")}),
    )

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        tone = {
            PaymentSubmissionStatus.PENDING: "amber",
            PaymentSubmissionStatus.APPROVED: "emerald",
            PaymentSubmissionStatus.REJECTED: "rose",
        }.get(obj.status, "slate")
        return tone_badge(obj.get_status_display(), tone)


@admin.register(CourseCertificate)
class CourseCertificateAdmin(ModelAdmin):
    list_display = ("user", "course", "certificate_code", "issued_at")
    list_filter = ("issued_at", "course")
    search_fields = ("user__email", "course__name", "certificate_code")
    autocomplete_fields = ("user", "course")


@admin.action(description="Remove expired sessions")
def remove_expired_sessions(modeladmin, request, queryset):
    removed, _ = queryset.filter(expires_at__lte=timezone.now()).delete()
    modeladmin.message_user(request, f"{removed} expired session record(s) removed.", level=messages.SUCCESS)


@admin.register(StudentDeviceSession)
class StudentDeviceSessionAdmin(ModelAdmin):
    list_display = ("user", "session_state", "ip_address", "created_at", "expires_at", "last_seen")
    list_filter = (SessionStateFilter, "created_at", "expires_at")
    search_fields = ("user__email", "jti", "ip_address", "user_agent")
    autocomplete_fields = ("user",)
    actions = (remove_expired_sessions,)

    @admin.display(description="State")
    def session_state(self, obj):
        return tone_badge("Active", "emerald") if obj.expires_at > timezone.now() else tone_badge("Expired", "rose")


@admin.register(EmailOTP)
class EmailOTPAdmin(ModelAdmin):
    list_display = ("user", "code", "otp_state", "created_at", "expires_at")
    list_filter = (OTPStateFilter, "created_at", "expires_at")
    search_fields = ("user__email", "code")
    autocomplete_fields = ("user",)

    @admin.display(description="State")
    def otp_state(self, obj):
        if obj.is_used:
            return tone_badge("Used", "emerald")
        if obj.expires_at <= timezone.now():
            return tone_badge("Expired", "rose")
        return tone_badge("Available", "amber")


@admin.register(PaymentInstruction)
class PaymentInstructionAdmin(ModelAdmin):
    list_display = ("id", "payment_method_name", "has_image", "created_at")
    search_fields = ("payment_method_name", "details")

    class PaymentInstructionForm(forms.ModelForm):
        class Meta:
            model = PaymentInstruction
            fields = "__all__"
            widgets = {"details": forms.Textarea(attrs={"class": "rte-enabled", "rows": 8})}

    form = PaymentInstructionForm

    class Media:
        js = ("js/admin_rte.js",)
        css = {"all": ("css/admin_rte.css",)}

    @admin.display(description="Image")
    def has_image(self, obj):
        return tone_badge("Uploaded", "emerald") if obj.image else tone_badge("Missing", "amber")

admin.site.site_header = "Interactive Teaching Platform"
admin.site.site_title = "Teaching Platform Admin"
admin.site.index_title = "Operations Dashboard"

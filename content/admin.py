from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline

from .models import (
    Category,
    Course,
    CourseCertificate,
    CourseContent,
    CourseQuiz,
    CourseQuizQuestion,
    EmailOTP,
    Module,
    ModuleAccordionSection,
    ModulePurchase,
    PaymentInstruction,
    QuizAttempt,
    StudentDeviceSession,
    Subcategory,
    UserProfile,
    UserRole,
)


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

        model_name = model_admin.model._meta.model_name
        field_map = {
            "module": "course__subcategory__category_id",
            "modulepurchase": "course__subcategory__category_id",
            "coursecontent": "module__course__subcategory__category_id",
            "coursequiz": "module__course__subcategory__category_id",
            "quizattempt": "quiz__module__course__subcategory__category_id",
        }
        lookup = field_map.get(model_name)
        if lookup:
            return queryset.filter(**{lookup: self.value()})
        return queryset


class ModuleCompletenessFilter(admin.SimpleListFilter):
    title = "module readiness"
    parameter_name = "module_readiness"

    def lookups(self, request, model_admin):
        return (
            ("ready", "Has content and quiz"),
            ("missing_content", "Missing content"),
            ("missing_quiz", "Missing quiz"),
            ("draft", "Missing both"),
        )

    def queryset(self, request, queryset):
        queryset = queryset.annotate(
            content_total=Count(
                "course_contents",
                filter=Q(course_contents__is_inline_reference=False),
                distinct=True,
            ),
            quiz_total=Count("course_quizzes", distinct=True),
        )
        if self.value() == "ready":
            return queryset.filter(content_total__gt=0, quiz_total__gt=0)
        if self.value() == "missing_content":
            return queryset.filter(content_total=0, quiz_total__gt=0)
        if self.value() == "missing_quiz":
            return queryset.filter(content_total__gt=0, quiz_total=0)
        if self.value() == "draft":
            return queryset.filter(content_total=0, quiz_total=0)
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
        return (
            ("available", "Available"),
            ("used", "Used"),
            ("expired", "Expired"),
        )

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == "available":
            return queryset.filter(is_used=False, expires_at__gt=now)
        if self.value() == "used":
            return queryset.filter(is_used=True)
        if self.value() == "expired":
            return queryset.filter(is_used=False, expires_at__lte=now)
        return queryset


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    extra = 0
    can_delete = False
    fk_name = "user"
    autocomplete_fields = ()
    fieldsets = (
        ("Profile", {"fields": ("role", "full_name", "phone_number", "profile_picture")}),
        ("Student Details", {"fields": ("student_institution", "student_level")}),
        (
            "Teacher Details",
            {"fields": ("teacher_institution", "teacher_subject", "teacher_experience_years")},
        ),
    )


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class UserAdmin(DjangoUserAdmin, ModelAdmin):
    inlines = [UserProfileInline]
    list_display = (
        "username",
        "email",
        "profile_role",
        "is_staff",
        "is_active",
        "course_purchases",
        "last_login",
        "date_joined",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "groups", "date_joined")
    search_fields = ("username", "first_name", "last_name", "email")
    ordering = ("-date_joined",)
    date_hierarchy = "date_joined"
    list_per_page = 30
    list_select_related = ()

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("profile")
            .annotate(confirmed_purchase_total=Count("module_purchases", filter=Q(module_purchases__is_purchased=True)))
        )

    @admin.display(description="Role", ordering="profile__role")
    def profile_role(self, obj):
        role = getattr(getattr(obj, "profile", None), "role", None)
        if role == UserRole.TEACHER:
            return tone_badge("Teacher", "blue")
        if role == UserRole.STUDENT:
            return tone_badge("Student", "teal")
        return tone_badge("No profile", "amber")

    @admin.display(description="Confirmed purchases", ordering="confirmed_purchase_total")
    def course_purchases(self, obj):
        return obj.confirmed_purchase_total


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ("name", "subcategory_total", "course_total", "created_at")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)

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
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("category__name", "name")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("category").annotate(
            course_total=Count("courses", distinct=True)
        )

    @admin.display(description="Courses", ordering="course_total")
    def course_total(self, obj):
        return obj.course_total


@admin.action(description="Mark selected purchases as confirmed")
def mark_purchases_confirmed(modeladmin, request, queryset):
    updated = queryset.update(is_purchased=True)
    modeladmin.message_user(request, f"{updated} purchase(s) marked as confirmed.", level=messages.SUCCESS)


@admin.action(description="Mark selected purchases as pending")
def mark_purchases_pending(modeladmin, request, queryset):
    updated = queryset.update(is_purchased=False)
    modeladmin.message_user(request, f"{updated} purchase(s) moved back to pending.", level=messages.WARNING)


@admin.register(Course)
class CourseAdmin(ModelAdmin):
    list_display = (
        "name",
        "subcategory",
        "price_display",
        "module_total",
        "content_total",
        "confirmed_sales",
        "created_at",
        "course_actions",
    )
    list_filter = (CourseCategoryFilter, "subcategory", "created_at")
    search_fields = ("name", "slug", "description", "subcategory__name", "subcategory__category__name")
    autocomplete_fields = ("subcategory",)
    prepopulated_fields = {"slug": ("name",)}
    date_hierarchy = "created_at"
    list_per_page = 30
    ordering = ("name",)

    fieldsets = (
        ("Catalog", {"fields": ("subcategory", "name", "slug", "price")}),
        ("Course Description", {"fields": ("description",)}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("subcategory", "subcategory__category")
            .annotate(
                module_total=Count("modules", distinct=True),
                content_total=Count(
                    "modules__course_contents",
                    filter=Q(modules__course_contents__is_inline_reference=False),
                    distinct=True,
                ),
                confirmed_sales=Count("purchases", filter=Q(purchases__is_purchased=True), distinct=True),
            )
        )

    @admin.display(description="Price", ordering="price")
    def price_display(self, obj):
        if obj.is_free:
            return tone_badge("Free", "emerald")
        return tone_badge(f"৳{obj.price}", "violet")

    @admin.display(description="Modules", ordering="module_total")
    def module_total(self, obj):
        return obj.module_total

    @admin.display(description="Interactive items", ordering="content_total")
    def content_total(self, obj):
        return obj.content_total

    @admin.display(description="Confirmed sales", ordering="confirmed_sales")
    def confirmed_sales(self, obj):
        return obj.confirmed_sales

    @admin.display(description="Workflow")
    def course_actions(self, obj):
        module_url = f"{reverse('admin:content_module_changelist')}?course__id__exact={obj.id}"
        purchase_url = f"{reverse('admin:content_modulepurchase_changelist')}?course__id__exact={obj.id}"
        return format_html("{} {}", object_link(module_url, "Modules"), object_link(purchase_url, "Sales"))


class CourseContentInline(TabularInline):
    model = CourseContent
    extra = 0
    show_change_link = True
    fields = ("title", "content_type", "order", "preview")
    readonly_fields = ("preview",)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_inline_reference=False)

    @admin.display(description="Preview")
    def preview(self, obj):
        if not obj.pk:
            return "Save to preview"
        return CourseContentAdmin.preview(self, obj)


class ModuleAccordionSectionInline(TabularInline):
    model = ModuleAccordionSection
    extra = 0
    show_change_link = True
    fields = ("title", "order", "is_open_by_default")


@admin.register(ModulePurchase)
class ModulePurchaseAdmin(ModelAdmin):
    list_display = (
        "id",
        "user",
        "course",
        "purchase_status",
        "payment_method",
        "module_price",
        "transaction_id",
        "purchased_at",
    )
    list_select_related = ("user", "course")
    list_filter = ("is_purchased", "payment_method", "purchased_at", RelatedCourseCategoryFilter)
    search_fields = ("user__username", "user__email", "course__name", "transaction_id")
    autocomplete_fields = ("user", "course")
    date_hierarchy = "purchased_at"
    list_per_page = 30
    ordering = ("-purchased_at",)
    actions = (mark_purchases_confirmed, mark_purchases_pending)

    @admin.display(description="Status", ordering="is_purchased")
    def purchase_status(self, obj):
        return tone_badge("Confirmed", "emerald") if obj.is_purchased else tone_badge("Pending", "amber")

    @admin.display(description="Price", ordering="course__price")
    def module_price(self, obj):
        return f"৳{obj.course.price}"


@admin.register(UserProfile)
class UserProfileAdmin(ModelAdmin):
    list_display = (
        "user",
        "role_badge",
        "full_name",
        "phone_number",
        "profile_health",
        "created_at",
        "updated_at",
    )
    list_filter = ("role", "created_at")
    search_fields = ("user__username", "user__email", "full_name", "phone_number")
    autocomplete_fields = ("user",)
    list_per_page = 30
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Account", {"fields": ("user", "role", "full_name", "phone_number", "profile_picture")}),
        ("Student Fields", {"fields": ("student_institution", "student_level")}),
        ("Teacher Fields", {"fields": ("teacher_institution", "teacher_subject", "teacher_experience_years")}),
        ("Audit", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Role", ordering="role")
    def role_badge(self, obj):
        return tone_badge(obj.get_role_display(), "blue" if obj.role == UserRole.TEACHER else "teal")

    @admin.display(description="Completeness")
    def profile_health(self, obj):
        filled_fields = sum(
            bool(value)
            for value in (
                obj.full_name,
                obj.phone_number,
                obj.student_institution if obj.role == UserRole.STUDENT else obj.teacher_institution,
                obj.student_level if obj.role == UserRole.STUDENT else obj.teacher_subject,
            )
        )
        return tone_badge(f"{filled_fields}/4 fields", "emerald" if filled_fields >= 3 else "amber")


@admin.action(description="Remove expired sessions")
def remove_expired_sessions(modeladmin, request, queryset):
    removed, _ = queryset.filter(expires_at__lte=timezone.now()).delete()
    modeladmin.message_user(request, f"{removed} expired session record(s) removed.", level=messages.SUCCESS)


@admin.register(StudentDeviceSession)
class StudentDeviceSessionAdmin(ModelAdmin):
    list_display = ("user", "session_state", "ip_address", "created_at", "expires_at", "last_seen")
    search_fields = ("user__username", "jti", "ip_address", "user_agent")
    list_filter = (SessionStateFilter, "created_at", "expires_at")
    autocomplete_fields = ("user",)
    list_per_page = 50
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "last_seen")
    actions = (remove_expired_sessions,)

    fieldsets = (
        ("Session", {"fields": ("user", "jti", "user_agent", "ip_address")}),
        ("Lifecycle", {"fields": ("created_at", "last_seen", "expires_at")}),
    )

    @admin.display(description="State")
    def session_state(self, obj):
        return tone_badge("Active", "emerald") if obj.expires_at > timezone.now() else tone_badge("Expired", "rose")


class CourseQuizQuestionInline(TabularInline):
    model = CourseQuizQuestion
    extra = 0
    fields = ("order", "question", "option_a", "option_b", "option_c", "option_d", "correct_option")


@admin.action(description="Activate selected quizzes")
def activate_quizzes(modeladmin, request, queryset):
    updated = queryset.update(is_active=True)
    modeladmin.message_user(request, f"{updated} quiz(es) activated.", level=messages.SUCCESS)


@admin.action(description="Archive selected quizzes")
def archive_quizzes(modeladmin, request, queryset):
    updated = queryset.update(is_active=False)
    modeladmin.message_user(request, f"{updated} quiz(es) archived.", level=messages.WARNING)


@admin.register(CourseQuiz)
class CourseQuizAdmin(ModelAdmin):
    list_display = ("title", "module", "pass_score", "question_total", "quiz_state", "created_at")
    list_filter = ("is_active", "created_at", RelatedCourseCategoryFilter)
    search_fields = ("title", "module__title", "module__course__name")
    autocomplete_fields = ("module",)
    inlines = [CourseQuizQuestionInline]
    actions = (activate_quizzes, archive_quizzes)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("module", "module__course").annotate(
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
    search_fields = ("user__username", "user__email", "quiz__title")
    autocomplete_fields = ("user", "quiz")
    ordering = ("-submitted_at",)

    @admin.display(description="Score", ordering="score")
    def score_badge(self, obj):
        if obj.score >= 80:
            tone = "emerald"
        elif obj.score >= 50:
            tone = "amber"
        else:
            tone = "rose"
        return tone_badge(f"{obj.score}%", tone)


@admin.register(CourseCertificate)
class CourseCertificateAdmin(ModelAdmin):
    list_display = ("user", "course", "certificate_code", "issued_at")
    list_filter = ("issued_at", "course")
    search_fields = ("user__username", "course__name", "certificate_code")
    autocomplete_fields = ("user", "course")
    ordering = ("-issued_at",)


@admin.register(Module)
class ModuleAdmin(ModelAdmin):
    list_display = (
        "title",
        "course",
        "order",
        "content_total",
        "quiz_total",
        "module_health",
        "updated_at",
        "frontend_editor_link",
    )
    search_fields = ("title", "slug", "course__name", "description")
    autocomplete_fields = ("course",)
    list_filter = (ModuleCompletenessFilter, RelatedCourseCategoryFilter, "updated_at")
    inlines = [CourseContentInline, ModuleAccordionSectionInline]
    readonly_fields = ("frontend_editor_link", "content_shortcuts", "created_at", "updated_at")
    ordering = ("course__name", "order", "title")

    class ModuleForm(forms.ModelForm):
        class Meta:
            model = Module
            fields = "__all__"
            widgets = {
                "body_content": forms.Textarea(attrs={"class": "rte-enabled", "rows": 12}),
                "description": forms.Textarea(attrs={"rows": 4}),
            }

    form = ModuleForm

    class Media:
        js = ("js/admin_rte.js",)
        css = {"all": ("css/admin_rte.css",)}

    fieldsets = (
        ("Basic Info", {"fields": ("course", "title", "slug", "order", "frontend_editor_link")}),
        (
            "Module Body",
            {
                "fields": ("description", "body_content"),
                "description": (
                    "Use HTML. To add an interactive highlight link, use "
                    "<code>&lt;span class=\"highlight-link\" data-content-id=\"ID\"&gt;your text&lt;/span&gt;</code>."
                ),
            },
        ),
        ("Management Shortcuts", {"fields": ("content_shortcuts",)}),
        ("Audit", {"fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("course", "course__subcategory", "course__subcategory__category")
            .annotate(
                content_total=Count(
                    "course_contents",
                    filter=Q(course_contents__is_inline_reference=False),
                    distinct=True,
                ),
                quiz_total=Count("course_quizzes", distinct=True),
            )
        )

    @admin.display(description="Interactive items", ordering="content_total")
    def content_total(self, obj):
        return obj.content_total

    @admin.display(description="Quizzes", ordering="quiz_total")
    def quiz_total(self, obj):
        return obj.quiz_total

    @admin.display(description="Readiness")
    def module_health(self, obj):
        if obj.content_total and obj.quiz_total:
            return tone_badge("Ready", "emerald")
        if obj.content_total or obj.quiz_total:
            return tone_badge("In progress", "amber")
        return tone_badge("Draft", "rose")

    @admin.display(description="Interactive Content")
    def content_shortcuts(self, obj):
        if not obj.pk:
            return "Save first to manage linked content."
        changelist_url = f"{reverse('admin:content_coursecontent_changelist')}?module__id__exact={obj.id}"
        add_url = f"{reverse('admin:content_coursecontent_add')}?module={obj.id}"
        return format_html("{} {}", object_link(changelist_url, "Manage content"), object_link(add_url, "Add item"))

    @admin.display(description="Frontend editor")
    def frontend_editor_link(self, obj):
        if not obj.pk:
            return tone_badge("Save first", "amber")
        url = reverse("content:subject_editor", args=[obj.course.slug, obj.slug])
        return object_link(url, "Open editor", new_tab=True)


@admin.register(CourseContent)
class CourseContentAdmin(ModelAdmin):
    list_display = ("id", "title", "content_kind", "module", "course", "order", "preview", "created_at")
    list_select_related = ("module", "module__course")
    list_filter = ("content_type", RelatedCourseCategoryFilter, "created_at")
    filter_lookup_signature = "content.module.course.subcategory.category"
    search_fields = ("title", "text_content", "youtube_url", "module__title", "module__course__name")
    autocomplete_fields = ("module",)
    date_hierarchy = "created_at"
    list_per_page = 25
    readonly_fields = ("id", "preview", "created_at")
    ordering = ("module__course__name", "module__order", "order", "created_at")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("module", "module__course").filter(
            is_inline_reference=False
        )

    fieldsets = (
        ("Basic", {"fields": ("id", "module", "title", "content_type", "order", "created_at")}),
        ("Text Content", {"fields": ("text_content",), "classes": ("collapse",)}),
        ("Media Files", {"fields": ("image", "audio", "video"), "classes": ("collapse",)}),
        ("Video Metadata", {"fields": ("video_url", "duration_seconds"), "classes": ("collapse",)}),
        ("YouTube", {"fields": ("youtube_url",), "classes": ("collapse",)}),
        ("Preview", {"fields": ("preview",)}),
    )

    class CourseContentForm(forms.ModelForm):
        class Meta:
            model = CourseContent
            fields = "__all__"
            widgets = {
                "text_content": forms.Textarea(attrs={"class": "rte-enabled", "rows": 8}),
            }

    form = CourseContentForm

    class Media:
        js = ("js/admin_rte.js",)
        css = {"all": ("css/admin_rte.css",)}

    @admin.display(description="Course", ordering="module__course__name")
    def course(self, obj):
        return obj.module.course if obj.module_id else "Unassigned"

    @admin.display(description="Type", ordering="content_type")
    def content_kind(self, obj):
        tone_map = {
            "text": "slate",
            "image": "blue",
            "audio": "violet",
            "video": "emerald",
            "youtube": "rose",
        }
        return tone_badge(obj.get_content_type_display(), tone_map.get(obj.content_type, "slate"))

    @admin.display(description="Preview")
    def preview(self, obj):
        if obj.content_type == "image" and obj.image:
            return format_html(
                '<img src="{}" style="max-height:88px;max-width:160px;border-radius:12px;object-fit:cover;" />',
                obj.image.url,
            )
        if obj.content_type == "audio" and obj.audio:
            return format_html('<audio controls style="max-width:220px;"><source src="{}"></audio>', obj.audio.url)
        if obj.content_type == "video" and obj.video:
            return format_html(
                '<video controls style="max-height:88px;max-width:160px;border-radius:12px;"><source src="{}"></video>',
                obj.video.url,
            )
        if obj.content_type == "youtube" and obj.youtube_url:
            return object_link(obj.youtube_url, "Open video", new_tab=True)
        if obj.content_type == "text" and obj.text_content:
            preview_text = obj.text_content[:140]
            return format_html(
                '<div style="max-width:260px;overflow:hidden;font-size:12px;line-height:1.6;color:#475569;">{}</div>',
                preview_text,
            )
        return "—"


@admin.register(EmailOTP)
class EmailOTPAdmin(ModelAdmin):
    list_display = ("user", "code", "otp_state", "created_at", "expires_at")
    list_filter = (OTPStateFilter, "created_at", "expires_at")
    search_fields = ("user__username", "user__email", "code")
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)

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
    ordering = ("payment_method_name", "-created_at")

    class PaymentInstructionForm(forms.ModelForm):
        class Meta:
            model = PaymentInstruction
            fields = "__all__"
            widgets = {
                "details": forms.Textarea(attrs={"class": "rte-enabled", "rows": 8}),
            }

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

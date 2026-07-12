from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db.models import Count, Q
from django.utils import timezone
from unfold.admin import ModelAdmin

from apps.authentication.models import OTP, UserRole
from content.admin import tone_badge


User = get_user_model()


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
        "phone_number",
        "full_name",
        "profile_role",
        "is_staff",
        "is_active",
        "last_login",
        "date_joined",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "date_joined")
    search_fields = ("email", "phone_number", "full_name")
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


@admin.register(OTP)
class OtpAdmin(ModelAdmin):
    list_display = ("user", "code", "channel", "otp_state", "created_at", "expires_at")
    list_filter = ("channel", OTPStateFilter, "created_at", "expires_at")
    search_fields = ("user__email", "user__phone_number", "code")
    autocomplete_fields = ("user",)

    @admin.display(description="State")
    def otp_state(self, obj):
        if obj.is_used:
            return tone_badge("Used", "emerald")
        if obj.expires_at <= timezone.now():
            return tone_badge("Expired", "rose")
        return tone_badge("Available", "amber")

from django import forms
from django.contrib import admin

from content.models import Category, UserRole
from unfold.admin import ModelAdmin

from .models import TeacherProfile


class TeacherProfileForm(forms.ModelForm):
    class Meta:
        model = TeacherProfile
        fields = (
            "user",
            "full_name",
            "phone_number",
            "profile_picture",
            "teacher_institution",
            "teacher_subject",
            "teacher_experience_years",
            "assigned_categories",
        )
        widgets = {
            "teacher_institution": forms.TextInput(attrs={"class": "w-full"}),
            "teacher_subject": forms.TextInput(attrs={"class": "w-full"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_categories"].queryset = Category.objects.order_by("name")

    def clean(self):
        cleaned = super().clean()
        if self.instance and self.instance.pk and self.instance.role != UserRole.TEACHER:
            self.add_error(None, "This profile is not a teacher profile.")
        return cleaned


@admin.register(TeacherProfile)
class TeacherProfileAdmin(ModelAdmin):
    form = TeacherProfileForm
    list_display = ("user", "full_name", "category_total", "assigned_category_list", "updated_at")
    search_fields = ("user__username", "user__email", "full_name", "teacher_subject", "teacher_institution")
    list_filter = ("assigned_categories", "created_at", "updated_at")
    autocomplete_fields = ("user", "assigned_categories")

    fieldsets = (
        ("Teacher", {"fields": ("user", "full_name", "phone_number", "profile_picture")}),
        ("Professional Info", {"fields": ("teacher_institution", "teacher_subject", "teacher_experience_years")}),
        ("Access", {"fields": ("assigned_categories",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user").prefetch_related("assigned_categories").filter(role=UserRole.TEACHER)

    @admin.display(description="Categories")
    def category_total(self, obj):
        return obj.assigned_categories.count()

    @admin.display(description="Assigned categories")
    def assigned_category_list(self, obj):
        categories = list(obj.assigned_categories.order_by("name").values_list("name", flat=True))
        return ", ".join(categories) if categories else "—"

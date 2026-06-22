from django import forms
from django.contrib import admin

from content.models import UserRole
from unfold.admin import ModelAdmin

from .models import StudentProfile


class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = (
            "user",
            "full_name",
            "phone_number",
            "profile_picture",
            "student_institution",
            "student_level",
        )
        widgets = {
            "student_institution": forms.TextInput(attrs={"class": "w-full"}),
            "student_level": forms.TextInput(attrs={"class": "w-full"}),
        }

    def clean(self):
        cleaned = super().clean()
        if self.instance and self.instance.pk and self.instance.role != UserRole.STUDENT:
            self.add_error(None, "This profile is not a student profile.")
        return cleaned


@admin.register(StudentProfile)
class StudentProfileAdmin(ModelAdmin):
    form = StudentProfileForm
    list_display = ("user", "full_name", "student_institution", "student_level")
    search_fields = ("user__email", "full_name", "student_institution", "student_level")
    autocomplete_fields = ("user",)

    fieldsets = (
        ("Student", {"fields": ("user", "full_name", "phone_number", "profile_picture")}),
        ("Academic Info", {"fields": ("student_institution", "student_level")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")

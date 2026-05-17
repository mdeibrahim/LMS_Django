from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
import re

from .models import UserProfile, UserRole

User = get_user_model()


class EmailLoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)


class BaseRoleSignupForm(UserCreationForm):
    email = forms.EmailField(required=True)
    full_name = forms.CharField(max_length=160, required=True)
    phone_number = forms.CharField(max_length=20, required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('email', 'full_name', 'phone_number', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('This email is already in use.')
        return email

    def _build_unique_username(self, email):
        local = email.split('@', 1)[0]
        base = re.sub(r'[^a-zA-Z0-9_]+', '_', local).strip('_').lower() or 'user'
        candidate = base
        idx = 1
        while User.objects.filter(username=candidate).exists():
            idx += 1
            candidate = f"{base}{idx}"
        return candidate

    def clean_full_name(self):
        full_name = self.cleaned_data.get('full_name', '').strip()
        if len(full_name) < 3:
            raise forms.ValidationError('Please provide your full name.')
        return full_name

    def clean_phone_number(self):
        raw_phone = self.cleaned_data.get('phone_number', '').strip()
        if not raw_phone:
            raise forms.ValidationError('Phone number is required.')

        normalized = raw_phone.replace(' ', '').replace('-', '')
        if normalized.startswith('+'):
            digits = normalized[1:]
        else:
            digits = normalized

        if not digits.isdigit():
            raise forms.ValidationError('Use only digits, optional +, space or hyphen.')
        if len(digits) < 10 or len(digits) > 15:
            raise forms.ValidationError('Phone number must be 10 to 15 digits.')
        return normalized

    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data['email']
        user.email = email
        user.username = self._build_unique_username(email)
        if commit:
            user.save()
        return user

    def save_profile(self, user, role):
        raise NotImplementedError


class StudentSignupForm(BaseRoleSignupForm):
    student_institution = forms.CharField(max_length=180, required=True)
    student_level = forms.CharField(max_length=80, required=True, label='Class / Level')

    class Meta(BaseRoleSignupForm.Meta):
        fields = BaseRoleSignupForm.Meta.fields + ('student_institution', 'student_level')

    def save_profile(self, user, role):
        UserProfile.objects.update_or_create(
            user=user,
            defaults={
                'role': role,
                'full_name': self.cleaned_data['full_name'].strip(),
                'phone_number': self.cleaned_data['phone_number'],
                'student_institution': self.cleaned_data['student_institution'].strip(),
                'student_level': self.cleaned_data['student_level'].strip(),
            },
        )


class NewCourseAddRequestForm(forms.Form):
    requested_category = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={'class': 'w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5', 'placeholder': 'Category name'}),
    )
    requested_course_name = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={'class': 'w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5'}),
    )
    requested_price = forms.DecimalField(
        required=True,
        min_value=0,
        decimal_places=2,
        max_digits=10,
        widget=forms.NumberInput(attrs={'step': '0.01', 'class': 'w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5'}),
    )
    details = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 4, 'class': 'w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5'}),
    )


class ProfileUpdateForm(forms.Form):
    email = forms.EmailField(required=True)
    full_name = forms.CharField(max_length=160, required=True)
    phone_number = forms.CharField(max_length=20, required=True)
    profile_picture = forms.ImageField(required=False)

    student_institution = forms.CharField(max_length=180, required=False)
    student_level = forms.CharField(max_length=80, required=False, label='Class / Level')

    def __init__(self, *args, user=None, profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.profile = profile

        if not self.is_bound and user and profile:
            self.initial.update({
                'email': user.email,
                'full_name': profile.full_name,
                'phone_number': profile.phone_number,
                'profile_picture': profile.profile_picture,
                'student_institution': profile.student_institution,
                'student_level': profile.student_level,
            })

        is_student = not profile or profile.role == UserRole.STUDENT
        self.fields['student_institution'].required = is_student
        self.fields['student_level'].required = is_student

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        qs = User.objects.filter(email__iexact=email)
        if self.user:
            qs = qs.exclude(id=self.user.id)
        if qs.exists():
            raise forms.ValidationError('This email is already in use.')
        return email

    def clean_full_name(self):
        full_name = self.cleaned_data.get('full_name', '').strip()
        if len(full_name) < 3:
            raise forms.ValidationError('Please provide your full name.')
        return full_name

    def clean_phone_number(self):
        raw_phone = self.cleaned_data.get('phone_number', '').strip()
        normalized = raw_phone.replace(' ', '').replace('-', '')
        if normalized.startswith('+'):
            digits = normalized[1:]
        else:
            digits = normalized
        if not digits.isdigit():
            raise forms.ValidationError('Use only digits, optional +, space or hyphen.')
        if len(digits) < 10 or len(digits) > 15:
            raise forms.ValidationError('Phone number must be 10 to 15 digits.')
        return normalized

    def clean(self):
        cleaned = super().clean()
        if self.profile and self.profile.role == UserRole.STUDENT:
            if not (cleaned.get('student_institution') or '').strip():
                self.add_error('student_institution', 'This field is required for students.')
            if not (cleaned.get('student_level') or '').strip():
                self.add_error('student_level', 'This field is required for students.')
        return cleaned

    def save(self):
        user = self.user
        profile = self.profile

        user.email = self.cleaned_data['email']
        user.save(update_fields=['email'])

        profile.full_name = self.cleaned_data['full_name'].strip()
        profile.phone_number = self.cleaned_data['phone_number']

        uploaded_picture = self.cleaned_data.get('profile_picture')
        if uploaded_picture:
            profile.profile_picture = uploaded_picture

        if profile.role == UserRole.STUDENT:
            profile.student_institution = self.cleaned_data['student_institution'].strip()
            profile.student_level = self.cleaned_data['student_level'].strip()

        profile.save()
        return profile


class OTPForm(forms.Form):
    code = forms.CharField(max_length=8, required=True, widget=forms.TextInput(attrs={'class': 'w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5'}))

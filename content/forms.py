from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import UserRole

User = get_user_model()


class EmailLoginForm(forms.Form):
    email = forms.CharField(label="Email or phone")
    password = forms.CharField(widget=forms.PasswordInput)


class BaseRoleSignupForm(UserCreationForm):
    email = forms.EmailField(required=False)
    full_name = forms.CharField(max_length=160, required=True)
    phone_number = forms.CharField(max_length=20, required=False)
    email_or_phone = forms.CharField(
        max_length=160, required=True,
        label='Email or Phone',
        help_text='Enter your email address or phone number.',
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('email', 'full_name', 'phone_number', 'password1', 'password2')

    def _looks_like_phone(self, value):
        """Return True if value looks like a phone number rather than an email."""
        stripped = value.replace(' ', '').replace('-', '')
        if '@' in stripped:
            return False
        if stripped.startswith('+'):
            return stripped[1:].isdigit()
        return stripped.isdigit() and len(stripped) >= 10

    def clean_email_or_phone(self):
        raw = (self.cleaned_data.get('email_or_phone') or '').strip()
        if not raw:
            raise forms.ValidationError('Email or phone number is required.')
        return raw

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('This email is already in use.')
        return email

    def clean_full_name(self):
        full_name = self.cleaned_data.get('full_name', '').strip()
        if len(full_name) < 3:
            raise forms.ValidationError('Please provide your full name.')
        return full_name

    def clean_phone_number(self):
        raw_phone = (self.cleaned_data.get('phone_number') or '').strip()
        if not raw_phone:
            return ''

        normalized = raw_phone.replace(' ', '').replace('-', '')
        if normalized.startswith('+'):
            digits = normalized[1:]
        else:
            digits = normalized

        if not digits.isdigit():
            raise forms.ValidationError('Use only digits, optional +, space or hyphen.')
        if len(digits) < 10 or len(digits) > 15:
            raise forms.ValidationError('Phone number must be 10 to 15 digits.')
        if User.objects.filter(phone_number=normalized).exists():
            raise forms.ValidationError('This phone number is already in use.')
        return normalized

    def clean(self):
        cleaned = super().clean()
        raw_input = (cleaned.get('email_or_phone') or '').strip()

        if raw_input:
            if self._looks_like_phone(raw_input):
                # Route to phone_number field and run its validation
                cleaned['phone_number'] = raw_input
                cleaned['email'] = ''
                # Validate the phone inline
                normalized = raw_input.replace(' ', '').replace('-', '')
                if normalized.startswith('+'):
                    digits = normalized[1:]
                else:
                    digits = normalized
                if not digits.isdigit():
                    self.add_error('email_or_phone', 'Use only digits, optional +, space or hyphen.')
                elif len(digits) < 10 or len(digits) > 15:
                    self.add_error('email_or_phone', 'Phone number must be 10 to 15 digits.')
                elif User.objects.filter(phone_number=normalized).exists():
                    self.add_error('email_or_phone', 'This phone number is already in use.')
                else:
                    cleaned['phone_number'] = normalized
            else:
                # Route to email field
                cleaned['email'] = raw_input.lower()
                cleaned['phone_number'] = ''
                # Validate email format
                try:
                    forms.EmailField().clean(raw_input)
                except forms.ValidationError:
                    self.add_error('email_or_phone', 'Enter a valid email address or phone number.')
                else:
                    if User.objects.filter(email__iexact=raw_input).exists():
                        self.add_error('email_or_phone', 'This email is already in use.')

        if not (cleaned.get('email') or cleaned.get('phone_number')):
            if not self.has_error('email_or_phone'):
                raise forms.ValidationError('Provide an email address or a phone number.')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data.get('email') or None
        user.phone_number = self.cleaned_data.get('phone_number') or ""
        if commit:
            user.save()
        return user

    def save_profile(self, user, role):
        raise NotImplementedError


class StudentSignupForm(BaseRoleSignupForm):
    student_institution = forms.CharField(max_length=180, required=False)
    student_level = forms.CharField(max_length=80, required=False, label='Class / Level')

    class Meta(BaseRoleSignupForm.Meta):
        fields = BaseRoleSignupForm.Meta.fields + ('student_institution', 'student_level')

    def save_profile(self, user, role):
        from apps.student_dashboard.models import StudentProfile

        user.role = UserRole.STUDENT
        user.full_name = self.cleaned_data['full_name'].strip()
        user.phone_number = self.cleaned_data.get('phone_number') or ""
        user.save(update_fields=['role', 'full_name', 'phone_number'])

        StudentProfile.objects.update_or_create(
            user=user,
            defaults={
                'full_name': self.cleaned_data['full_name'].strip(),
                'phone_number': self.cleaned_data.get('phone_number') or '',
                'student_institution': (self.cleaned_data.get('student_institution') or '').strip(),
                'student_level': (self.cleaned_data.get('student_level') or '').strip(),
            },
        )


# class NewCourseAddRequestForm(forms.Form):
#     requested_category = forms.CharField(
#         max_length=255,
#         required=True,
#         widget=forms.TextInput(attrs={'class': 'w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5', 'placeholder': 'Category name'}),
#     )
#     requested_course_name = forms.CharField(
#         max_length=255,
#         required=True,
#         widget=forms.TextInput(attrs={'class': 'w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5'}),
#     )
#     requested_price = forms.DecimalField(
#         required=True,
#         min_value=0,
#         decimal_places=2,
#         max_digits=10,
#         widget=forms.NumberInput(attrs={'step': '0.01', 'class': 'w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5'}),
#     )
#     details = forms.CharField(
#         required=False,
#         widget=forms.Textarea(attrs={'rows': 4, 'class': 'w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5'}),
#     )


class ProfileUpdateForm(forms.Form):
    email = forms.EmailField(required=False)
    full_name = forms.CharField(max_length=160, required=True)
    phone_number = forms.CharField(max_length=20, required=False)
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
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if not email:
            return ''
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
        raw_phone = (self.cleaned_data.get('phone_number') or '').strip()
        if not raw_phone:
            return ''
        normalized = raw_phone.replace(' ', '').replace('-', '')
        if normalized.startswith('+'):
            digits = normalized[1:]
        else:
            digits = normalized
        if not digits.isdigit():
            raise forms.ValidationError('Use only digits, optional +, space or hyphen.')
        if len(digits) < 10 or len(digits) > 15:
            raise forms.ValidationError('Phone number must be 10 to 15 digits.')
        qs = User.objects.filter(phone_number=normalized)
        if self.user:
            qs = qs.exclude(id=self.user.id)
        if qs.exists():
            raise forms.ValidationError('This phone number is already in use.')
        return normalized

    def clean(self):
        cleaned = super().clean()
        if not (cleaned.get('email') or cleaned.get('phone_number')):
            raise forms.ValidationError('Provide at least an email address or a phone number.')
        if self.profile and self.profile.role == UserRole.STUDENT:
            if not (cleaned.get('student_institution') or '').strip():
                self.add_error('student_institution', 'This field is required for students.')
            if not (cleaned.get('student_level') or '').strip():
                self.add_error('student_level', 'This field is required for students.')
        return cleaned

    def save(self):
        user = self.user
        profile = self.profile

        user.email = self.cleaned_data.get('email') or None
        user.phone_number = self.cleaned_data.get('phone_number') or ""
        user.full_name = self.cleaned_data['full_name'].strip()
        user.save(update_fields=['email', 'phone_number', 'full_name'])

        profile.full_name = self.cleaned_data['full_name'].strip()
        profile.phone_number = self.cleaned_data.get('phone_number') or ''

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

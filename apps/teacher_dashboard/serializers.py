from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers
from apps.teacher_dashboard.models import TeacherProfile
from content.models import UserRole


User = get_user_model()

class TeacherRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    full_name = serializers.CharField()
    phone_number = serializers.CharField(required=True)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email is already in use")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match"}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_password")

        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            full_name=validated_data["full_name"],
            phone_number=validated_data["phone_number"],
            role=UserRole.TEACHER,
        )

        return user
    

class TeacherLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get("email")
        password = data.get("password")

        user = authenticate(email=email, password=password)

        if not user:
            raise serializers.ValidationError(
                {"detail": "Invalid email or password"}
            )

        try:
            profile_role = user.profile.role
        except Exception:
            profile_role = None
        if profile_role != UserRole.TEACHER and not user.is_staff:
            raise serializers.ValidationError(
                {"detail": "Teacher account required"}
            )

        if not user.is_active:
            raise serializers.ValidationError(
                {"detail": "Account is inactive"}
            )

        data["user"] = user
        return data


class TeacherProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = TeacherProfile
        fields = (
            "full_name",
            "email",
            "phone_number",
            "profile_picture",
            "teacher_institution",
            "teacher_subject",
            "teacher_experience_years",
        )
        read_only_fields = ("email",)

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        email = user_data.get("email")

        if email and email != instance.user.email:
            if User.objects.filter(email=email).exists():
                raise serializers.ValidationError({"email": "Email is already in use"})
            instance.user.email = email
            instance.user.save(update_fields=["email"])

        return super().update(instance, validated_data)
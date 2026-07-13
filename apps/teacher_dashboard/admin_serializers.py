from rest_framework import serializers

from apps.authentication.models import OTP, User
from apps.student_dashboard.models import StudentDeviceSession, StudentProfile
from apps.teacher_dashboard.models import TeacherProfile
from content.models import (
    Course,
    CourseCertificate,
    CourseEnrollment,
    PaymentInstruction,
    PaymentSubmission,
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "phone_number",
            "role",
            "is_active",
            "is_staff",
            "is_verified",
            "date_joined",
        )
        read_only_fields = fields


class UserNestedSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    full_name = serializers.CharField()


class CourseNestedSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class AdminTeacherProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = TeacherProfile
        fields = (
            "id",
            "user",
            "profile_picture",
            "full_name",
            "phone_number",
            "address",
            "bio",
            "teacher_institution",
            "teacher_subject",
            "teacher_experience_years",
            "created_at",
        )
        read_only_fields = fields


class AdminStudentProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = StudentProfile
        fields = (
            "id",
            "user",
            "profile_picture",
            "full_name",
            "phone_number",
            "student_institution",
            "student_level",
            "created_at",
        )
        read_only_fields = fields


class AdminDeviceSessionUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    full_name = serializers.CharField()


class AdminDeviceSessionSerializer(serializers.ModelSerializer):
    user = AdminDeviceSessionUserSerializer(read_only=True)

    class Meta:
        model = StudentDeviceSession
        fields = (
            "id",
            "user",
            "jti",
            "user_agent",
            "ip_address",
            "created_at",
            "last_seen",
            "expires_at",
        )
        read_only_fields = fields


class AdminOTPSerializer(serializers.ModelSerializer):
    user = UserNestedSerializer(read_only=True)

    class Meta:
        model = OTP
        fields = (
            "id",
            "user",
            "code",
            "channel",
            "is_used",
            "created_at",
            "expires_at",
        )
        read_only_fields = fields


class AdminPaymentSubmissionCourseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class AdminPaymentSubmissionReviewerSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()


class AdminPaymentSubmissionSerializer(serializers.ModelSerializer):
    user = UserNestedSerializer(read_only=True)
    course = AdminPaymentSubmissionCourseSerializer(read_only=True)
    reviewed_by = AdminPaymentSubmissionReviewerSerializer(read_only=True)

    class Meta:
        model = PaymentSubmission
        fields = (
            "id",
            "user",
            "course",
            "payment_method",
            "transaction_id",
            "bkash_phone_number",
            "note",
            "status",
            "reviewed_by",
            "reviewed_at",
            "rejection_reason",
            "submitted_at",
            "updated_at",
        )
        read_only_fields = fields


class AdminEnrollmentCourseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()


class AdminEnrollmentGrantedBySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()


class AdminEnrollmentSerializer(serializers.ModelSerializer):
    user = UserNestedSerializer(read_only=True)
    course = AdminEnrollmentCourseSerializer(read_only=True)
    granted_by = AdminEnrollmentGrantedBySerializer(read_only=True)

    class Meta:
        model = CourseEnrollment
        fields = (
            "id",
            "user",
            "course",
            "status",
            "granted_by",
            "granted_at",
            "updated_at",
        )
        read_only_fields = fields


class AdminCertificateSerializer(serializers.ModelSerializer):
    user = UserNestedSerializer(read_only=True)
    course = CourseNestedSerializer(read_only=True)

    class Meta:
        model = CourseCertificate
        fields = (
            "id",
            "user",
            "course",
            "certificate_code",
            "issued_at",
        )
        read_only_fields = fields


class AdminPaymentInstructionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentInstruction
        fields = (
            "id",
            "payment_method_name",
            "details",
            "image",
            "created_at",
        )
        read_only_fields = fields

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from apps.authentication.models import OTP, User
from apps.student_dashboard.models import StudentDeviceSession, StudentProfile
from apps.teacher_dashboard.models import TeacherProfile
from content.models import (
    Course,
    CourseCertificate,
    CourseEnrollment,
    PaymentInstruction,
    PaymentSubmission,
    PaymentSubmissionStatus,
)
from .admin_serializers import (
    AdminCertificateSerializer,
    AdminDeviceSessionSerializer,
    AdminEnrollmentSerializer,
    AdminOTPSerializer,
    AdminPaymentInstructionSerializer,
    AdminPaymentSubmissionSerializer,
    AdminStudentProfileSerializer,
    AdminTeacherProfileSerializer,
    UserSerializer,
)


def _forbidden_response():
    return Response(
        {"message": "Admin access required."},
        status=status.HTTP_403_FORBIDDEN,
    )


def _paginate(request, queryset):
    try:
        page = int(request.query_params.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    if page < 1:
        page = 1

    try:
        limit = int(request.query_params.get("limit", 20))
    except (TypeError, ValueError):
        limit = 20
    if limit < 1:
        limit = 20

    total = queryset.count()
    start = (page - 1) * limit
    end = start + limit
    items = queryset[start:end]
    return items, total, page, limit


class AdminUserListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return _forbidden_response()

        queryset = User.objects.all()

        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(email__icontains=search)
                | Q(full_name__icontains=search)
                | Q(phone_number__icontains=search)
            )

        role = request.query_params.get("role")
        if role:
            queryset = queryset.filter(role=role)

        is_staff = request.query_params.get("is_staff")
        if is_staff is not None:
            is_staff_value = is_staff.lower() == "true"
            queryset = queryset.filter(is_staff=is_staff_value)

        queryset = queryset.order_by("-date_joined")

        items, total, page, limit = _paginate(request, queryset)
        serializer = UserSerializer(items, many=True)

        return Response(
            {
                "message": "User list retrieved successfully",
                "data": serializer.data,
                "pagination": {
                    "total": total,
                    "page": page,
                    "limit": limit,
                    "pages": (total + limit - 1) // limit if limit else 1,
                },
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        if not request.user.is_staff:
            return _forbidden_response()

        email = request.data.get("email")
        password = request.data.get("password")
        full_name = request.data.get("full_name", "")
        phone_number = request.data.get("phone_number", "")
        role = request.data.get("role", "student")
        is_staff = bool(request.data.get("is_staff", False))
        is_active = bool(request.data.get("is_active", True))

        if not email and not phone_number:
            return Response(
                {"message": "Either email or phone_number is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not password:
            return Response(
                {"message": "Password is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if email and User.objects.filter(email=email.lower()).exists():
            return Response(
                {"message": "Email is already in use."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if phone_number and User.objects.filter(phone_number=phone_number).exists():
            return Response(
                {"message": "Phone number is already in use."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.create_user(
            email=email,
            password=password,
            full_name=full_name,
            phone_number=phone_number,
            role=role,
            is_staff=is_staff,
            is_active=is_active,
        )

        if role == "teacher":
            TeacherProfile.objects.get_or_create(user=user)
        elif role == "student":
            StudentProfile.objects.get_or_create(user=user)

        serializer = UserSerializer(user)

        return Response(
            {
                "message": "User created successfully",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class AdminUserDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not request.user.is_staff:
            return _forbidden_response()

        user = get_object_or_404(User, pk=pk)
        serializer = UserSerializer(user)

        return Response(
            {
                "message": "User retrieved successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request, pk):
        if not request.user.is_staff:
            return _forbidden_response()

        user = get_object_or_404(User, pk=pk)

        email = request.data.get("email")
        if email is not None:
            email = email.lower()
            if User.objects.filter(email=email).exclude(pk=user.pk).exists():
                return Response(
                    {"message": "Email is already in use."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.email = email

        full_name = request.data.get("full_name")
        if full_name is not None:
            user.full_name = full_name

        phone_number = request.data.get("phone_number")
        if phone_number is not None:
            if phone_number and User.objects.filter(phone_number=phone_number).exclude(pk=user.pk).exists():
                return Response(
                    {"message": "Phone number is already in use."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.phone_number = phone_number

        role = request.data.get("role")
        if role is not None:
            user.role = role

        is_staff = request.data.get("is_staff")
        if is_staff is not None:
            user.is_staff = bool(is_staff)

        is_active = request.data.get("is_active")
        if is_active is not None:
            user.is_active = bool(is_active)

        password = request.data.get("password")
        if password:
            user.set_password(password)

        user.save()

        serializer = UserSerializer(user)

        return Response(
            {
                "message": "User updated successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        if not request.user.is_staff:
            return _forbidden_response()

        user = get_object_or_404(User, pk=pk)

        if user.pk == request.user.pk:
            return Response(
                {"message": "You cannot delete your own account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.is_active = False
        user.save(update_fields=["is_active"])

        return Response(
            {
                "message": "User deleted successfully",
            },
            status=status.HTTP_200_OK,
        )


class AdminTeacherListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return _forbidden_response()

        queryset = TeacherProfile.objects.select_related("user").all()
        serializer = AdminTeacherProfileSerializer(queryset, many=True)

        return Response(
            {
                "message": "Teacher list retrieved successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class AdminStudentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return _forbidden_response()

        queryset = StudentProfile.objects.select_related("user").all()
        serializer = AdminStudentProfileSerializer(queryset, many=True)

        return Response(
            {
                "message": "Student list retrieved successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class AdminDeviceSessionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return _forbidden_response()

        queryset = StudentDeviceSession.objects.select_related("user").all()

        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(user__email__icontains=search)
                | Q(user__full_name__icontains=search)
                | Q(jti__icontains=search)
                | Q(ip_address__icontains=search)
            )

        items, total, page, limit = _paginate(request, queryset)
        serializer = AdminDeviceSessionSerializer(items, many=True)

        return Response(
            {
                "message": "Device session list retrieved successfully",
                "data": serializer.data,
                "pagination": {
                    "total": total,
                    "page": page,
                    "limit": limit,
                    "pages": (total + limit - 1) // limit if limit else 1,
                },
            },
            status=status.HTTP_200_OK,
        )


class AdminOTPListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return _forbidden_response()

        queryset = OTP.objects.select_related("user").all()

        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(user__email__icontains=search)
                | Q(user__full_name__icontains=search)
                | Q(code__icontains=search)
            )

        channel = request.query_params.get("channel")
        if channel:
            queryset = queryset.filter(channel=channel)

        is_used = request.query_params.get("is_used")
        if is_used is not None:
            is_used_value = is_used.lower() == "true"
            queryset = queryset.filter(is_used=is_used_value)

        queryset = queryset.order_by("-created_at")

        items, total, page, limit = _paginate(request, queryset)
        serializer = AdminOTPSerializer(items, many=True)

        return Response(
            {
                "message": "OTP list retrieved successfully",
                "data": serializer.data,
                "pagination": {
                    "total": total,
                    "page": page,
                    "limit": limit,
                    "pages": (total + limit - 1) // limit if limit else 1,
                },
            },
            status=status.HTTP_200_OK,
        )


class AdminPaymentSubmissionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return _forbidden_response()

        queryset = PaymentSubmission.objects.select_related(
            "user", "course", "reviewed_by"
        ).all()

        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        user_id = request.query_params.get("user_id")
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        course_id = request.query_params.get("course_id")
        if course_id:
            queryset = queryset.filter(course_id=course_id)

        queryset = queryset.order_by("-submitted_at")

        items, total, page, limit = _paginate(request, queryset)
        serializer = AdminPaymentSubmissionSerializer(items, many=True)

        return Response(
            {
                "message": "Payment submission list retrieved successfully",
                "data": serializer.data,
                "pagination": {
                    "total": total,
                    "page": page,
                    "limit": limit,
                    "pages": (total + limit - 1) // limit if limit else 1,
                },
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request, pk):
        if not request.user.is_staff:
            return _forbidden_response()

        submission = get_object_or_404(PaymentSubmission, pk=pk)

        new_status = request.data.get("status")
        if new_status not in (
            PaymentSubmissionStatus.PENDING,
            PaymentSubmissionStatus.APPROVED,
            PaymentSubmissionStatus.REJECTED,
        ):
            return Response(
                {"message": "Valid status (pending/approved/rejected) is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rejection_reason = request.data.get("rejection_reason", "")
        if new_status == PaymentSubmissionStatus.REJECTED and not rejection_reason:
            return Response(
                {"message": "Rejection reason is required when rejecting."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_status == PaymentSubmissionStatus.PENDING:
            submission.status = PaymentSubmissionStatus.PENDING
            submission.reviewed_by = None
            submission.reviewed_at = None
            submission.rejection_reason = ""
        else:
            submission.status = new_status
            submission.reviewed_by = request.user
            submission.reviewed_at = timezone.now()
            if new_status == PaymentSubmissionStatus.REJECTED:
                submission.rejection_reason = rejection_reason
            else:
                submission.rejection_reason = ""

        submission.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "rejection_reason",
            ]
        )

        serializer = AdminPaymentSubmissionSerializer(submission)

        return Response(
            {
                "message": f"Payment submission {new_status} successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class AdminEnrollmentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return _forbidden_response()

        queryset = CourseEnrollment.objects.select_related(
            "user", "course", "granted_by"
        ).all()

        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        user_id = request.query_params.get("user_id")
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        course_id = request.query_params.get("course_id")
        if course_id:
            queryset = queryset.filter(course_id=course_id)

        items, total, page, limit = _paginate(request, queryset)
        serializer = AdminEnrollmentSerializer(items, many=True)

        return Response(
            {
                "message": "Enrollment list retrieved successfully",
                "data": serializer.data,
                "pagination": {
                    "total": total,
                    "page": page,
                    "limit": limit,
                    "pages": (total + limit - 1) // limit if limit else 1,
                },
            },
            status=status.HTTP_200_OK,
        )


class AdminCertificateListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return _forbidden_response()

        queryset = CourseCertificate.objects.select_related("user", "course").all()

        user_id = request.query_params.get("user_id")
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        course_id = request.query_params.get("course_id")
        if course_id:
            queryset = queryset.filter(course_id=course_id)

        items, total, page, limit = _paginate(request, queryset)
        serializer = AdminCertificateSerializer(items, many=True)

        return Response(
            {
                "message": "Certificate list retrieved successfully",
                "data": serializer.data,
                "pagination": {
                    "total": total,
                    "page": page,
                    "limit": limit,
                    "pages": (total + limit - 1) // limit if limit else 1,
                },
            },
            status=status.HTTP_200_OK,
        )


class AdminPaymentInstructionListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return _forbidden_response()

        queryset = PaymentInstruction.objects.all().order_by(
            "payment_method_name", "-created_at"
        )
        serializer = AdminPaymentInstructionSerializer(queryset, many=True)

        return Response(
            {
                "message": "Payment instruction list retrieved successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        if not request.user.is_staff:
            return _forbidden_response()

        payment_method_name = request.data.get("payment_method_name")
        details = request.data.get("details", "")
        image = request.FILES.get("image") if hasattr(request, "FILES") else None

        if not payment_method_name:
            return Response(
                {"message": "payment_method_name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instruction = PaymentInstruction.objects.create(
            payment_method_name=payment_method_name,
            details=details,
        )
        if image:
            instruction.image = image
            instruction.save(update_fields=["image"])

        serializer = AdminPaymentInstructionSerializer(instruction)

        return Response(
            {
                "message": "Payment instruction created successfully",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class AdminPaymentInstructionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        if not request.user.is_staff:
            return _forbidden_response()

        instruction = get_object_or_404(PaymentInstruction, pk=pk)

        payment_method_name = request.data.get("payment_method_name")
        if payment_method_name is not None:
            instruction.payment_method_name = payment_method_name

        details = request.data.get("details")
        if details is not None:
            instruction.details = details

        image = request.FILES.get("image") if hasattr(request, "FILES") else None
        if image:
            instruction.image = image

        instruction.save()

        serializer = AdminPaymentInstructionSerializer(instruction)

        return Response(
            {
                "message": "Payment instruction updated successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        if not request.user.is_staff:
            return _forbidden_response()

        instruction = get_object_or_404(PaymentInstruction, pk=pk)
        instruction.delete()

        return Response(
            {
                "message": "Payment instruction deleted successfully",
            },
            status=status.HTTP_200_OK,
        )

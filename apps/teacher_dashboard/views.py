from datetime import timedelta
import random

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from apps.teacher_dashboard.utils import send_verification_email, forgot_password_email
from content import models
from content.models import Course, Module, Lesson, LessonResource, EmailOTP, PasswordResetSession, CourseQuiz
from .models import Category
from .serializers import (
    CategorySubcategorySerializer,
    CourseSerializer,
    LessonCreateSerializer,
    LessonSerializer,
    ModuleSerializer,
    SubcategorySerializer,
    TeacherLoginSerializer,
    TeacherProfileSerializer,
    TeacherRegisterSerializer,
    CourseQuizListSerializer,
    CourseQuizCreateSerializer,
    CourseQuizQuestionCreateSerializer,
)

def generate_otp(user):
    EmailOTP.objects.filter(user=user).delete()
    code = f"{random.randint(100000, 999999)}"
    expires = timezone.now() + timedelta(minutes=15)
    is_used = False
    EmailOTP.objects.create(user=user, code=code, expires_at=expires, is_used=is_used)
    return code

class RegisterView(APIView):
    def post(self, request):
        serializer = TeacherRegisterSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()

            code = generate_otp(user)

            sent = send_verification_email(user, code)
            if not sent:
                return Response(
                    {"message": "Failed to send verification email."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            

            return Response(
                {"message": "OTP sent to your email. Please verify to complete registration."},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class VerifyOTPView(APIView):
    def post(self, request):
        email = request.data.get("email")
        otp = request.data.get("otp")
        type = request.data.get("type", "register")

        if not email or not otp:
            return Response(
                {"message": "Email and OTP are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = models.User.objects.get(email=email)
        except models.User.DoesNotExist:
            return Response(
                {"message": "User with this email does not exist."},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            otp_record = EmailOTP.objects.get(user=user, code=otp, is_used=False, expires_at__gt=timezone.now())
        except EmailOTP.DoesNotExist:
            print(f"otp_record: {otp_record}")
            return Response(
                {"message": "Invalid OTP."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Mark the user as verified
        user.is_verified = True
        user.is_active = True  
        user.save(update_fields=["is_verified", "is_active"])

        # Mark the OTP as used
        otp_record.is_used = True
        otp_record.save(update_fields=["is_used"])

        session = None
        if type != "register":
            session = PasswordResetSession.objects.create(
                user=user,
                expires_at=timezone.now() + timedelta(minutes=15)
            )
            reset_token = str(session.token)
        else:
            reset_token = None

        response_data = {"message": "OTP verified successfully."}
        if reset_token:
            response_data["reset_token"] = reset_token

        return Response(
            response_data,
            status=status.HTTP_200_OK
        )
    

class ResendOTPView(APIView):
    def post(self, request):
        email = request.data.get("email")
        type = request.data.get("type", "register") 

        if not email:
            return Response(
                {"message": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = models.User.objects.get(email=email)
        except models.User.DoesNotExist:
            return Response(
                {"message": "User with this email does not exist."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Generate a new OTP
        code = generate_otp(user)

        if user.is_verified:
            return Response(
                {"message": "User is already verified."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if type == "register":
            sent = send_verification_email(user, code)
        else:
            sent = forgot_password_email(user, code)
        
        if not sent:
            return Response(
                {"message": "Failed to send verification email."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {"message": "A new OTP has been sent to your email."},
            status=status.HTTP_200_OK
        )
    

class LoginView(APIView):
    def post(self, request):
        serializer = TeacherLoginSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.validated_data["user"]

            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "message": "Teacher login successful",
                    "refresh_token": str(refresh),
                    "access_token": str(refresh.access_token),
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "name": user.get_full_name(),
                        "profile_picture": user.profile.profile_picture.url if user.profile.profile_picture else None,
                    }
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
    

class TeacherProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = getattr(user, "teacher_profile", None)

        if not profile:
            return Response(
                {"message": "Teacher profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = TeacherProfileSerializer(profile, context={"request": request})

        return Response(
            {
                "message": "Teacher profile retrieved successfully",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK
        )
    
    def put(self, request):
        user = request.user
        profile = getattr(user, "teacher_profile", None)

        if not profile:
            return Response(
                {"message": "Teacher profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = TeacherProfileSerializer(profile, data=request.data, partial=True, context={"request": request})

        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "message": "Teacher profile updated successfully",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        current_password = request.data.get("current_password")
        new_password = request.data.get("new_password")
        confirm_password = request.data.get("confirm_password")

        if not current_password or not new_password or not confirm_password:
            return Response(
                {"message": "All password fields are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if new_password != confirm_password:
            return Response(
                {"message": "New passwords do not match."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not user.check_password(current_password):
            return Response(
                {"message": "Current password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(new_password)
        user.save()

        return Response(
            {"message": "Password changed successfully."},
            status=status.HTTP_200_OK
        )
    

class ForgotPasswordView(APIView):
    def post(self, request):
        email = request.data.get("email")

        if not email:
            return Response(
                {"message": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = models.User.objects.get(email=email)
        except models.User.DoesNotExist:
            return Response(
                {"message": "User with this email does not exist."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Generate a new OTP for password reset
        code = generate_otp(user)

        sent = forgot_password_email(user, code)
        if not sent:
            return Response(
                {"message": "Failed to send password reset email."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {"message": "A password reset OTP has been sent to your email."},
            status=status.HTTP_200_OK
        )
    
class ResetPasswordView(APIView):
    def post(self, request):
        email = request.data.get("email")
        reset_token = request.data.get("reset_token")
        new_password = request.data.get("password")
        confirm_password = request.data.get("confirm_password")

        if not email or not reset_token or not new_password or not confirm_password:
            print ("All fields are required.")
            return Response(
                {"message": "All fields are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if new_password != confirm_password:
            print ("New passwords do not match.")
            return Response(
                {"message": "New passwords do not match."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = models.User.objects.get(email=email)
        except models.User.DoesNotExist:
            print ("User with this email does not exist.")
            return Response(
                {"message": "User with this email does not exist."},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            session = PasswordResetSession.objects.get(user=user, token=reset_token, is_used=False, expires_at__gt=timezone.now())
        except PasswordResetSession.DoesNotExist:
            print ("Invalid reset token.")
            return Response(
                {"message": "Invalid reset token."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Reset the user's password
        user.set_password(new_password)
        user.save()

        # Mark the reset session as used
        session.is_used = True
        session.save(update_fields=["is_used"])

        return Response(
            {"message": "Password reset successfully."},
            status=status.HTTP_200_OK
        )
    

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh_token"]
            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response(
                {"message": "Logout successful"},
                status=status.HTTP_205_RESET_CONTENT
            )
        except Exception as e:
            return Response(
                {"message": "Invalid token or token has already been blacklisted."},
                status=status.HTTP_400_BAD_REQUEST
            )
    

class CategorySubcategoryListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        
        teacher_profile = getattr(
            request.user,
            "teacher_profile",
            None
        )
        categories = Category.objects.prefetch_related('subcategories').filter(assigned_teachers=teacher_profile)
        serializer = CategorySubcategorySerializer(categories, many=True)

        return Response(
            {
                "message": "Category and subcategory list retrieved successfully",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )

class SubcategoryCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):

        teacher_profile = getattr(
            request.user,
            "teacher_profile",
            None
        )

        if not teacher_profile:
            return Response(
                {
                    "message": "Only teachers can create subcategories."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = SubcategorySerializer(
            data=request.data,
            context={"request": request}
        )

        if serializer.is_valid():
            subcategory = serializer.save()

            return Response(
                {
                    "message": "Subcategory created successfully",
                    "data": SubcategorySerializer(
                        subcategory,
                        context={"request": request}
                    ).data
                },
                status=status.HTTP_201_CREATED
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
    

class CourseListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = getattr(user, "teacher_profile", None)

        course_id = request.query_params.get("course_id", None)

        if not profile:
            return Response(
                {"message": "Teacher profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if course_id:
            courses = profile.teacher_courses.filter(id=course_id)

        else:
            courses = profile.teacher_courses.all()
            
        serializer = CourseSerializer(courses, context={"request": request}, many=True)

        return Response(
            {
                "message": "Course list retrieved successfully",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    def post(self, request):
        user = request.user
        profile = getattr(user, "teacher_profile", None)

        if not profile:
            return Response(
                {"message": "Teacher profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        course_id = request.query_params.get("course_id", None)

        if course_id:
            try:
                course = profile.teacher_courses.get(id=course_id)
            except Course.DoesNotExist:
                return Response(
                    {"message": "Course not found."},
                    status=status.HTTP_404_NOT_FOUND
                )

        serializer = CourseSerializer(data=request.data, context={"request": request})

        if serializer.is_valid():
            course = serializer.save()
            return Response(
                {
                    "message": "Course created successfully",
                    "data": CourseSerializer(course, context={"request": request}).data
                },
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

    def patch(self, request):
        user = request.user
        profile = getattr(user, "teacher_profile", None)

        if not profile:
            return Response(
                {"message": "Teacher profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        course_id = request.query_params.get("course_id", None)

        if not course_id:
            return Response(
                {"message": "Course ID is required for updating."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            course = profile.teacher_courses.get(id=course_id)
        except Course.DoesNotExist:
            return Response(
                {"message": "Course not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = CourseSerializer(course, data=request.data, partial=True, context={"request": request})

        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "message": "Course updated successfully",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class ModuleListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = getattr(user, "teacher_profile", None)

        module_id = request.query_params.get("module_id", None)
        course_id = request.query_params.get("course_id", None)

        if not profile:
            return Response(
                {"message": "Teacher profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            course = profile.teacher_courses.get(id=course_id)
        except Course.DoesNotExist:
            return Response(
                {"message": "Course not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if module_id:
            try:
                module = course.modules.get(id=module_id)
            except Module.DoesNotExist:
                return Response(
                    {"message": "Module not found."},
                    status=status.HTTP_404_NOT_FOUND
                )
            serializer = ModuleSerializer(module)
            return Response(
                {
                    "message": "Module retrieved successfully",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )
        modules = course.modules.all()
        serializer = ModuleSerializer(modules, many=True)

        return Response(
            {
                "message": "Module list retrieved successfully",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    def post(self, request):
        user = request.user
        profile = getattr(user, "teacher_profile", None)

        if not profile:
            return Response(
                {"message": "Teacher profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        course_id = request.query_params.get("course_id", None)

        try:
            course = profile.teacher_courses.get(id=course_id)
        except Course.DoesNotExist:
            return Response(
                {"message": "Course not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ModuleSerializer(data=request.data)

        if serializer.is_valid():
            module = serializer.save(course=course)
            return Response(
                {
                    "message": "Module created successfully",
                    "data": ModuleSerializer(module).data
                },
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

    def patch(self, request):
        user = request.user
        profile = getattr(user, "teacher_profile", None)

        course_id = request.query_params.get("course_id", None)
        module_id = request.query_params.get("module_id", None)

        if not profile:
            return Response(
                {"message": "Teacher profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if not module_id:
            return Response(
                {"message": "Module ID is required for updating."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            module = Module.objects.get(id=module_id, course__in=profile.teacher_courses.filter(id=course_id))
        except Module.DoesNotExist:
            return Response(
                {"message": "Module not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ModuleSerializer(module, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "message": "Module updated successfully",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request):
        user = request.user
        profile = getattr(user, "teacher_profile", None)

        course_id = request.query_params.get("course_id", None)
        module_id = request.query_params.get("module_id", None)

        if not profile:
            return Response(
                {"message": "Teacher profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if not module_id:
            return Response(
                {"message": "Module ID is required for deletion."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            module = Module.objects.get(id=module_id, course__in=profile.teacher_courses.filter(id=course_id))
        except Module.DoesNotExist:
            return Response(
                {"message": "Module not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        module.delete()

        return Response(
            {
                "message": "Module deleted successfully"
            },
            status=status.HTTP_200_OK
        )
    

# ------------------------------- Lesson Views -------------------------------

class LessonListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, "teacher_profile", None)

        if not profile:
            return Response(
                {"message": "Teacher profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        module_id = request.query_params.get("module_id")
        lesson_id = request.query_params.get("lesson_id")
        course_id = request.query_params.get("course_id")

        # if not module_id:
        #     return Response(
        #         {"module_id": "This query parameter is required."},
        #         status=status.HTTP_400_BAD_REQUEST
        #     )

        if module_id:
            try:
                module = Module.objects.select_related("course").get(
                    id=module_id,
                    course__teacher=profile
                )
            except Module.DoesNotExist:
                return Response(
                    {"message": "Module not found."},
                    status=status.HTTP_404_NOT_FOUND
                )
        # Get single lesson
        if lesson_id:
            try:
                lesson = Lesson.objects.prefetch_related("resources").get(
                    id=lesson_id,
                    module=module
                )
            except Lesson.DoesNotExist:
                return Response(
                    {"message": "Lesson not found."},
                    status=status.HTTP_404_NOT_FOUND
                )

            serializer = LessonSerializer(
                lesson,
                context={"request": request}
            )

            return Response(
                {
                    "message": "Lesson retrieved successfully",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )

        # Get all lessons for the teacher, optionally filtered by course or module
        lessons = Lesson.objects.filter(module__course__teacher=profile)
        if course_id:
            lessons = lessons.filter(module__course__id=course_id)
        if module_id:
            lessons = lessons.filter(module__id=module_id)
        lessons = lessons.prefetch_related("resources").order_by("order")

        serializer = LessonSerializer(
            lessons,
            many=True,
            context={"request": request}
        )

        return Response(
            {
                "message": "Lesson list retrieved successfully",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )

    def post(self, request):
        profile = getattr(request.user, "teacher_profile", None)

        if not profile:
            return Response(
                {"message": "Teacher profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        module_id = request.query_params.get("module_id")

        if not module_id:
            return Response(
                {"module_id": "This query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        payload = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        payload["module"] = module_id

        serializer = LessonCreateSerializer(
            data=payload,
            context={"request": request},
        )

        if serializer.is_valid():
            lesson = serializer.save()

            return Response(
                {
                    "message": "Lesson created successfully",
                    "data": LessonSerializer(
                        lesson,
                        context={"request": request}
                    ).data,
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

    def patch(self, request):
        profile = getattr(request.user, "teacher_profile", None)

        if not profile:
            return Response(
                {"message": "Teacher profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # module_id = request.query_params.get("module_id")
        lesson_id = request.query_params.get("lesson_id")

        if not lesson_id:
            return Response(
                {"lesson_id": "This query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            lesson = Lesson.objects.select_related("module__course").get(
                id=lesson_id,
                module__course__teacher=profile
            )
        except Lesson.DoesNotExist:
            return Response(
                {"message": "Lesson not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = LessonCreateSerializer(
            lesson,
            data=request.data,
            partial=True,
            context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()

            return Response(
                {
                    "message": "Lesson updated successfully",
                    "data": LessonSerializer(
                        lesson,
                        context={"request": request}
                    ).data,
                },
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    def delete(self, request):
        profile = getattr(request.user, "teacher_profile", None)

        if not profile:
            return Response(
                {"message": "Teacher profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        lesson_id = request.query_params.get("lesson_id")

        if not lesson_id:
            return Response(
                {"lesson_id": "This query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            lesson = Lesson.objects.select_related("module__course").get(
                id=lesson_id,
                module__course__teacher=profile
            )
        except Lesson.DoesNotExist:
            return Response(
                {"message": "Lesson not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        lesson.delete()

        return Response(
            {
                "message": "Lesson deleted successfully"
            },
            status=status.HTTP_200_OK
        )
    

from django.db.models import Max

class NextResourceIdView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, "teacher_profile", None)

        category = request.query_params.get("category")
        subcategory = request.query_params.get("subcategory")
        course = request.query_params.get("course")

        if not profile:
            return Response(
                {"message": "Teacher profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Build base queryset
        queryset = LessonResource.objects.all()
        # Apply optional filters
        if category:
            queryset = queryset.filter(lesson__module__course__subcategory__category_id=category)
        if subcategory:
            queryset = queryset.filter(lesson__module__course__subcategory_id=subcategory)
        if course:
            queryset = queryset.filter(lesson__module__course_id=course)

        next_resource_id = (queryset.aggregate(max_id=Max("id"))["max_id"] or 0) + 1

        return Response(
            {
                "message": "Next resource ID retrieved successfully",
                "next_resource_id": next_resource_id,
            },
            status=status.HTTP_200_OK,
        )


class QuizListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, "teacher_profile", None)
        if not profile:
            return Response({"message": "Teacher profile not found."}, status=status.HTTP_404_NOT_FOUND)
        quizzes = CourseQuiz.objects.filter(lesson__module__course__teacher=profile).order_by("order")
        serializer = CourseQuizListSerializer(quizzes, many=True, context={"request": request})
        return Response({"message": "Quiz list retrieved successfully", "data": serializer.data}, status=status.HTTP_200_OK)


class QuizCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = getattr(request.user, "teacher_profile", None)
        if not profile:
            return Response({"message": "Teacher profile not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = CourseQuizCreateSerializer(data=request.data)
        if serializer.is_valid():
            quiz = serializer.save()
            # Handle nested questions if provided
            questions_data = request.data.get('questions', [])
            for q_data in questions_data:
                # Ensure the quiz foreign key is set
                q_data['quiz'] = quiz.id
                q_serializer = CourseQuizQuestionCreateSerializer(data=q_data)
                if q_serializer.is_valid():
                    q_serializer.save()
                else:
                    # Roll back the quiz if any question is invalid
                    quiz.delete()
                    return Response({"message": "Invalid question data", "errors": q_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"message": "Quiz created successfully", "data": CourseQuizListSerializer(quiz, context={"request": request}).data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
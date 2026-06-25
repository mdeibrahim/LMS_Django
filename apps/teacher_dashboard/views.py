from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated

from content.models import Course, Module, Lesson
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
)

class RegisterView(APIView):
    def post(self, request):
        serializer = TeacherRegisterSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Teacher registered successfully"},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

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
                {"detail": "Teacher profile not found."},
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
                {"detail": "Teacher profile not found."},
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
                    "detail": "Only teachers can create subcategories."
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

        if not profile:
            return Response(
                {"detail": "Teacher profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

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
                {"detail": "Teacher profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        course_id = request.query_params.get("course_id", None)

        try:
            course = profile.teacher_courses.get(id=course_id)
        except Course.DoesNotExist:
            return Response(
                {"detail": "Course not found."},
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



class ModuleListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = getattr(user, "teacher_profile", None)

        module_id = request.query_params.get("module_id", None)
        course_id = request.query_params.get("course_id", None)

        if not profile:
            return Response(
                {"detail": "Teacher profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            course = profile.teacher_courses.get(id=course_id)
        except Course.DoesNotExist:
            return Response(
                {"detail": "Course not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if module_id:
            try:
                module = course.modules.get(id=module_id)
            except Module.DoesNotExist:
                return Response(
                    {"detail": "Module not found."},
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
                {"detail": "Teacher profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        course_id = request.query_params.get("course_id", None)

        try:
            course = profile.teacher_courses.get(id=course_id)
        except Course.DoesNotExist:
            return Response(
                {"detail": "Course not found."},
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
                {"detail": "Teacher profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if not module_id:
            return Response(
                {"detail": "Module ID is required for updating."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            module = Module.objects.get(id=module_id, course__in=profile.teacher_courses.filter(id=course_id))
        except Module.DoesNotExist:
            return Response(
                {"detail": "Module not found."},
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
                {"detail": "Teacher profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if not module_id:
            return Response(
                {"detail": "Module ID is required for deletion."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            module = Module.objects.get(id=module_id, course__in=profile.teacher_courses.filter(id=course_id))
        except Module.DoesNotExist:
            return Response(
                {"detail": "Module not found."},
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
        user = request.user
        profile = getattr(user, "teacher_profile", None)

        lesson_id = request.query_params.get("lesson_id", None)
        module_id = request.query_params.get("module_id", None)
        course_id = request.query_params.get("course_id", None)

        if not profile:
            return Response(
                {"detail": "Teacher profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            course = profile.teacher_courses.get(id=course_id)
        except Course.DoesNotExist:
            return Response(
                {"detail": "Course not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            module = course.modules.get(id=module_id)
        except Module.DoesNotExist:
            return Response(
                {"detail": "Module not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if lesson_id:
            try:
                lesson = module.lessons.get(id=lesson_id)
            except Lesson.DoesNotExist:
                return Response(
                    {"detail": "Lesson not found."},
                    status=status.HTTP_404_NOT_FOUND
                )
            serializer = LessonSerializer(lesson, context={"request": request})
            return Response(
                {
                    "message": "Lesson retrieved successfully",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )
        lessons = module.lessons.all()
        serializer = LessonSerializer(lessons, many=True, context={"request": request})

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
                {"detail": "Teacher profile not found."},
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
    

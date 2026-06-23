from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated

from .serializers import TeacherLoginSerializer, TeacherRegisterSerializer, TeacherProfileSerializer, CourseSerializer, SubcategorySerializer

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

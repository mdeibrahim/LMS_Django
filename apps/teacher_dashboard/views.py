from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated

from .serializers import TeacherLoginSerializer, TeacherRegisterSerializer, TeacherProfileSerializer

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

        return Response(
            {
                "id": profile.id,
                "full_name": profile.full_name,
                "phone_number": profile.phone_number,
                "profile_picture": profile.profile_picture.url if profile.profile_picture else None,
                "teacher_institution": profile.teacher_institution,
                "teacher_subject": profile.teacher_subject,
                "teacher_experience_years": profile.teacher_experience_years,
                "date_joined": profile.created_at,
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

        serializer = TeacherProfileSerializer(profile, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
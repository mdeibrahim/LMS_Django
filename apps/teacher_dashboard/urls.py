from django.urls import path
from .views import LoginView, RegisterView, TeacherProfileView


urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='teacher_register'),
    path('auth/login/', LoginView.as_view(), name='teacher_login'),
    path('profile/', TeacherProfileView.as_view(), name='teacher_profile'),
    path('update-profile/', TeacherProfileView.as_view(), name='teacher_update_profile'),
]

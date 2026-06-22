from django.urls import path
from .views import LoginView, RegisterView


urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='teacher_register'),
    path('auth/login/', LoginView.as_view(), name='teacher_login'),
]

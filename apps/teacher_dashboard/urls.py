from django.urls import path
from .views import LoginView, RegisterView, TeacherProfileView, CourseListView, SubcategoryCreateView


urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='teacher_register'),
    path('auth/login/', LoginView.as_view(), name='teacher_login'),
    path('profile/', TeacherProfileView.as_view(), name='teacher_profile'),
    path('update-profile/', TeacherProfileView.as_view(), name='teacher_update_profile'),

    path('create-subcategory/', SubcategoryCreateView.as_view(), name='teacher_create_subcategory'),
    path('create-course/', CourseListView.as_view(), name='teacher_create_course'),
    path('course-list/', CourseListView.as_view(), name='teacher_course_list'),
]

from django.urls import path
from .views import LoginView, RegisterView, TeacherProfileView, CourseListView, SubcategoryCreateView, CategorySubcategoryListView, ModuleListView, LessonListView, NextResourceIdView, LogoutView, ChangePasswordView, VerifyOTPView, ResendOTPView, ForgotPasswordView, ResetPasswordView


urlpatterns = [
    # Auth URLs 
    path('auth/register/', RegisterView.as_view(), name='teacher_register'),
    path('auth/verify-otp/', VerifyOTPView.as_view(), name='teacher_verify_otp'),
    path('auth/resend-otp/', ResendOTPView.as_view(), name='teacher_resend_otp'),

    path('auth/login/', LoginView.as_view(), name='teacher_login'),
    path('profile/', TeacherProfileView.as_view(), name='teacher_profile'),
    path('change-password/', ChangePasswordView.as_view(), name='teacher_password_change'),
    path('update-profile/', TeacherProfileView.as_view(), name='teacher_update_profile'),
    path('logout/', LogoutView.as_view(), name='teacher_logout'),

    path('auth/forgot-password/', ForgotPasswordView.as_view(), name='teacher_forgot_password'),
    path('auth/reset-password/', ResetPasswordView.as_view(), name='teacher_reset_password'),

    # Course and Subcategory URLs
    path('category-subcategory-list/', CategorySubcategoryListView.as_view(), name='teacher_category_subcategory_list'),
    path('create-subcategory/', SubcategoryCreateView.as_view(), name='teacher_create_subcategory'),
    

    # Course URLs
    path('course-list/', CourseListView.as_view(), name='teacher_course_list'),
    path('course-detail/', CourseListView.as_view(), name='teacher_course_detail'),
    path('create-course/', CourseListView.as_view(), name='teacher_create_course'),
    path('update-course/', CourseListView.as_view(), name='teacher_update_course'),
    path('delete-course/', CourseListView.as_view(), name='teacher_delete_course'),
    


    # Module URLs
    path('module-list/', ModuleListView.as_view(), name='teacher_module_list'),
    path('module-detail/', ModuleListView.as_view(), name='teacher_module_detail'),
    path('create-module/', ModuleListView.as_view(), name='teacher_create_module'),
    path('update-module/', ModuleListView.as_view(), name='teacher_update_module'),
    path('delete-module/', ModuleListView.as_view(), name='teacher_delete_module'),


    # Lesson URLs
    path('lesson-list/', LessonListView.as_view(), name='teacher_lesson_list'),
    path('lesson-detail/', LessonListView.as_view(), name='teacher_lesson_detail'),
    path('create-lesson/', LessonListView.as_view(), name='teacher_create_lesson'),
    path('update-lesson/', LessonListView.as_view(), name='teacher_update_lesson'),
    path('delete-lesson/', LessonListView.as_view(), name='teacher_delete_lesson'),
    path('next-resource-id/', NextResourceIdView.as_view(), name='teacher_next_resource_id'),
]

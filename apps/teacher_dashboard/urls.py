from django.urls import path
from .views import (
    FirebaseGoogleLoginView,
    LoginView, RegisterView, TeacherProfileView, CourseListView,
    SubcategoryCreateView, SubcategoryDetailUpdateDeleteView,
    CategorySubcategoryListView, ModuleListView, LessonListView,
    NextResourceIdView, LogoutView, ChangePasswordView, VerifyOTPView,
    ResendOTPView, ForgotPasswordView, ResetPasswordView,
    QuizListView
)
from .admin_views import (
    AdminCertificateListView,
    AdminDeviceSessionListView,
    AdminEnrollmentListView,
    AdminOTPListView,
    AdminPaymentInstructionDetailView,
    AdminPaymentInstructionListCreateView,
    AdminPaymentSubmissionListView,
    AdminStudentListView,
    AdminTeacherListView,
    AdminUserDetailView,
    AdminUserListView,
)


urlpatterns = [
    # Auth URLs 
    path('auth/register/', RegisterView.as_view(), name='teacher_register'),
    path('auth/verify-otp/', VerifyOTPView.as_view(), name='teacher_verify_otp'),
    path('auth/resend-otp/', ResendOTPView.as_view(), name='teacher_resend_otp'),

    path('auth/login/', LoginView.as_view(), name='teacher_login'),
    path('auth/firebase-google-auth/', FirebaseGoogleLoginView.as_view(), name='teacher_firebase_google_auth'),
    path('profile/', TeacherProfileView.as_view(), name='teacher_profile'),
    path('change-password/', ChangePasswordView.as_view(), name='teacher_password_change'),
    path('update-profile/', TeacherProfileView.as_view(), name='teacher_update_profile'),
    path('logout/', LogoutView.as_view(), name='teacher_logout'),

    path('auth/forgot-password/', ForgotPasswordView.as_view(), name='teacher_forgot_password'),
    path('auth/reset-password/', ResetPasswordView.as_view(), name='teacher_reset_password'),

    # Course and Subcategory URLs
    path('category-subcategory-list/', CategorySubcategoryListView.as_view(), name='teacher_category_subcategory_list'),
    path('create-subcategory/', SubcategoryCreateView.as_view(), name='teacher_create_subcategory'),
    path('subcategories/<int:pk>/', SubcategoryDetailUpdateDeleteView.as_view(), name='subcategory-detail-update-delete'),
    

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


    # Quiz URLs
    path('quiz-list/', QuizListView.as_view(), name='teacher_quiz_list'),
    path('quiz-detail/', QuizListView.as_view(), name='teacher_quiz_detail'),
    path('create-quiz/', QuizListView.as_view(), name='teacher_create_quiz'),
    path('update-quiz/', QuizListView.as_view(), name='teacher_update_quiz'),
    path('delete-quiz/', QuizListView.as_view(), name='teacher_delete_quiz'),

    # Admin URLs
    path('admin/users/', AdminUserListView.as_view(), name='admin_user_list'),
    path('admin/users/<int:pk>/', AdminUserDetailView.as_view(), name='admin_user_detail'),
    path('admin/teachers/', AdminTeacherListView.as_view(), name='admin_teacher_list'),
    path('admin/students/', AdminStudentListView.as_view(), name='admin_student_list'),
    path('admin/device-sessions/', AdminDeviceSessionListView.as_view(), name='admin_device_session_list'),
    path('admin/otps/', AdminOTPListView.as_view(), name='admin_otp_list'),
    path('admin/payment-submissions/', AdminPaymentSubmissionListView.as_view(), name='admin_payment_submission_list'),
    path('admin/payment-submissions/<int:pk>/', AdminPaymentSubmissionListView.as_view(), name='admin_payment_submission_detail'),
    path('admin/enrollments/', AdminEnrollmentListView.as_view(), name='admin_enrollment_list'),
    path('admin/certificates/', AdminCertificateListView.as_view(), name='admin_certificate_list'),
    path('admin/payment-instructions/', AdminPaymentInstructionListCreateView.as_view(), name='admin_payment_instruction_list'),
    path('admin/payment-instructions/<int:pk>/', AdminPaymentInstructionDetailView.as_view(), name='admin_payment_instruction_detail'),
]

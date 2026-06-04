from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

app_name = 'content'

urlpatterns = [
    # ── Page views ──────────────────────────────────────────────
    path('', views.home, name='home'),
    path('accounts/login/', views.student_login, name='login'),
    path('accounts/signup/', views.student_signup, name='signup'),
    path('accounts/login/student/', views.student_login, name='student_login'),
    path('accounts/otp-verify/', views.otp_verify, name='otp_verify'),
    path('accounts/otp-resend/', views.otp_resend, name='otp_resend'),


    # Password reset (using Django auth views)
    path('accounts/password-reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset_form.html',
        email_template_name='registration/password_reset_email.html',
        success_url='/accounts/password-reset/done/'
    ), name='password_reset'),
    path('accounts/password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'
    ), name='password_reset_done'),
    path('accounts/password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
        success_url='/accounts/password-reset/complete/'
    ), name='password_reset_confirm'),
    path('accounts/password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'
    ), name='password_reset_complete'),


    path('accounts/signup/student/', views.student_signup, name='student_signup'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('profile/', views.profile_page, name='profile'),
    path('dashboard/student/', views.student_dashboard, name='student_dashboard'),
    path('dashboard/course/<int:course_id>/claim-certificate/', views.claim_certificate, name='claim_certificate'),
    path('my-courses/', views.my_modules, name='my_courses'),
    path('my-modules/', views.my_modules, name='my_modules'),


    # Course-centric routes (category removed)
    path('courses/<slug:course_slug>/', views.course_detail, name='course_detail'),
    path('courses/<slug:course_slug>/details/', views.course_detail, name='course_details'),
    path('courses/<slug:course_slug>/modules/<slug:module_slug>/', views.module_detail, name='module_detail'),
    path('courses/<slug:course_slug>/modules/<slug:module_slug>/editor/', views.module_editor, name='module_editor'),
    path('courses/<slug:course_slug>/modules/<slug:module_slug>/lessons/<slug:lesson_slug>/', views.lesson_detail, name='lesson_detail'),
    path('courses/<slug:course_slug>/modules/<slug:module_slug>/lessons/<slug:lesson_slug>/quizzes/<int:quiz_id>/', views.quiz_detail, name='quiz_detail'),
    path('courses/<slug:course_slug>/modules/<slug:module_slug>/resources/<int:video_id>/', views.play_video, name='play_video'),
    path('courses/<slug:course_slug>/buy/', views.buy_module, name='buy_module'),
    path('courses/<slug:course_slug>/start-purchase/', views.start_purchase, name='start_purchase'),
    path('courses/<slug:course_slug>/purchase/', views.course_purchase, name='course_purchase'),
    path('courses/<slug:course_slug>/submit-payment/', views.submit_payment_details, name='submit_payment_details'),

    # ── Module / interactive content APIs ───────────────────────
    path('api/content/<int:content_id>/', views.get_course_content, name='get_course_content'),
    path('api/interactive-content/<int:content_id>/', views.get_interactive_content, name='get_interactive_content'),
    path('api/module/<int:module_id>/save/', views.api_subject_save, name='api_subject_save'),
    path('api/module/<int:module_id>/ic/create/', views.api_ic_create, name='api_ic_create'),
    path('api/ic/<int:ic_id>/update/', views.api_ic_update, name='api_ic_update'),
    path('api/ic/<int:ic_id>/delete/', views.api_ic_delete, name='api_ic_delete'),
    path('api/module/<int:module_id>/accordion/create/', views.api_accordion_create, name='api_accordion_create'),
    path('api/accordion/<int:section_id>/update/', views.api_accordion_update, name='api_accordion_update'),
    path('api/accordion/<int:section_id>/delete/', views.api_accordion_delete, name='api_accordion_delete'),

    # ── Read API ────────────────────────────────────────────────
    path('api/v1/', include('content.api_urls')),
]

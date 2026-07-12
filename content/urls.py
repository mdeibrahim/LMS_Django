from django.urls import path
from . import views

app_name = 'content'

urlpatterns = [
    # ── Page views ──────────────────────────────────────────────
    path('', views.home, name='home'),
    path('profile/', views.profile_page, name='profile'),
    path('dashboard/student/', views.student_dashboard, name='student_dashboard'),
    path('dashboard/course/<int:course_id>/claim-certificate/', views.claim_certificate, name='claim_certificate'),
    path('my-courses/', views.my_modules, name='my_courses'),
    path('my-modules/', views.my_modules, name='my_modules'),


    # Course-centric routes (category removed)
    path('courses/<str:course_slug>/', views.course_detail, name='course_detail'),
    path('courses/<str:course_slug>/details/', views.course_detail, name='course_details'),
    path('courses/<str:course_slug>/modules/<str:module_slug>/', views.module_detail, name='module_detail'),
    path('courses/<str:course_slug>/modules/<str:module_slug>/editor/', views.module_editor, name='module_editor'),
    path('courses/<str:course_slug>/modules/<str:module_slug>/lessons/<str:lesson_slug>/', views.lesson_detail, name='lesson_detail'),
    path('courses/<str:course_slug>/modules/<str:module_slug>/lessons/<str:lesson_slug>/editor/', views.lesson_editor, name='lesson_editor'),
    path('courses/<str:course_slug>/modules/<str:module_slug>/lessons/<str:lesson_slug>/quizzes/<int:quiz_id>/', views.quiz_detail, name='quiz_detail'),
    path('courses/<str:course_slug>/modules/<str:module_slug>/quizzes/<int:quiz_id>/', views.quiz_detail, name='module_quiz_detail'),
    path('courses/<str:course_slug>/modules/<str:module_slug>/resources/<int:video_id>/', views.play_video, name='play_video'),
    path('courses/<str:course_slug>/buy/', views.buy_module, name='buy_module'),
    path('courses/<str:course_slug>/start-purchase/', views.start_purchase, name='start_purchase'),
    path('courses/<str:course_slug>/purchase/', views.course_purchase, name='course_purchase'),
    path('courses/<str:course_slug>/submit-payment/', views.submit_payment_details, name='submit_payment_details'),

    # ── Module / content APIs ───────────────────────
    path('api/content/<int:content_id>/', views.get_course_content, name='get_course_content'),
    path('api/resource/<int:content_id>/', views.get_lesson_resource, name='get_lesson_resource'),
    path('api/module/<int:module_id>/save/', views.api_subject_save, name='api_subject_save'),
    path('api/lesson/<int:lesson_id>/save/', views.api_lesson_save, name='api_lesson_save'),
    path('api/module/<int:module_id>/ic/create/', views.api_ic_create, name='api_ic_create'),
    path('api/lesson/<int:lesson_id>/ic/create/', views.api_lesson_ic_create, name='api_lesson_ic_create'),
    path('api/ic/<int:ic_id>/update/', views.api_ic_update, name='api_ic_update'),
    path('api/ic/<int:ic_id>/delete/', views.api_ic_delete, name='api_ic_delete'),

]

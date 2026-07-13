from django.urls import path
from django.contrib.auth import views as auth_views
from apps.authentication import views

app_name = 'authentication'

urlpatterns = [
    path('accounts/login/', views.student_login, name='login'),
    path('accounts/signup/', views.student_signup, name='signup'),
    path('accounts/signup/student/', views.student_signup, name='student_signup'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/login/student/', views.student_login, name='student_login'),
    path('accounts/otp-verify/', views.otp_verify, name='otp_verify'),
    path('accounts/otp-resend/', views.otp_resend, name='otp_resend'),
    # path('accounts/firebase-phone-auth/', views.firebase_phone_auth, name='firebase_phone_auth'),
    path('accounts/firebase-google-auth/', views.firebase_google_auth, name='firebase_google_auth'),
    # path('accounts/firebase-link-phone/', views.firebase_link_phone, name='firebase_link_phone'),

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


# Teacher Auth Urls



# Student Auth Urls

    
]

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from content.dashboard import admin_dashboard, admin_root_redirect

urlpatterns = [
    path('admin/', admin.site.admin_view(admin_root_redirect), name='admin_root'),
    path('admin/dashboard/', admin.site.admin_view(admin_dashboard), name='admin_dashboard'),
    path('admin/', admin.site.urls),
    path('', include(('content.urls', 'content'), namespace='content')),
    path('', include(('apps.authentication.urls', 'authentication'), namespace='authentication')),

    
    path('api/', include(('apps.teacher_dashboard.urls', 'apps.teacher_dashboard'), namespace='teacher_dashboard')),
    path('api/', include(('apps.student_dashboard.urls', 'apps.student_dashboard'), namespace='student_dashboard'))
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# In production, static() does not serve media when DEBUG=False.
# This keeps uploaded files accessible behind Gunicorn (suitable for small/demo deployments).
if not settings.DEBUG:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]

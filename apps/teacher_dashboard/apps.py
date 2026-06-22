from django.apps import AppConfig


class TeacherDashboardConfig(AppConfig):
    name = 'apps.teacher_dashboard'
    verbose_name = "Teacher Dashboard"

    def ready(self):
        import apps.teacher_dashboard.signals

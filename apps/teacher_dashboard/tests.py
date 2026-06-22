from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.student_dashboard.models import StudentProfile
from content.models import Category, Subcategory, UserRole

from .models import TeacherProfile


User = get_user_model()


class TeacherDashboardTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="admin@example.com",
            password="adminpass123",
        )
        self.category_1 = Category.objects.create(name="Programming", slug="programming")
        self.category_2 = Category.objects.create(name="Design", slug="design")
        self.subcategory_1 = Subcategory.objects.create(category=self.category_1, name="Python", slug="python")
        self.subcategory_2 = Subcategory.objects.create(category=self.category_2, name="UI", slug="ui")

        self.teacher_user = User.objects.create_user(
            email="teacher1@example.com",
            password="teacherpass123",
        )
        self.teacher_profile = TeacherProfile.objects.create(
            user=self.teacher_user,
            full_name="Teacher One",
            phone_number="01234567890",
        )
        self.teacher_profile.assigned_categories.add(self.category_1, self.category_2)

        self.student_user = User.objects.create_user(
            email="student1@example.com",
            password="studentpass123",
        )
        StudentProfile.objects.create(
            user=self.student_user,
            full_name="Student One",
            phone_number="09876543210",
        )

    def test_teacher_proxy_only_returns_teacher_profiles(self):
        teacher_ids = list(TeacherProfile.objects.values_list("user_id", flat=True))

        self.assertEqual(teacher_ids, [self.teacher_user.id])

        teacher_profile = TeacherProfile.objects.get(user=self.teacher_user)
        subcategory_names = list(teacher_profile.assigned_subcategories.values_list("name", flat=True))

        self.assertCountEqual(subcategory_names, ["Python", "UI"])

    def test_teacher_admin_changelist_is_available(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("admin:teacher_dashboard_teacherprofile_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Teacher One")
        self.assertNotContains(response, "Student One")

    def test_teacher_profile_has_multiple_categories(self):
        teacher_profile = TeacherProfile.objects.get(user=self.teacher_user)
        category_names = list(teacher_profile.assigned_categories.values_list("name", flat=True))

        self.assertCountEqual(category_names, ["Programming", "Design"])

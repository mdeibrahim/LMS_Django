import json

from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.student_dashboard.models import StudentProfile
from content.models import Category, Course, Lesson, LessonResource, Module, Subcategory, UserRole

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
        self.course = Course.objects.create(
            subcategory=self.subcategory_1,
            teacher=self.teacher_profile,
            name="Intro to Python",
            slug="intro-to-python",
            description="",
            price=0,
            is_published=True,
        )
        self.module = Module.objects.create(course=self.course, title="Core Concepts", slug="core-concepts")

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

        self.assertCountEqual(subcategory_names, ["all", "Python", "all", "UI"])

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

    def test_teacher_course_list_returns_teacher_courses(self):
        self.client.force_login(self.teacher_user)

        response = self.client.get(reverse("teacher_dashboard:teacher_course_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]), 1)
        self.assertEqual(response.data["data"][0]["id"], self.course.id)
        self.assertEqual(response.data["data"][0]["name"], self.course.name)

    def test_teacher_create_course_auto_generates_slug_and_subcategory(self):
        self.client.force_login(self.teacher_user)

        response = self.client.post(
            reverse("teacher_dashboard:teacher_create_course"),
            data={
                "name": "Django Basics",
                "category": self.category_1.id,
                "description": "Intro course",
                "price": "150.00",
                "is_published": True,
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["data"]["name"], "Django Basics")
        self.assertEqual(response.data["data"]["slug"], "django-basics")
        self.assertEqual(response.data["data"]["subcategory"], "all")
        self.assertEqual(response.data["data"]["category"], "Programming")
        self.assertTrue(Course.objects.filter(slug="django-basics", teacher=self.teacher_profile).exists())
        created_course = Course.objects.get(slug="django-basics")
        self.assertEqual(created_course.subcategory.category, self.category_1)
        self.assertEqual(created_course.subcategory.slug, "all")

    def test_teacher_create_subcategory_duplicate_name_returns_custom_message(self):
        self.client.force_login(self.teacher_user)

        response = self.client.post(
            reverse("teacher_dashboard:teacher_create_subcategory"),
            data={
                "name": "Python",
                "category": self.category_1.id,
                "description": "Another python subcategory",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["non_field_errors"][0],
            "subcategory already exist in this category",
        )

    def test_teacher_create_lesson_creates_lesson_and_media_in_one_request(self):
        self.client.force_login(self.teacher_user)
        image_file = SimpleUploadedFile("diagram.png", b"image-bytes", content_type="image/png")

        response = self.client.post(
            reverse("teacher_dashboard:teacher_create_lesson"),
            data={
                "module_id": self.module.id,
                "title": "Lesson One",
                "description": "Rich lesson content",
                "body_content": "<p><strong>Bold</strong> and <em>italic</em> text.</p>",
                "order": 1,
                "is_preview": True,
                "is_published": True,
                "resources": json.dumps([
                    {
                        "title": "Lesson Notes",
                        "content_type": "text",
                        "text_content": "<p>Notes</p>",
                        "order": 1,
                    },
                    {
                        "title": "Lesson Diagram",
                        "content_type": "image",
                        "file_key": "diagram_file",
                        "order": 2,
                    },
                ]),
                "diagram_file": image_file,
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["data"]["title"], "Lesson One")
        self.assertEqual(response.data["data"]["slug"], "lesson-one")
        self.assertEqual(response.data["data"]["body_content"], "<p><strong>Bold</strong> and <em>italic</em> text.</p>")
        self.assertEqual(len(response.data["data"]["resources"]), 2)

        lesson = Lesson.objects.get(title="Lesson One")
        self.assertEqual(lesson.module, self.module)
        self.assertEqual(lesson.body_content, "<p><strong>Bold</strong> and <em>italic</em> text.</p>")
        self.assertEqual(lesson.resources.count(), 2)

        image_resource = LessonResource.objects.get(lesson=lesson, content_type="image")
        self.assertIn("diagram", image_resource.file.name)
        self.assertTrue(image_resource.file.name.endswith(".png"))

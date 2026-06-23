from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.teacher_dashboard.models import TeacherProfile

from .models import (
    Category,
    Course,
    CourseEnrollment,
    CourseQuiz,
    CourseQuizQuestion,
    Lesson,
    LessonResource,
    Module,
    Subcategory,
)
from .templatetags.content_render import render_stored_content


User = get_user_model()


class PurchaseAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='student@example.com', password='testpass123')
        self.teacher_user = User.objects.create_user(email='teacher@example.com', password='testpass123')
        self.teacher_profile = TeacherProfile.objects.create(user=self.teacher_user, full_name='Teacher', phone_number='01234567890')
        self.category = Category.objects.create(name="Programming", slug="programming")
        self.subcategory = Subcategory.objects.create(category=self.category, name="Python", slug="python")
        self.course = Course.objects.create(
            subcategory=self.subcategory,
            teacher=self.teacher_profile,
            name='Python Basics',
            slug='python-basics',
            price=999,
        )
        self.module = Module.objects.create(course=self.course, title='Module 1', slug='module-1')
        self.lesson = Lesson.objects.create(
            module=self.module,
            title='Lesson 1',
            slug='lesson-1',
            body_content='<p>Lesson body</p>',
            is_preview=True,
        )
        self.quiz = CourseQuiz.objects.create(lesson=self.lesson, module=self.module, title='Quiz 1', pass_score=50)
        CourseQuizQuestion.objects.create(
            quiz=self.quiz,
            question='What is Python?',
            option_a='A snake',
            option_b='A programming language',
            option_c='A car',
            option_d='A game',
            correct_option='B',
        )
        self.course_url = reverse('content:course_detail', args=[self.course.slug])

    def test_pending_purchase_still_shows_course_page(self):
        self.client.force_login(self.user)

        response = self.client.get(self.course_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'content/course_detail.html')

    def test_completed_purchase_grants_course_access(self):
        self.client.force_login(self.user)
        CourseEnrollment.objects.create(user=self.user, course=self.course)

        response = self.client.get(self.course_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'content/course_detail.html')

    def test_course_page_contains_collapsible_module_content(self):
        response = self.client.get(self.course_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.module.title)
        self.assertContains(response, self.lesson.title)
        self.assertContains(response, self.quiz.title)

    def test_preview_lesson_is_accessible_without_enrollment(self):
        response = self.client.get(
            reverse('content:lesson_detail', args=[self.course.slug, self.module.slug, self.lesson.slug])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'content/lesson_detail.html')
        self.assertContains(response, 'Lesson body')

    def test_quiz_submission_records_score(self):
        self.client.force_login(self.user)
        CourseEnrollment.objects.create(user=self.user, course=self.course)

        response = self.client.post(
            reverse('content:quiz_detail', args=[self.course.slug, self.module.slug, self.lesson.slug, self.quiz.id]),
            data={f'question_{self.quiz.questions.first().id}': 'B'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Score: 100%')

    def test_quiz_question_preserves_line_breaks(self):
        self.client.force_login(self.user)
        CourseEnrollment.objects.create(user=self.user, course=self.course)
        question = self.quiz.questions.first()
        question.question = "Choose the best answer:\nLine two"
        question.save(update_fields=["question"])

        response = self.client.get(
            reverse('content:quiz_detail', args=[self.course.slug, self.module.slug, self.lesson.slug, self.quiz.id])
        )

        self.assertContains(response, 'Choose the best answer:<br>Line two')


class StaffEditorTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email='admin@example.com',
            password='adminpass123',
            is_staff=True,
        )
        self.teacher_user = User.objects.create_user(email='teacher-staff@example.com', password='testpass123')
        self.teacher_profile = TeacherProfile.objects.create(user=self.teacher_user, full_name='Teacher', phone_number='01234567890')
        self.category = Category.objects.create(name="Programming", slug="programming-staff")
        self.subcategory = Subcategory.objects.create(category=self.category, name="Python", slug="python-staff")
        self.course = Course.objects.create(
            subcategory=self.subcategory,
            teacher=self.teacher_profile,
            name='Python Advanced',
            slug='python-advanced',
            price=999,
        )
        self.module = Module.objects.create(course=self.course, title='Module 1', slug='module-1')
        self.lesson = Lesson.objects.create(
            module=self.module,
            title='Lesson 1',
            slug='lesson-1',
            body_content='<p>Lesson body</p>',
            is_preview=True,
        )

    def test_staff_can_open_lesson_editor(self):
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse('content:lesson_editor', args=[self.course.slug, self.module.slug, self.lesson.slug])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lesson Editor')
        self.assertContains(response, self.lesson.title)

    def test_lesson_editor_save_updates_lesson_only(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse('content:api_lesson_save', args=[self.lesson.id]),
            data='{"title":"Lesson 1 Updated","body_content":"<p>Updated lesson</p>"}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.lesson.refresh_from_db()
        self.module.refresh_from_db()
        self.assertEqual(self.lesson.title, 'Lesson 1 Updated')
        self.assertEqual(self.lesson.body_content, '<p>Updated lesson</p>')
        self.assertEqual(self.module.title, 'Module 1')


class ContentRenderTests(TestCase):
    def test_plain_text_preserves_line_breaks(self):
        rendered = str(render_stored_content('Line one\nLine two'))

        self.assertIn('Line one<br>Line two', rendered)

    def test_html_content_is_preserved(self):
        html = '<p><strong>Target Persona</strong></p>'

        self.assertEqual(str(render_stored_content(html)), html)

    def test_highlight_link_gets_variant_class_from_multimedia_content(self):
        teacher_user = User.objects.create_user(email='teacher-render@example.com', password='testpass123')
        teacher_profile = TeacherProfile.objects.create(user=teacher_user, full_name='Teacher', phone_number='01234567890')
        category = Category.objects.create(name="Media", slug="media")
        subcategory = Subcategory.objects.create(category=category, name="Audio", slug="audio")
        course = Course.objects.create(subcategory=subcategory, teacher=teacher_profile, name='Media Course', slug='media-course')
        module = Module.objects.create(course=course, title='Lesson 1', slug='lesson-1', body_content='')
        lesson = Lesson.objects.create(module=module, title="Intro Lesson", slug="intro-lesson", body_content="")
        item = LessonResource.objects.create(
            lesson=lesson,
            title='Sample Audio',
            slug="sample-audio",
            content_type='audio',
        )
        html = f'<p>Click <span data-content-id="{item.id}">this word</span></p>'

        rendered = str(render_stored_content(html))

        self.assertIn('class="highlight-link highlight-link--audio"', rendered)
        self.assertIn(f'data-content-id="{item.id}"', rendered)

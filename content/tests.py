from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Course, CourseContent, Module, ModulePurchase
from .templatetags.content_render import render_stored_content


User = get_user_model()


class PurchaseAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='student', email='student@example.com', password='testpass123')
        self.course = Course.objects.create(
            name='Python Basics',
            slug='python-basics',
            price=999,
        )
        self.course_url = reverse('content:course_detail', args=[self.course.slug])

    def test_pending_purchase_still_shows_course_page(self):
        self.client.force_login(self.user)
        ModulePurchase.objects.create(user=self.user, course=self.course, is_purchased=False)

        response = self.client.get(self.course_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'content/course_detail.html')

    def test_completed_purchase_grants_course_access(self):
        self.client.force_login(self.user)
        ModulePurchase.objects.create(user=self.user, course=self.course, is_purchased=True)

        response = self.client.get(self.course_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'content/course_detail.html')


class ContentRenderTests(TestCase):
    def test_plain_text_preserves_line_breaks(self):
        rendered = str(render_stored_content('Line one\nLine two'))

        self.assertIn('Line one<br>Line two', rendered)

    def test_html_content_is_preserved(self):
        html = '<p><strong>Target Persona</strong></p>'

        self.assertEqual(str(render_stored_content(html)), html)

    def test_highlight_link_gets_variant_class_from_multimedia_content(self):
        course = Course.objects.create(name='Media Course', slug='media-course')
        module = Module.objects.create(course=course, title='Lesson 1', slug='lesson-1', body_content='')
        item = CourseContent.objects.create(
            module=module,
            title='Sample Audio',
            content_type='audio',
        )
        html = f'<p>Click <span data-content-id="{item.id}">this word</span></p>'

        rendered = str(render_stored_content(html))

        self.assertIn('class="highlight-link highlight-link--audio"', rendered)
        self.assertIn(f'data-content-id="{item.id}"', rendered)


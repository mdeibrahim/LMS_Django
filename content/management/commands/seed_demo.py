from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from content.models import (
    Category,
    Course,
    CourseQuiz,
    CourseQuizQuestion,
    Lesson,
    LessonResource,
    LessonResourceType,
    Module,
    ModuleAccordionSection,
    Subcategory,
)


SEED_DATA = [
    {
        "course": {
            "slug": "crime-reporting",
            "name": "Crime Reporting",
            "description": "Covering criminal investigations and court proceedings.",
            "price": "299.00",
        },
        "modules": [
            {
                "slug": "intro-context",
                "title": "Introduction & Context",
                "description": "Overview and background of the case.",
                "order": 1,
                "contents": [
                    {
                        "title": "Overview of the Case",
                        "order": 1,
                        "video_url": "https://youtu.be/M7lc1UVf-VE",
                        "duration_seconds": 480,
                    },
                    {
                        "title": "Timeline & Key Events",
                        "order": 2,
                        "video_url": "https://youtu.be/dQw4w9WgXcQ",
                        "duration_seconds": 420,
                    },
                ],
                "accordions": [
                    {
                        "title": "Quick Checklist",
                        "content": "<p>Audience define করুন, ৩টা content pillar লিখুন, আর একটি clear CTA ঠিক করুন।</p>",
                        "order": 1,
                        "is_open_by_default": True,
                    },
                    {
                        "title": "Common Mistakes",
                        "content": "<p>একসাথে সব platform-এ না গিয়ে প্রথমে একটি channel-এ consistent execution করুন।</p>",
                        "order": 2,
                        "is_open_by_default": False,
                    },
                ],
                "quizzes": [
                    {
                        "title": "Introduction Quiz",
                        "pass_score": 50,
                        "is_active": True,
                        "questions": [
                            {
                                "order": 1,
                                "question": "Which piece of evidence was central to the arrest?",
                                "option_a": "CCTV footage",
                                "option_b": "Witness testimony",
                                "option_c": "Recovered jewelry",
                                "option_d": "None of the above",
                                "correct_option": "A",
                            }
                        ],
                    }
                ],
            },
            {
                "slug": "case-analysis",
                "title": "Case Analysis",
                "description": "Detailed walkthrough and evidence analysis.",
                "order": 2,
                "contents": [
                    {
                        "title": "CCTV Footage Breakdown",
                        "order": 1,
                        "video_url": "https://youtu.be/IcrbM1l_BoI",
                        "duration_seconds": 510,
                    }
                ],
                "quizzes": [
                    {
                        "title": "Analysis Quiz",
                        "pass_score": 60,
                        "is_active": True,
                        "questions": [
                            {
                                "order": 1,
                                "question": "What analysis helped identify suspects?",
                                "option_a": "Timeline cross-check",
                                "option_b": "CCTV enhancement",
                                "option_c": "Forensic lab test",
                                "option_d": "Social media tracing",
                                "correct_option": "B",
                            }
                        ],
                    }
                ],
            },
        ],
    },
    {
        "course": {
            "slug": "digital-marketing-basics",
            "name": "Digital Marketing Basics",
            "description": "Learn SEO, social media and campaign fundamentals.",
            "price": "0.00",
        },
        "modules": [
            {
                "slug": "marketing-foundations",
                "title": "Marketing Foundations",
                "description": "Core digital marketing concepts and funnel basics.",
                "order": 1,
                "body_content": """<p>
ডিজিটাল মার্কেটিং শুরু করার আগে আপনার অডিয়েন্স, লক্ষ্য এবং অফার পরিষ্কারভাবে নির্ধারণ করুন।
তারপর একটি সহজ ফানেল বানান: Awareness → Consideration → Conversion।
</p>

<p>
এই মডিউলের লক্ষ্য হলো এমন একটি ভিত্তি তৈরি করা, যেটা পরবর্তী SEO, কনটেন্ট এবং সোশ্যাল ক্যাম্পেইনে ব্যবহার করা যাবে।
আপনি চাইলে এই লেখা Admin থেকে বা API দিয়ে পরবর্তীতে সম্পাদনা করতে পারবেন।
</p>

<p>
প্রতিটি লেসনের শেষে ছোট চেকলিস্ট রাখুন: কী শিখলাম, কী ইমপ্লিমেন্ট করলাম, আর পরের ধাপ কী।
</p>""",
                "contents": [
                    {
                        "title": "What is Digital Marketing?",
                        "order": 1,
                        "video_url": "https://youtu.be/9gTw2EDkaDQ",
                        "duration_seconds": 360,
                    },
                    {
                        "title": "Building a Basic Funnel",
                        "order": 2,
                        "video_url": "https://youtu.be/tAGnKpE4NCI",
                        "duration_seconds": 540,
                    },
                    {
                        "title": "Content Calendar Planning",
                        "order": 3,
                        "video_url": "https://youtu.be/5MgBikgcWnY",
                        "duration_seconds": 390,
                    },
                    {
                        "title": "Marketing Strategy Notes (Editable)",
                        "content_type": "text",
                        "order": 4,
                        "text_content": """<p>
এই অংশটি text content হিসেবে রাখা হয়েছে, যাতে আপনি editor/API দিয়ে সহজে update করতে পারেন।
</p>
<p>
উদাহরণ: <strong>Target Persona</strong>, <em>Content Pillars</em>, এবং CTA পরিকল্পনা এখানে লিখে রাখতে পারেন।
</p>""",
                    },
                ],
                "quizzes": [
                    {
                        "title": "Foundations Quiz",
                        "pass_score": 55,
                        "is_active": True,
                        "questions": [
                            {
                                "order": 1,
                                "question": "Which stage usually comes first in a funnel?",
                                "option_a": "Retention",
                                "option_b": "Awareness",
                                "option_c": "Advocacy",
                                "option_d": "Conversion",
                                "correct_option": "B",
                            }
                        ],
                    }
                ],
            },
            {
                "slug": "seo-social",
                "title": "SEO and Social Media",
                "description": "Ranking basics, keywords, and social content planning.",
                "order": 2,
                "contents": [
                    {
                        "title": "Keyword Research Essentials",
                        "order": 1,
                        "video_url": "https://youtu.be/OPf0YbXqDm0",
                        "duration_seconds": 450,
                    }
                ],
                "quizzes": [],
            },
        ],
    },
    {
        "course": {
            "slug": "python-for-beginners",
            "name": "Python for Beginners",
            "description": "Start coding with Python from zero to practical scripts.",
            "price": "399.00",
        },
        "modules": [
            {
                "slug": "python-setup",
                "title": "Setup and First Script",
                "description": "Install Python and write your first program.",
                "order": 1,
                "contents": [
                    {
                        "title": "Installing Python and VS Code",
                        "order": 1,
                        "video_url": "https://youtu.be/fLexgOxsZu0",
                        "duration_seconds": 600,
                    },
                    {
                        "title": "Hello World and Variables",
                        "order": 2,
                        "video_url": "https://youtu.be/kXYiU_JCYtU",
                        "duration_seconds": 520,
                    },
                ],
                "quizzes": [
                    {
                        "title": "Python Basics Quiz",
                        "pass_score": 60,
                        "is_active": True,
                        "questions": [
                            {
                                "order": 1,
                                "question": "Which keyword declares a function in Python?",
                                "option_a": "func",
                                "option_b": "def",
                                "option_c": "function",
                                "option_d": "lambda",
                                "correct_option": "B",
                            }
                        ],
                    }
                ],
            },
            {
                "slug": "python-control-flow",
                "title": "Control Flow and Loops",
                "description": "If/else, loops, and practical examples.",
                "order": 2,
                "contents": [
                    {
                        "title": "If Else in Practice",
                        "order": 1,
                        "video_url": "https://youtu.be/l482T0yNkeo",
                        "duration_seconds": 430,
                    }
                ],
                "quizzes": [],
            },
        ],
    },
]


class Command(BaseCommand):
    help = "Seed multiple demo courses. Existing records are updated instead of duplicated."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Seeding demo courses..."))

        category, _ = Category.objects.get_or_create(
            slug="demo-courses",
            defaults={
                "name": "Demo Courses",
                "description": "Default demo category for seeded LMS content.",
            },
        )
        subcategory, _ = Subcategory.objects.get_or_create(
            category=category,
            slug="general",
            defaults={
                "name": "General",
                "description": "Default subcategory for seeded demo courses.",
            },
        )

        course_count = 0
        module_count = 0
        lesson_count = 0
        resource_count = 0
        quiz_count = 0
        question_count = 0

        for item in SEED_DATA:
            course_data = item["course"]
            course, _ = Course.objects.update_or_create(
                slug=course_data["slug"],
                defaults={
                    "subcategory": subcategory,
                    "name": course_data["name"],
                    "description": course_data["description"],
                    "price": course_data["price"],
                },
            )
            course_count += 1

            for module_data in item["modules"]:
                module, _ = Module.objects.update_or_create(
                    course=course,
                    slug=module_data["slug"],
                    defaults={
                        "title": module_data["title"],
                        "description": module_data["description"],
                        "order": module_data["order"],
                        "body_content": module_data.get("body_content", ""),
                    },
                )
                module_count += 1
                lesson, _ = Lesson.objects.update_or_create(
                    module=module,
                    slug=f"{module.slug}-lesson",
                    defaults={
                        "title": module.title,
                        "description": module.description,
                        "body_content": module.body_content,
                        "order": module.order,
                        "is_published": True,
                    },
                )
                lesson_count += 1

                for content_data in module_data["contents"]:
                    inferred_type = content_data.get("content_type", LessonResourceType.VIDEO)
                    if inferred_type == "youtube":
                        inferred_type = LessonResourceType.VIDEO

                    video_url = content_data.get("video_url", "")
                    external_url = video_url if video_url else content_data.get("external_url", "")
                    embed_url = video_url if "youtu" in video_url else content_data.get("embed_url", "")

                    resource, _ = LessonResource.objects.update_or_create(
                        lesson=lesson,
                        title=content_data["title"],
                        defaults={
                            "slug": slugify(content_data["title"]) or f"resource-{content_data['order']}",
                            "content_type": inferred_type,
                            "order": content_data["order"],
                            "duration_seconds": content_data.get("duration_seconds", 0),
                            "text_content": content_data.get("text_content", ""),
                            "external_url": external_url,
                            "embed_url": embed_url,
                            "is_published": True,
                        },
                    )
                    resource_count += 1

                    if resource.content_type == LessonResourceType.QUIZ:
                        resource.is_preview = False
                        resource.save(update_fields=["is_preview"])

                for section_data in module_data.get("accordions", []):
                    ModuleAccordionSection.objects.update_or_create(
                        module=module,
                        title=section_data["title"],
                        defaults={
                            "content": section_data.get("content", ""),
                            "order": section_data.get("order", 0),
                            "is_open_by_default": section_data.get("is_open_by_default", False),
                        },
                    )

                for quiz_data in module_data["quizzes"]:
                    quiz, _ = CourseQuiz.objects.update_or_create(
                        lesson=lesson,
                        title=quiz_data["title"],
                        defaults={
                            "module": module,
                            "pass_score": quiz_data["pass_score"],
                            "is_active": quiz_data["is_active"],
                        },
                    )
                    quiz_count += 1

                    for question_data in quiz_data["questions"]:
                        CourseQuizQuestion.objects.update_or_create(
                            quiz=quiz,
                            order=question_data["order"],
                            defaults={
                                "question": question_data["question"],
                                "option_a": question_data["option_a"],
                                "option_b": question_data["option_b"],
                                "option_c": question_data["option_c"],
                                "option_d": question_data["option_d"],
                                "correct_option": question_data["correct_option"],
                            },
                        )
                        question_count += 1

            self.stdout.write(self.style.HTTP_INFO(f"Updated course: {course.name}"))

        self.stdout.write(
            self.style.SUCCESS(
                "\nSeed complete.\n"
                f"Courses processed: {course_count}\n"
                f"Modules processed: {module_count}\n"
                f"Lessons processed: {lesson_count}\n"
                f"Lesson resources processed: {resource_count}\n"
                f"Quizzes processed: {quiz_count}\n"
                f"Quiz questions processed: {question_count}\n"
            )
        )

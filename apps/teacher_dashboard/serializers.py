from django.contrib.auth import authenticate, get_user_model
import json
from django.db import transaction
from django.utils.text import slugify
from rest_framework import serializers, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.teacher_dashboard.models import TeacherProfile
from content.models import Category, Course, Lesson, LessonResource, LessonResourceType, Module, Subcategory, UserRole, CourseQuiz, CourseQuizQuestion


User = get_user_model()

class TeacherRegisterSerializer(serializers.Serializer):
    email_or_phone = serializers.CharField()
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    full_name = serializers.CharField()

    @staticmethod
    def _is_phone(value: str) -> bool:
        normalized = value.replace(" ", "").replace("-", "")
        if normalized.startswith("+"):
            normalized = normalized[1:]
        return normalized.isdigit() and 10 <= len(normalized) <= 15

    def validate_email_or_phone(self, value):
        if self._is_phone(value):
            normalized = value.replace(" ", "").replace("-", "")
            if User.objects.filter(phone_number=normalized).exists():
                raise serializers.ValidationError("Phone number is already in use")
            return value
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError("Email is already in use")
        return value.lower()

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match"}
            )

        contact = attrs["email_or_phone"]
        if self._is_phone(contact):
            normalized = contact.replace(" ", "").replace("-", "")
            if not (10 <= len(normalized) <= 15):
                raise serializers.ValidationError(
                    {"email_or_phone": "Phone number must be 10 to 15 digits."}
                )

        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_password")
        contact = validated_data.pop("email_or_phone")

        if self._is_phone(contact):
            normalized = contact.replace(" ", "").replace("-", "")
            user = User.objects.create_user(
                phone_number=normalized,
                password=validated_data["password"],
                full_name=validated_data["full_name"],
                role=UserRole.TEACHER,
            )
        else:
            user = User.objects.create_user(
                email=contact.lower(),
                password=validated_data["password"],
                full_name=validated_data["full_name"],
                role=UserRole.TEACHER,
            )

        TeacherProfile.objects.get_or_create(user=user)
        return user
    

class TeacherLoginSerializer(serializers.Serializer):
    email_or_phone = serializers.CharField()
    password = serializers.CharField(write_only=True)

    @staticmethod
    def _is_phone(value: str) -> bool:
        normalized = value.replace(" ", "").replace("-", "")
        if normalized.startswith("+"):
            normalized = normalized[1:]
        return normalized.isdigit() and 10 <= len(normalized) <= 15

    def validate(self, data):
        contact = data.get("email_or_phone")
        password = data.get("password")

        if self._is_phone(contact):
            username = contact.replace(" ", "").replace("-", "")
            user = authenticate(username=username, password=password)
        else:
            user = authenticate(username=contact.lower(), password=password)

        if not user:
            raise serializers.ValidationError(
                {"detail": "Invalid credentials"}
            )

        try:
            profile_role = user.profile.role
        except Exception:
            profile_role = None
        if profile_role != UserRole.TEACHER and not user.is_staff:
            raise serializers.ValidationError(
                {"detail": "Teacher account required"}
            )

        if not user.is_active:
            raise serializers.ValidationError(
                {"detail": "Account is inactive"}
            )

        data["user"] = user
        return data


class TeacherProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = TeacherProfile
        fields = (
            "id",
            "full_name",
            "email",
            "phone_number",
            "address",
            "bio",
            "profile_picture",
            "teacher_institution",
            "teacher_subject",
            "teacher_experience_years",
            "created_at",
        )
        read_only_fields = ("email",)

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        email = user_data.get("email")

        if email and email != instance.user.email:
            if User.objects.filter(email=email).exists():
                raise serializers.ValidationError({"email": "Email is already in use"})
            instance.user.email = email
            instance.user.save(update_fields=["email"])

        return super().update(instance, validated_data)
    

# Category Subcategory Serializer
class CategorySubcategorySerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField()
 
    class Meta:
        model = Category
        fields = ("id", "name", "subcategories")
 
    def get_subcategories(self, obj):
        subcategories = obj.subcategories.all()
        return SubcategorySerializer(subcategories, many=True).data
 
class SubcategorySerializer(serializers.ModelSerializer):
 
    class Meta:
        model = Subcategory
        fields = (
            "id",
            "name",
            "category",
            "description",
            "created_at",
        )
        read_only_fields = ("created_at",)
 
    def get_unique_together_validators(self):
        return []
 
    def validate_category(self, value):
        request = self.context.get("request")
 
        teacher_profile = getattr(
            getattr(request, "user", None),
            "teacher_profile",
            None
        )
 
        if teacher_profile and not teacher_profile.assigned_categories.filter(
            pk=value.pk
        ).exists():
            raise serializers.ValidationError(
                "Selected category is not assigned to this teacher."
            )
 
        return value
 
    def validate(self, attrs):
        # PATCH/partial update এ category বা name না পাঠালে instance থেকে ফলব্যাক করা
        category = attrs.get(
            "category",
            getattr(self.instance, "category", None)
        )
        name = attrs.get(
            "name",
            getattr(self.instance, "name", None)
        )
 
        duplicate_qs = Subcategory.objects.filter(
            category=category,
            name__iexact=name
        )
 
        # Update এর ক্ষেত্রে নিজেকে বাদ দিয়ে চেক করা, নাহলে নিজের নাম দিয়েই
        # "already exists" এরর দেখাবে
        if self.instance is not None:
            duplicate_qs = duplicate_qs.exclude(pk=self.instance.pk)
 
        if duplicate_qs.exists():
            raise serializers.ValidationError(
                "subcategory already exist in this category"
            )
 
        return attrs
 
    def create(self, validated_data):
        return Subcategory.objects.create(**validated_data)
 
class CategorySimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name")
 
class SubcategorySimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subcategory
        fields = ("id", "name")


# Course Serializer
class CourseSerializer(serializers.ModelSerializer):
    # --- write fields (accept IDs on POST/PATCH) ---
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    subcategory = serializers.PrimaryKeyRelatedField(
        queryset=Subcategory.objects.all(),
        required=False,
        allow_null=True,
    )

    slug = serializers.SlugField(read_only=True)
    modules_count = serializers.IntegerField(source="modules.count", read_only=True)

    class Meta:
        model = Course
        fields = (
            "id",
            "name",
            "slug",
            "category",
            "subcategory",
            "description",
            "cover_image",
            "price",
            "enrollment_count",
            "is_published",
            "created_at",
            "modules_count",
        )

    def to_representation(self, instance):
        """Return nested objects on read instead of plain IDs."""
        data = super().to_representation(instance)
        # subcategory → nested object
        if instance.subcategory:
            data["subcategory"] = SubcategorySimpleSerializer(instance.subcategory).data
        else:
            data["subcategory"] = None
        # category → derived from subcategory
        if instance.subcategory and instance.subcategory.category_id:
            cat = instance.subcategory.category
            data["category"] = {"id": cat.id, "name": cat.name}
        else:
            data["category"] = None
        return data

    def _get_teacher_profile(self):
        request = self.context.get("request")
        return getattr(getattr(request, "user", None), "teacher_profile", None)

    def validate(self, attrs):
        teacher_profile = self._get_teacher_profile()
        category = attrs.get("category")
        subcategory = attrs.get("subcategory")

        if subcategory and not category:
            category = subcategory.category
            attrs["category"] = category

        if category and teacher_profile:
            if not teacher_profile.assigned_categories.filter(pk=category.pk).exists():
                raise serializers.ValidationError({"category": "Selected category is not assigned to this teacher."})

        if subcategory:
            if category and subcategory.category_id != category.pk:
                raise serializers.ValidationError({"subcategory": "Selected subcategory must belong to the selected category."})

            if teacher_profile and not teacher_profile.assigned_categories.filter(pk=subcategory.category_id).exists():
                raise serializers.ValidationError({"subcategory": "Selected subcategory is not assigned to this teacher."})

        if not category:
            if teacher_profile:
                category = teacher_profile.assigned_categories.order_by("name").first()
                if not category:
                    raise serializers.ValidationError({"category": "At least one assigned category is required."})
                attrs["category"] = category
            else:
                raise serializers.ValidationError({"category": "Category is required."})

        if not subcategory:
            subcategory = category.subcategories.filter(slug="all").first()
            if subcategory is None:
                subcategory = category.ensure_default_subcategory()
            attrs["subcategory"] = subcategory

        return attrs

    def _generate_unique_slug(self, name):
        base_slug = slugify(name) or "course"
        slug = base_slug
        counter = 2
        while Course.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug

    def create(self, validated_data):
        teacher_profile = self.context["request"].user.teacher_profile
        validated_data.pop("category", None)
        subcategory = validated_data.pop("subcategory")
        validated_data["slug"] = self._generate_unique_slug(validated_data["name"])
        return Course.objects.create(
            teacher=teacher_profile,
            subcategory=subcategory,
            **validated_data
        )

    def update(self, instance, validated_data):
        validated_data.pop("category", None)  # category is derived from subcategory
        if "name" in validated_data:
            instance.slug = self._generate_unique_slug(validated_data["name"])
        return super().update(instance, validated_data)
    

# Module Serializer
class ModuleSerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(read_only=True)
    lesson_count = serializers.IntegerField(source="lessons.count", read_only=True)
    class Meta:
        model = Module
        fields = (
            "id",
            "title",
            "description",
            "order",
            "is_published",
            "slug",
            "lesson_count",
        )
        read_only_fields = ("id", "course", "slug", "lesson_count")


    def _generate_unique_slug(self, title):
        base_slug = slugify(title) or "module"
        slug = base_slug
        counter = 2
        while Module.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug

    def create(self, validated_data):
        course = validated_data["course"]
        validated_data["slug"] = self._generate_unique_slug(validated_data["title"])
        return Module.objects.create(**validated_data)
    
    def update(self, instance, validated_data):
        if "title" in validated_data:
            instance.slug = self._generate_unique_slug(validated_data["title"])
        return super().update(instance, validated_data)
    

# Lesson Serializer
class LessonResourceSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    youtube_embed_url = serializers.SerializerMethodField()
    youtube_url = serializers.ReadOnlyField()

    class Meta:
        model = LessonResource
        fields = (
            "id",
            "title",
            "slug",
            "content_type",
            "order",
            "is_preview",
            "is_published",
            "text_content",
            "file_url",
            "youtube_url",
            "youtube_embed_url",
            "external_url",
            "embed_url",
            "created_at",
        )

    def get_file_url(self, obj):
        if not obj.file:
            return ""
        request = self.context.get("request")
        url = obj.file.url
        if request is not None:
            return request.build_absolute_uri(url)
        return url

    def get_youtube_embed_url(self, obj):
        return obj.get_youtube_embed_url()

class LessonSerializer(serializers.ModelSerializer):
    resources = LessonResourceSerializer(many=True, read_only=True)
    module_title = serializers.CharField(source="module.title", read_only=True)
    course_id = serializers.IntegerField(source="module.course.id", read_only=True)
    course_title = serializers.CharField(source="module.course.name", read_only=True)
    course_slug = serializers.CharField(source="module.course.slug", read_only=True)

    class Meta:
        model = Lesson
        fields = (
            "id",
            "module",
            "module_title",
            "course_id",
            "course_title",
            "course_slug",
            "title",
            "slug",
            "description",
            "body_content",
            "order",
            "is_preview",
            "is_published",
            "created_at",
            "updated_at",
            "resources",
        )
        read_only_fields = ("id", "slug", "created_at", "updated_at", "resources")

class LessonCreateSerializer(serializers.ModelSerializer):
    resources = serializers.JSONField(required=False, write_only=True, default=list)

    class Meta:
        model = Lesson
        fields = (
            "id",
            "module",
            "title",
            "description",
            "body_content",
            "order",
            "is_preview",
            "is_published",
            "resources",
        )
        read_only_fields = ("id",)

    def validate_module(self, module):
        teacher_profile = getattr(getattr(self.context.get("request"), "user", None), "teacher_profile", None)
        if teacher_profile and module.course.teacher_id != teacher_profile.id:
            raise serializers.ValidationError("You can only add lessons to your own modules.")
        return module

    def validate_resources(self, resources):
        if resources in (None, ""):
            return []
        if isinstance(resources, str):
            try:
                resources = json.loads(resources)
            except Exception:
                raise serializers.ValidationError("resources must be valid JSON.")
        if not isinstance(resources, list):
            raise serializers.ValidationError("resources must be a list of media items.")
        allowed_types = {choice[0] for choice in LessonResourceType.choices}
        allowed_types.add("youtube")
        for resource in resources:
            content_type = str(resource.get("content_type") or LessonResourceType.TEXT).strip().lower()
            if content_type not in allowed_types:
                raise serializers.ValidationError(f"Unsupported content_type '{content_type}'.")
            if content_type == "youtube" and not (resource.get("youtube_url") or resource.get("external_url")):
                raise serializers.ValidationError("YouTube media items require a youtube_url or external_url.")
        return resources

    @transaction.atomic
    def create(self, validated_data):
        resources = validated_data.pop("resources", [])
        lesson = Lesson.objects.create(**validated_data)

        request = self.context.get("request")
        files = getattr(request, "FILES", {})

        for index, resource_data in enumerate(resources, start=1):
            file_key = (resource_data.get("file_key") or "").strip()
            uploaded_file = files.get(file_key) if file_key else None

            content_type = str(resource_data.get("content_type") or LessonResourceType.TEXT).strip().lower()
            if content_type == "youtube":
                content_type = LessonResourceType.VIDEO
            text_content = resource_data.get("text_content", "")
            external_url = resource_data.get("external_url", "") or resource_data.get("youtube_url", "") or resource_data.get("video_url", "")
            embed_url = resource_data.get("embed_url", "")

            if content_type == LessonResourceType.VIDEO and not embed_url:
                embed_url = external_url

            r_id = resource_data.get("id")
            
            kwargs = {
                "lesson": lesson,
                "title": (resource_data.get("title") or "Untitled").strip() or "Untitled",
                "content_type": content_type,
                "order": int(resource_data.get("order") or index),
                "is_preview": bool(resource_data.get("is_preview", lesson.is_preview)),
                "is_published": bool(resource_data.get("is_published", True)),
                "text_content": text_content,
                "external_url": external_url,
                "embed_url": embed_url,
                "duration_seconds": int(resource_data.get("duration_seconds") or 0),
            }
            if r_id:
                kwargs["id"] = int(r_id)

            resource = LessonResource.objects.create(**kwargs)

            if uploaded_file:
                resource.file = uploaded_file
                resource.save(update_fields=["file"])

        return lesson

    @transaction.atomic
    def update(self, instance, validated_data):
        resources_data = validated_data.pop("resources", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if resources_data is not None:
            request = self.context.get("request")
            files = getattr(request, "FILES", {})
            
            existing_resources = {r.id: r for r in instance.resources.all()}
            incoming_ids = [r.get("id") for r in resources_data if r.get("id")]
            
            for r_id, r in existing_resources.items():
                if r_id not in incoming_ids:
                    r.delete()

            for index, resource_data in enumerate(resources_data, start=1):
                r_id = resource_data.get("id")
                file_key = (resource_data.get("file_key") or "").strip()
                uploaded_file = files.get(file_key) if file_key else None
                
                content_type = str(resource_data.get("content_type") or LessonResourceType.TEXT).strip().lower()
                if content_type == "youtube":
                    content_type = LessonResourceType.VIDEO
                text_content = resource_data.get("text_content", "")
                external_url = resource_data.get("external_url", "") or resource_data.get("youtube_url", "") or resource_data.get("video_url", "")
                embed_url = resource_data.get("embed_url", "")

                if content_type == LessonResourceType.VIDEO and not embed_url:
                    embed_url = external_url

                if r_id and r_id in existing_resources:
                    resource = existing_resources[r_id]
                    resource.title = (resource_data.get("title") or "Untitled").strip() or "Untitled"
                    resource.content_type = content_type
                    resource.order = int(resource_data.get("order") or index)
                    resource.is_preview = bool(resource_data.get("is_preview", instance.is_preview))
                    resource.is_published = bool(resource_data.get("is_published", True))
                    resource.text_content = text_content
                    resource.external_url = external_url
                    resource.embed_url = embed_url
                    resource.duration_seconds = int(resource_data.get("duration_seconds") or 0)
                    
                    if uploaded_file:
                        resource.file = uploaded_file
                    resource.save()
                else:
                    kwargs = {
                        "lesson": instance,
                        "title": (resource_data.get("title") or "Untitled").strip() or "Untitled",
                        "content_type": content_type,
                        "order": int(resource_data.get("order") or index),
                        "is_preview": bool(resource_data.get("is_preview", instance.is_preview)),
                        "is_published": bool(resource_data.get("is_published", True)),
                        "text_content": text_content,
                        "external_url": external_url,
                        "embed_url": embed_url,
                        "duration_seconds": int(resource_data.get("duration_seconds") or 0),
                    }
                    if r_id:
                        kwargs["id"] = int(r_id)

                    resource = LessonResource.objects.create(**kwargs)

                    if uploaded_file:
                        resource.file = uploaded_file
                        resource.save(update_fields=["file"])

        return instance

    def to_internal_value(self, data):
        if hasattr(data, '_mutable'):
            was_mutable = data._mutable
            data._mutable = True
            if data.get("module_id") and not data.get("module"):
                data["module"] = data.get("module_id")
            data._mutable = was_mutable
            mutable_data = data
        else:
            mutable_data = dict(data)
            if mutable_data.get("module_id") and not mutable_data.get("module"):
                mutable_data["module"] = mutable_data.get("module_id")
        return super().to_internal_value(mutable_data)


# ----------------------------- Quiz Serializer -----------------------------
class CourseQuizQuestionSerializer(serializers.ModelSerializer):
    """Read-only representation of a question, used when returning quiz detail."""
    image = serializers.SerializerMethodField()
    explanation_image = serializers.SerializerMethodField()

    class Meta:
        model = CourseQuizQuestion
        fields = (
            "id",
            "question",
            "option_a",
            "option_b",
            "option_c",
            "option_d",
            "correct_option",
            "order",
            "image",
            "explanation",
            "explanation_image",
            "explanation_note",
            "explanation_video_url",
        )

    def get_image(self, obj):
        if not obj.image:
            return ""
        request = self.context.get("request")
        url = obj.image.url
        if request is not None:
            return request.build_absolute_uri(url)
        return url

    def get_explanation_image(self, obj):
        if not obj.explanation_image:
            return ""
        request = self.context.get("request")
        url = obj.explanation_image.url
        if request is not None:
            return request.build_absolute_uri(url)
        return url


class CourseQuizQuestionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseQuizQuestion
        fields = (
            "id",
            "quiz",
            "question",
            "option_a",
            "option_b",
            "option_c",
            "option_d",
            "correct_option",
            "order",
            "image",
            "explanation",
            "explanation_image",
            "explanation_note",
            "explanation_video_url",
        )
        read_only_fields = ("id",)


class CourseQuizListSerializer(serializers.ModelSerializer):
    """Read serializer — used for list, detail, and as the response after create/update."""

    questions = CourseQuizQuestionSerializer(many=True, read_only=True)
    lesson_title = serializers.CharField(
        source="lesson.title", read_only=True, default=None
    )
    module_title = serializers.CharField(
        source="module.title", read_only=True, default=None
    )
    course_title = serializers.SerializerMethodField()
    question_count = serializers.SerializerMethodField()
    attempts_count = serializers.SerializerMethodField()

    class Meta:
        model = CourseQuiz
        fields = (
            "id",
            "module",
            "module_title",
            "lesson",
            "lesson_title",
            "course_title",
            "title",
            "pass_score",
            "order",
            "is_active",
            "created_at",
            "question_count",
            "attempts_count",
            "questions",
        )

    def get_course_title(self, obj):
        course = None
        if obj.lesson_id and obj.lesson.module_id:
            course = obj.lesson.module.course
        elif obj.module_id:
            course = obj.module.course

        if course is None:
            return None

        # tolerate either `.name` or `.title` depending on your Course model
        return getattr(course, "name", None) or getattr(course, "title", None)

    def get_question_count(self, obj):
        # obj.questions is prefetched in the view, so this doesn't re-hit the DB
        return len(obj.questions.all())

    def get_attempts_count(self, obj):
        return obj.attempts.count()


class CourseQuizCreateSerializer(serializers.ModelSerializer):
    """Write serializer for create/update, accepts nested questions as JSON."""

    questions = serializers.JSONField(required=False, default=list)

    class Meta:
        model = CourseQuiz
        fields = (
            "id",
            "module",
            "lesson",
            "title",
            "pass_score",
            "order",
            "is_active",
            "questions",
        )
        read_only_fields = ("id",)

    # ---- ownership checks ----

    def _teacher_profile(self):
        request = self.context.get("request")
        return getattr(getattr(request, "user", None), "teacher_profile", None)

    def validate_module(self, value):
        teacher_profile = self._teacher_profile()
        if teacher_profile and value and value.course.teacher_id != teacher_profile.id:
            raise serializers.ValidationError(
                "You can only attach quizzes to your own modules."
            )
        return value

    def validate_lesson(self, value):
        teacher_profile = self._teacher_profile()
        if (
            teacher_profile
            and value
            and value.module.course.teacher_id != teacher_profile.id
        ):
            raise serializers.ValidationError(
                "You can only attach quizzes to your own lessons."
            )
        return value

    def validate_questions(self, value):
        if value in (None, ""):
            return []

        if not isinstance(value, list):
            raise serializers.ValidationError("questions must be a list of question objects.")

        required_fields = (
            "question",
            "option_a",
            "option_b",
            "option_c",
            "option_d",
            "correct_option",
        )

        for index, item in enumerate(value, start=1):
            if not isinstance(item, dict):
                raise serializers.ValidationError(f"Question #{index} must be an object.")

            missing = [field for field in required_fields if not str(item.get(field, "")).strip()]
            if missing:
                raise serializers.ValidationError(
                    f"Question #{index} is missing: {', '.join(missing)}."
                )

            correct_option = str(item.get("correct_option")).strip().upper()
            if correct_option not in {"A", "B", "C", "D"}:
                raise serializers.ValidationError(
                    f"Question #{index} has an invalid correct_option; must be A, B, C, or D."
                )

        return value

    def validate(self, attrs):
        module = attrs.get("module", getattr(self.instance, "module", None))
        lesson = attrs.get("lesson", getattr(self.instance, "lesson", None))

        if not module and not lesson:
            raise serializers.ValidationError(
                "A quiz must be linked to either a module or a lesson."
            )

        return attrs

    # ---- persistence ----

    def _save_questions(self, quiz, questions):
        from django.conf import settings
        request = self.context.get("request")
        files = getattr(request, "FILES", {}) if request else {}

        def clean_media_path(url):
            if not url:
                return None
            media_url = getattr(settings, "MEDIA_URL", "/media/")
            if "://" in url:
                url = url.split("://", 1)[1]
                if "/" in url:
                    url = "/" + url.split("/", 1)[1]
            if url.startswith(media_url):
                return url[len(media_url):]
            return url

        for index, item in enumerate(questions, start=1):
            image_key = item.get("image_key")
            explanation_image_key = item.get("explanation_image_key")

            uploaded_image = files.get(image_key) if image_key else None
            uploaded_explanation_image = files.get(explanation_image_key) if explanation_image_key else None

            question_obj = CourseQuizQuestion.objects.create(
                quiz=quiz,
                question=item.get("question", "").strip(),
                option_a=item.get("option_a", "").strip(),
                option_b=item.get("option_b", "").strip(),
                option_c=item.get("option_c", "").strip(),
                option_d=item.get("option_d", "").strip(),
                correct_option=str(item.get("correct_option")).strip().upper(),
                order=int(item.get("order") or index),
                explanation=item.get("explanation", "").strip(),
                explanation_note=item.get("explanation_note", "").strip(),
                explanation_video_url=item.get("explanation_video_url", "").strip(),
            )

            if uploaded_image:
                question_obj.image = uploaded_image
            elif item.get("image"):
                question_obj.image = clean_media_path(item.get("image"))

            if uploaded_explanation_image:
                question_obj.explanation_image = uploaded_explanation_image
            elif item.get("explanation_image"):
                question_obj.explanation_image = clean_media_path(item.get("explanation_image"))

            question_obj.save()

    @transaction.atomic
    def create(self, validated_data):
        questions = validated_data.pop("questions", [])
        quiz = CourseQuiz.objects.create(**validated_data)
        self._save_questions(quiz, questions)
        return quiz

    @transaction.atomic
    def update(self, instance, validated_data):
        # questions is popped separately so "not provided at all" (PATCH without
        # touching questions) is distinguishable from "provided as an empty list"
        questions = validated_data.pop("questions", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if questions is not None:
            instance.questions.all().delete()
            self._save_questions(instance, questions)

        return instance

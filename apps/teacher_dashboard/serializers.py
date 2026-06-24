from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from django.utils.text import slugify
from rest_framework import serializers
from apps.teacher_dashboard.models import TeacherProfile
from content.models import Category, Course, Lesson, LessonResource, LessonResourceType, Module, Subcategory, UserRole


User = get_user_model()

class TeacherRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    full_name = serializers.CharField()
    phone_number = serializers.CharField(required=True)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email is already in use")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match"}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_password")

        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            full_name=validated_data["full_name"],
            phone_number=validated_data["phone_number"],
            role=UserRole.TEACHER,
        )

        return user
    

class TeacherLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get("email")
        password = data.get("password")

        user = authenticate(email=email, password=password)

        if not user:
            raise serializers.ValidationError(
                {"detail": "Invalid email or password"}
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
        category = attrs["category"]
        name = attrs["name"]

        if Subcategory.objects.filter(
            category=category,
            name__iexact=name
        ).exists():
            raise serializers.ValidationError("subcategory already exist in this category")

        return attrs

    def create(self, validated_data):
        return Subcategory.objects.create(**validated_data)
    
        
class SubcategoryDisplayField(serializers.PrimaryKeyRelatedField):
    def use_pk_only_optimization(self):
        return False

    def to_representation(self, value):
        return value.name


class CategoryDisplayField(serializers.PrimaryKeyRelatedField):
    def use_pk_only_optimization(self):
        return False

    def get_attribute(self, instance):
        return instance.subcategory.category

    def to_representation(self, value):
        return value.name


class CourseSerializer(serializers.ModelSerializer):
    category = CategoryDisplayField(
        queryset=Category.objects.all(),
        required=False,
        allow_null=True,
    )
    subcategory = SubcategoryDisplayField(
        queryset=Subcategory.objects.select_related("category").all(),
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
            "duration_seconds",
            "metadata",
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
    course_title = serializers.CharField(source="module.course.name", read_only=True)
    course_slug = serializers.CharField(source="module.course.slug", read_only=True)

    class Meta:
        model = Lesson
        fields = (
            "id",
            "module",
            "module_title",
            "course_title",
            "course_slug",
            "title",
            "slug",
            "description",
            "body_content",
            "order",
            "duration_seconds",
            "thumbnail",
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
            "duration_seconds",
            "thumbnail",
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

            resource = LessonResource.objects.create(
                lesson=lesson,
                title=(resource_data.get("title") or "Untitled").strip() or "Untitled",
                content_type=content_type,
                order=int(resource_data.get("order") or index),
                is_preview=bool(resource_data.get("is_preview", lesson.is_preview)),
                is_published=bool(resource_data.get("is_published", True)),
                text_content=text_content,
                external_url=external_url,
                embed_url=embed_url,
                duration_seconds=int(resource_data.get("duration_seconds") or 0),
                metadata=resource_data.get("metadata") or {},
            )

            if uploaded_file:
                resource.file = uploaded_file
                resource.save(update_fields=["file"])

        return lesson

    def to_internal_value(self, data):
        mutable_data = data.copy() if hasattr(data, "copy") else dict(data)
        if mutable_data.get("module_id") and not mutable_data.get("module"):
            mutable_data["module"] = mutable_data["module_id"]
        return super().to_internal_value(mutable_data)

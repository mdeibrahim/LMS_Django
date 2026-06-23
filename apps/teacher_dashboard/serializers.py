from django.contrib.auth import authenticate, get_user_model
from django.utils.text import slugify
from rest_framework import serializers
from apps.teacher_dashboard.models import TeacherProfile
from content.models import Category, Course, Subcategory, UserRole


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
    

from django.utils.text import slugify
from rest_framework import serializers

from .models import Subcategory


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
            raise serializers.ValidationError({
                "name": "This subcategory already exists in this category."
            })

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

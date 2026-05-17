from django.contrib import admin
from django import forms
from django.utils import timezone
from unfold.admin import ModelAdmin, TabularInline
from django.urls import reverse
from django.utils.html import format_html
from .models import (
    User,
    Category,
    CourseCertificate,
    CourseQuiz,
    CourseQuizQuestion,
    CourseContent,
    Course,
    ModuleAccordionSection,
    PaymentInstruction,
    QuizAttempt,
    Subcategory,
    ModulePurchase,
    Module, UserProfile,
    StudentDeviceSession,
)

try:
    admin.site.unregister(User)
except Exception:
    pass

@admin.register(User)
class UserAdmin(ModelAdmin):
    list_display = ('username', 'email', 'is_staff', 'is_active', 'date_joined')
    search_fields = ('username', 'email')
    list_filter = ('is_staff', 'is_active', 'date_joined')
    date_hierarchy = 'date_joined'
    list_per_page = 30

    
class CourseInline(TabularInline):
    model = Course
    extra = 0
    show_change_link = True
    prepopulated_fields = {'slug': ('name',)}
    fields = ('name', 'slug', 'price', 'description')


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Subcategory)
class SubcategoryAdmin(ModelAdmin):
    list_display = ('name', 'slug', 'category')
    list_filter = ('category',)
    search_fields = ('name', 'slug', 'category__name')
    autocomplete_fields = ('category',)
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Course)
class CourseAdmin(ModelAdmin):
    list_display = ('name', 'price', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    date_hierarchy = 'created_at'
    list_per_page = 30

class CourseContentInline(TabularInline):
    model = CourseContent
    extra = 0
    show_change_link = True
    fields = ('title', 'content_type', 'text_content', 'image', 'audio', 'video', 'youtube_url', 'preview')
    readonly_fields = ('id', 'preview')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.filter(is_inline_reference=False)

    def preview(self, obj):
        if not obj.pk:
            return 'Save to preview'
        return CourseContentAdmin.preview(self, obj)
    preview.short_description = 'Preview'


class ModuleAccordionSectionInline(TabularInline):
    model = ModuleAccordionSection
    extra = 0
    show_change_link = True
    fields = ('title', 'order', 'is_open_by_default')



@admin.register(ModulePurchase)
class ModulePurchaseAdmin(ModelAdmin):
    list_display = ('id', 'user', 'course', 'module_price', 'purchased_at')
    list_select_related = ('user', 'course')
    list_filter = ('course', 'purchased_at')
    search_fields = ('user__username', 'user__email', 'course__name')
    autocomplete_fields = ('user', 'course')
    date_hierarchy = 'purchased_at'
    list_per_page = 30

    def module_price(self, obj):
        return obj.course.price
    module_price.short_description = 'Price'


@admin.register(UserProfile)
class UserProfileAdmin(ModelAdmin):
    list_display = ('user', 'role', 'full_name', 'phone_number', 'created_at', 'updated_at')
    list_filter = ('role', 'created_at')
    search_fields = ('user__username', 'user__email', 'full_name', 'phone_number')
    autocomplete_fields = ('user',)
    list_per_page = 30
    fieldsets = (
        ('Account', {'fields': ('user', 'role', 'full_name', 'phone_number')}),
        ('Student Fields', {'fields': ('student_institution', 'student_level')}),
        ('Audit', {'fields': ('created_at', 'updated_at')}),
    )
    readonly_fields = ('created_at', 'updated_at')


@admin.register(StudentDeviceSession)
class StudentDeviceSessionAdmin(ModelAdmin):
    list_display = ('user', 'jti', 'ip_address', 'created_at', 'expires_at', 'last_seen')
    search_fields = ('user__username', 'jti', 'ip_address')
    list_filter = ('created_at', 'expires_at')
    autocomplete_fields = ('user',)
    list_per_page = 50


class CourseQuizQuestionInline(TabularInline):
    model = CourseQuizQuestion
    extra = 0


@admin.register(CourseQuiz)
class CourseQuizAdmin(ModelAdmin):
    list_display = ('title', 'module', 'pass_score', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at', 'module__course')
    search_fields = ('title', 'module__title')
    autocomplete_fields = ('module',)
    inlines = [CourseQuizQuestionInline]


@admin.register(QuizAttempt)
class QuizAttemptAdmin(ModelAdmin):
    list_display = ('user', 'quiz', 'score', 'submitted_at')
    list_filter = ('submitted_at',)
    search_fields = ('user__username', 'quiz__title')
    autocomplete_fields = ('user', 'quiz')

@admin.register(CourseCertificate)
class CourseCertificateAdmin(ModelAdmin):
    list_display = ('user', 'course', 'certificate_code', 'issued_at')
    list_filter = ('issued_at', 'course')
    search_fields = ('user__username', 'course__name', 'certificate_code')
    autocomplete_fields = ('user', 'course')


@admin.register(Module)
class ModuleAdmin(ModelAdmin):
    list_display = ('title', 'course', 'frontend_editor_link')
    search_fields = ('title',)
    inlines = [CourseContentInline, ModuleAccordionSectionInline]
    readonly_fields = ('frontend_editor_link',)

    class ModuleForm(forms.ModelForm):
        class Meta:
            model = Module
            fields = '__all__'
            widgets = {
                'body_content': forms.Textarea(attrs={'class': 'rte-enabled', 'rows': 12}),
            }

    form = ModuleForm

    class Media:
        js = ('js/admin_rte.js',)
        css = {'all': ('css/admin_rte.css',)}


    fieldsets = (
        ('Basic Info', {
            'fields': ('course', 'title', 'slug', 'frontend_editor_link')
        }),
        ('Body Content', {
            'fields': ('body_content',),
            'description': (
                'Use HTML. To add an interactive highlight link, use: '
                '<code>&lt;span class="highlight-link" data-content-id="ID"&gt;your text&lt;/span&gt;</code> '
                'where ID is the CourseContent ID.'
            )
        }),
    )

    def content_count(self, obj):
        return obj.course_contents.filter(is_inline_reference=False).count()
    content_count.short_description = 'Interactive Items'

    def edit_contents_link(self, obj):
        url = f"{reverse('admin:content_coursecontent_changelist')}?module__id__exact={obj.id}"
        return format_html('<a href="{}">Manage Items</a>', url)
    edit_contents_link.short_description = 'Interactive Content'

    def frontend_editor_link(self, obj):
        if not obj.pk:
            return 'Save first'
        url = reverse('content:subject_editor', args=[obj.course.slug, obj.slug])
        return format_html('<a href="{}" target="_blank">Open Frontend Editor</a>', url)
    frontend_editor_link.short_description = 'Frontend Editor'



@admin.register(CourseContent)
class CourseContentAdmin(ModelAdmin):
    list_display = ('id', 'title', 'content_type', 'module', 'course', 'preview', 'created_at')
    list_select_related = ('module', 'module__course')
    list_filter = ('content_type', 'module__course', 'created_at')
    search_fields = ('title', 'text_content', 'youtube_url')
    autocomplete_fields = ('module',)
    date_hierarchy = 'created_at'
    list_per_page = 25
    readonly_fields = ('id', 'preview')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.filter(is_inline_reference=False)

    fieldsets = (
        ('Basic', {
            'fields': ('id', 'module', 'title', 'content_type')
        }),
        ('Text Content', {
            'fields': ('text_content',),
            'classes': ('collapse',),
        }),
        ('Media Files', {
            'fields': ('image', 'audio', 'video'),
            'classes': ('collapse',),
        }),
        ('YouTube', {
            'fields': ('youtube_url',),
            'classes': ('collapse',),
        }),
        ('Preview', {
            'fields': ('preview',),
        }),
    )

    class CourseContentForm(forms.ModelForm):
        class Meta:
            model = CourseContent
            fields = '__all__'
            widgets = {
                'text_content': forms.Textarea(attrs={'class': 'rte-enabled', 'rows': 8}),
            }

    form = CourseContentForm

    class Media:
        js = ('js/admin_rte.js',)
        css = {'all': ('css/admin_rte.css',)}

    def course(self, obj):
        return obj.module.course
    course.short_description = 'Course'
    course.admin_order_field = 'module__course__name'

    def preview(self, obj):
        if obj.content_type == 'image' and obj.image:
            return format_html('<img src="{}" style="max-height:100px;max-width:200px;border-radius:6px;" />', obj.image.url)
        if obj.content_type == 'audio' and obj.audio:
            return format_html('<audio controls style="max-width:300px;"><source src="{}"></audio>', obj.audio.url)
        if obj.content_type == 'video' and obj.video:
            return format_html('<video controls style="max-height:100px;max-width:200px;"><source src="{}"></video>', obj.video.url)
        if obj.content_type == 'youtube' and obj.youtube_url:
            return format_html('<a href="{}" target="_blank">▶ Open YouTube</a>', obj.youtube_url)
        if obj.content_type == 'text' and obj.text_content:
            return format_html('<div style="max-width:300px;overflow:hidden;font-size:12px;">{}</div>', obj.text_content[:200])
        return '—'
    preview.short_description = 'Preview'


@admin.register(PaymentInstruction)
class PaymentInstructionAdmin(ModelAdmin):
    list_display = ('id','payment_method_name',  'created_at')
    search_fields = ('payment_method_name',)
    class PaymentInstructionForm(forms.ModelForm):
        class Meta:
            model = PaymentInstruction
            fields = '__all__'
            widgets = {
                'details': forms.Textarea(attrs={'class': 'rte-enabled', 'rows': 8}),
            }

    form = PaymentInstructionForm

    class Media:
        js = ('js/admin_rte.js',)
        css = {'all': ('css/admin_rte.css',)}

# Customize admin site
admin.site.site_header = "Interactive Teaching Platform"
admin.site.site_title = "Teaching Platform Admin"
admin.site.index_title = "Content Management"

from django.urls import path
from .views import LoginView, RegisterView, TeacherProfileView, CourseListView, SubcategoryCreateView, CategorySubcategoryListView, ModuleListView


urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='teacher_register'),
    path('auth/login/', LoginView.as_view(), name='teacher_login'),
    path('profile/', TeacherProfileView.as_view(), name='teacher_profile'),
    path('update-profile/', TeacherProfileView.as_view(), name='teacher_update_profile'),

    path('category-subcategory-list/', CategorySubcategoryListView.as_view(), name='teacher_category_subcategory_list'),
    path('create-subcategory/', SubcategoryCreateView.as_view(), name='teacher_create_subcategory'),

    path('create-course/', CourseListView.as_view(), name='teacher_create_course'),
    path('course-list/', CourseListView.as_view(), name='teacher_course_list'),


    # Module URLs
    path('module-list/', ModuleListView.as_view(), name='teacher_module_list'),
    path('module-detail/', ModuleListView.as_view(), name='teacher_module_detail'),
    path('create-module/', ModuleListView.as_view(), name='teacher_create_module'),
    path('update-module/', ModuleListView.as_view(), name='teacher_update_module'),
    path('delete-module/', ModuleListView.as_view(), name='teacher_delete_module'),
]

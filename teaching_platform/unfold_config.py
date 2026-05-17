from django.urls import reverse_lazy

UNFOLD = {
    "SITE_TITLE": "Teaching Platform Admin",
    "SITE_HEADER": "Interactive Teaching Platform",
    "SITE_SYMBOL": "school",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Dashboard",
                "separator": False,
                "collapsible": False,
                "items": [
                    {
                        "title": "Overview",
                        "icon": "dashboard",
                        "link": reverse_lazy("admin_dashboard"),
                    },
                ],
            },
            {
                "title": "Content Management",
                "separator": True,
                "collapsible": False,
                "items": [
                    {
                        "title": "Categories",
                        "icon": "account_tree",
                        "link": reverse_lazy("admin:content_category_changelist"),
                    },
                    {
                        "title": "Subcategories",
                        "icon": "account_tree",
                        "link": reverse_lazy("admin:content_subcategory_changelist"),
                    },
                    {
                        "title": "Courses",
                        "icon": "account_tree",
                        "link": reverse_lazy("admin:content_course_changelist"),
                    },
                    {
                        "title": "Modules",
                        "icon": "menu_book",
                        "link": reverse_lazy("admin:content_module_changelist"),
                    },
                    {
                        "title": "Course Content",
                        "icon": "video_library",
                        "link": reverse_lazy("admin:content_coursecontent_changelist"),
                    },
                    {
                        "title": "Quizzes",
                        "icon": "quiz",
                        "link": reverse_lazy("admin:content_coursequiz_changelist"),
                    },
                    {
                        "title": "Quiz Attempts",
                        "icon": "fact_check",
                        "link": reverse_lazy("admin:content_quizattempt_changelist"),
                    },
                ],
            },
            {
                "title": "Platform",
                "separator": True,
                "collapsible": False,
                "items": [
                    {
                        "title": "Purchases",
                        "icon": "shopping_cart",
                        "link": reverse_lazy("admin:content_modulepurchase_changelist"),
                    },
                    {
                        "title": "Certificates",
                        "icon": "verified",
                        "link": reverse_lazy("admin:content_coursecertificate_changelist"),
                    },
                ],
            },
            {
                "title": "Authentication",
                "separator": True,
                "collapsible": False,
                "items": [
                    {
                        "title": "Users",
                        "icon": "person",
                        "link": reverse_lazy("admin:auth_user_changelist"),
                    },
                    {
                        "title": "User Profiles",
                        "icon": "badge",
                        "link": reverse_lazy("admin:content_userprofile_changelist"),
                    },
                    {
                        "title": "Groups",
                        "icon": "groups",
                        "link": reverse_lazy("admin:auth_group_changelist"),
                    },
                    {
                        "title": "Device Sessions",
                        "icon": "devices",
                        "link": reverse_lazy("admin:content_studentdevicesession_changelist"),
                    },
                ],
            },
            {
                "title": "Payment Instructions",
                "separator": True,
                "collapsible": False,
                "items": [
                    
                    {
                        "title": "Payment Instructions",
                        "icon": "account_tree",
                        "link": reverse_lazy("admin:content_paymentinstruction_changelist"),
                    },
                ],
            },
        ],
    },
}

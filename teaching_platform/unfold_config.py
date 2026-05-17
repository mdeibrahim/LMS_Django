from django.urls import reverse_lazy

UNFOLD = {
    "SITE_TITLE": "Teaching Platform Admin",
    "SITE_HEADER": "Interactive Teaching Platform",
    "SITE_SYMBOL": "auto_stories",
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
                "title": "Curriculum",
                "separator": True,
                "collapsible": False,
                "items": [
                    {
                        "title": "Categories",
                        "icon": "category",
                        "link": reverse_lazy("admin:content_category_changelist"),
                    },
                    {
                        "title": "Subcategories",
                        "icon": "segment",
                        "link": reverse_lazy("admin:content_subcategory_changelist"),
                    },
                    {
                        "title": "Courses",
                        "icon": "school",
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
                "title": "Commerce",
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
                "title": "People",
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
                    {
                        "title": "Email OTPs",
                        "icon": "mark_email_read",
                        "link": reverse_lazy("admin:content_emailotp_changelist"),
                    },
                ],
            },
            {
                "title": "Operations",
                "separator": True,
                "collapsible": False,
                "items": [
                    {
                        "title": "Payment Instructions",
                        "icon": "payments",
                        "link": reverse_lazy("admin:content_paymentinstruction_changelist"),
                    },
                ],
            },
        ],
    },
}

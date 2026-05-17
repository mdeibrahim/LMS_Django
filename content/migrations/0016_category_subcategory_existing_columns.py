from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0015_category_remove_course_teacher_subcategory_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='category',
                    name='description',
                    field=models.TextField(blank=True, default=''),
                ),
                migrations.AddField(
                    model_name='category',
                    name='created_at',
                    field=models.DateTimeField(auto_now_add=True),
                ),
                migrations.AddField(
                    model_name='subcategory',
                    name='description',
                    field=models.TextField(blank=True, default=''),
                ),
                migrations.AddField(
                    model_name='subcategory',
                    name='created_at',
                    field=models.DateTimeField(auto_now_add=True),
                ),
            ],
            database_operations=[],
        ),
    ]

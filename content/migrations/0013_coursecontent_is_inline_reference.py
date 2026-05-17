from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0012_alter_coursecontent_content_type_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='coursecontent',
            name='is_inline_reference',
            field=models.BooleanField(default=False),
        ),
    ]

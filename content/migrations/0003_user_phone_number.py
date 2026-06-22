from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0002_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="phone_number",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
    ]

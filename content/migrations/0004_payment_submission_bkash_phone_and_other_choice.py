# Generated manually because Django is not available in the current shell environment.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0003_coursequizquestion_explanation_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentsubmission",
            name="bkash_phone_number",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AlterField(
            model_name="paymentinstruction",
            name="payment_method_name",
            field=models.CharField(
                blank=True,
                choices=[
                    ("bkash", "Bkash"),
                    ("nagad", "Nagad"),
                    ("rocket", "Rocket"),
                    ("bank_transfer", "Bank Transfer"),
                    ("other", "Other"),
                ],
                default="other",
                max_length=20,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="paymentsubmission",
            name="payment_method",
            field=models.CharField(
                choices=[
                    ("bkash", "Bkash"),
                    ("nagad", "Nagad"),
                    ("rocket", "Rocket"),
                    ("bank_transfer", "Bank Transfer"),
                    ("other", "Other"),
                ],
                default="other",
                max_length=20,
            ),
        ),
    ]

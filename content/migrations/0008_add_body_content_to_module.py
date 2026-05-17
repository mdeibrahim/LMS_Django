from django.db import migrations


def add_body_content_if_missing(apps, schema_editor):
    connection = schema_editor.connection
    table_name = "content_module"

    with connection.cursor() as cursor:
        existing_columns = {
            column.name
            for column in connection.introspection.get_table_description(cursor, table_name)
        }
        if "body_content" not in existing_columns:
            cursor.execute("ALTER TABLE content_module ADD COLUMN body_content text NOT NULL DEFAULT '';")


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(add_body_content_if_missing, migrations.RunPython.noop),
    ]

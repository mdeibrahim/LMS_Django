from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0008_add_body_content_to_module'),
    ]

    def add_content_type_if_missing(apps, schema_editor):
        table_name = "content_coursecontent"
        existing_columns = {
            column.name for column in schema_editor.connection.introspection.get_table_description(schema_editor.connection.cursor(), table_name)
        }
        if "content_type" in existing_columns:
            return
        schema_editor.execute(
            "ALTER TABLE content_coursecontent "
            "ADD COLUMN content_type varchar(20) NOT NULL DEFAULT 'text';"
        )

    operations = [
        migrations.RunPython(add_content_type_if_missing, migrations.RunPython.noop),
    ]

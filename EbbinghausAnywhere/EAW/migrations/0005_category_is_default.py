# Generated by Django 5.1.3 on 2024-12-06 02:06

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("EAW", "0004_item_src_tts"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="is_default",
            field=models.BooleanField(default=False, editable=False),
        ),
    ]

# Generated by Django 5.1.3 on 2024-12-06 01:57

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("EAW", "0003_alter_category_user_alter_item_user_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="src_tts",
            field=models.URLField(
                blank=True,
                help_text="URL pointing to the TTS audio file (e.g., Baidu API TTS)",
                max_length=500,
                null=True,
            ),
        ),
    ]

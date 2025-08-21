from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("analytics", "0002_interestevent_searchquery_ip_searchquery_session_key_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="viewevent",
            name="path",
            field=models.CharField(max_length=255, blank=True, default=""),
        ),
        migrations.AddField(
            model_name="viewevent",
            name="url",
            field=models.URLField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="viewevent",
            name="user_agent",
            field=models.CharField(max_length=500, blank=True, default=""),
        ),
        migrations.AddField(
            model_name="viewevent",
            name="referer",
            field=models.CharField(max_length=1000, blank=True, default=""),
        ),
    ]

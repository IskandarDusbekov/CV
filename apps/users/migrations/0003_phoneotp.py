from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_companybranding'),
    ]

    operations = [
        migrations.CreateModel(
            name='PhoneOTP',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone', models.CharField(db_index=True, max_length=20)),
                ('otp_code', models.CharField(max_length=6)),
                ('session_key', models.CharField(blank=True, max_length=64)),
                ('telegram_chat_id', models.BigIntegerField(blank=True, null=True)),
                ('attempts', models.IntegerField(default=0)),
                ('is_verified', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
            ],
            options={
                'ordering': ('-created_at',),
            },
        ),
    ]

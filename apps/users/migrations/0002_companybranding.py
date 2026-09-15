from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CompanyBranding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Kompaniya nomi')),
                ('tagline', models.CharField(blank=True, max_length=200, verbose_name='Qisqa tavsif')),
                ('website', models.URLField(blank=True, verbose_name='Veb-sayt')),
                ('logo', models.ImageField(blank=True, null=True, upload_to='branding/', verbose_name='Logo')),
                ('footer_text', models.CharField(blank=True, help_text="Bo'sh qoldirsangiz avtomatik yaratiladi", max_length=300)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='company_branding',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Kompaniya brendingi',
                'verbose_name_plural': 'Kompaniya brendinglari',
            },
        ),
    ]

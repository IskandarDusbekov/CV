from django.db import migrations


def convert_legacy_templates(apps, schema_editor):
    CV = apps.get_model('cv', 'CV')
    CV.objects.filter(selected_template='free_classic').update(selected_template='classic')
    CV.objects.filter(selected_template='premium_modern').update(selected_template='modern')


class Migration(migrations.Migration):

    dependencies = [
        ('cv', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cv',
            name='selected_template',
            field=__import__('django.db.models', fromlist=['CharField']).CharField(
                choices=[
                    ('classic',   'Klassik'),
                    ('modern',    'Zamonaviy'),
                    ('creative',  'Kreativ'),
                    ('executive', 'Executive'),
                    ('minimal',   'Minimal'),
                    ('dark',      'Dark Mode'),
                    ('elegant',   'Elegant'),
                    ('free_classic',   'Free Classic (legacy)'),
                    ('premium_modern', 'Premium Modern (legacy)'),
                ],
                default='classic',
                max_length=50,
            ),
        ),
        migrations.RunPython(convert_legacy_templates, migrations.RunPython.noop),
    ]

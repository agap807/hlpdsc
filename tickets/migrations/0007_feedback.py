# Generated by Django 5.2.1 on 2025-05-25 20:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0006_emailsettings_notificationtemplate'),
    ]

    operations = [
        migrations.CreateModel(
            name='Feedback',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('feedback_type', models.CharField(choices=[('complaint', 'Жалоба'), ('suggestion', 'Предложение'), ('other', 'Другое')], default='suggestion', max_length=20, verbose_name='Тип обращения')),
                ('name', models.CharField(max_length=255, verbose_name='Ваше имя (или анонимно)')),
                ('email', models.EmailField(blank=True, max_length=254, null=True, verbose_name='Ваш Email (для возможной обратной связи)')),
                ('subject', models.CharField(max_length=255, verbose_name='Тема')),
                ('message', models.TextField(verbose_name='Текст обращения')),
                ('submitted_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата отправки')),
                ('is_reviewed', models.BooleanField(default=False, verbose_name='Рассмотрено')),
                ('reviewer_notes', models.TextField(blank=True, null=True, verbose_name='Заметки рассмотревшего (внутренние)')),
            ],
            options={
                'verbose_name': 'Жалоба или предложение',
                'verbose_name_plural': 'Жалобы и предложения',
                'ordering': ['-submitted_at'],
            },
        ),
    ]

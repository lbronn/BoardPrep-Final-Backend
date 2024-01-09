# Generated by Django 4.2.4 on 2024-01-09 18:55

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CorrectQuestions',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ],
        ),
        migrations.CreateModel(
            name='Difficulty',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(choices=[('1', 'Easy'), ('2', 'Medium'), ('3', 'Hard')], max_length=255, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='MockQuestions',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('question', models.TextField(max_length=512)),
                ('choiceA', models.CharField(max_length=255, verbose_name='A')),
                ('choiceB', models.CharField(max_length=255, verbose_name='B')),
                ('choiceC', models.CharField(max_length=255, verbose_name='C')),
                ('choiceD', models.CharField(max_length=255, verbose_name='D')),
                ('subject', models.CharField(max_length=255)),
                ('correctAnswer', models.CharField(max_length=255, verbose_name='Correct Answer')),
            ],
        ),
        migrations.CreateModel(
            name='MockTest',
            fields=[
                ('mocktestID', models.BigAutoField(primary_key=True, serialize=False)),
                ('mocktestName', models.CharField(max_length=200)),
                ('mocktestDescription', models.TextField()),
                ('mocktestDateCreated', models.DateField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='MockTestScores',
            fields=[
                ('mocktestScoreID', models.BigAutoField(primary_key=True, serialize=False)),
                ('score', models.FloatField()),
                ('feedback', models.TextField()),
                ('mocktestDateTaken', models.DateField(auto_now_add=True)),
                ('totalQuestions', models.IntegerField(default=0)),
                ('correct_questions', models.ManyToManyField(related_name='correct_in_tests', through='Mocktest.CorrectQuestions', to='Mocktest.mockquestions')),
                ('mocktest_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mocktest_scores', to='Mocktest.mocktest')),
            ],
        ),
    ]

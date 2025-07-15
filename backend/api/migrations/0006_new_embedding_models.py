# Generated manually for EasyRead embeddings refactor
# This migration creates the new ImageSet, Image, and Embedding models

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0005_imagemetadata_is_generated'),
    ]

    operations = [
        migrations.CreateModel(
            name='ImageSet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True)),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Image',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('filename', models.CharField(max_length=255)),
                ('original_path', models.CharField(max_length=500)),
                ('processed_path', models.CharField(blank=True, max_length=500)),
                ('description', models.TextField(blank=True)),
                ('file_format', models.CharField(choices=[('PNG', 'PNG'), ('SVG', 'SVG')], max_length=10)),
                ('file_size', models.IntegerField(blank=True, null=True)),
                ('width', models.IntegerField(blank=True, null=True)),
                ('height', models.IntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('set', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='api.imageset')),
            ],
            options={
                'ordering': ['set__name', 'filename'],
            },
        ),
        migrations.CreateModel(
            name='Embedding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('embedding_type', models.CharField(choices=[('image', 'Image Embedding'), ('text', 'Text Embedding')], max_length=10)),
                ('vector', models.JSONField()),
                ('model_name', models.CharField(default='openclip-vit-bigG-14', max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('image', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='embeddings', to='api.image')),
            ],
            options={
                'ordering': ['image', 'embedding_type'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='image',
            unique_together={('set', 'filename')},
        ),
        migrations.AlterUniqueTogether(
            name='embedding',
            unique_together={('image', 'embedding_type')},
        ),
    ]
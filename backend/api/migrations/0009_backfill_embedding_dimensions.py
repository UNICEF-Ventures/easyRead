# Generated data migration to backfill embedding dimensions

from django.db import migrations
import json


def backfill_embedding_dimensions(apps, schema_editor):
    """
    Backfill embedding_dimension field from existing vector data.
    """
    Embedding = apps.get_model('api', 'Embedding')
    
    for embedding in Embedding.objects.all():
        try:
            # Parse the vector to get its length
            if isinstance(embedding.vector, list):
                dimension = len(embedding.vector)
            elif isinstance(embedding.vector, str):
                # Parse JSON string
                vector_data = json.loads(embedding.vector)
                dimension = len(vector_data)
            else:
                # Default to 1280 if we can't determine
                dimension = 1280
            
            # Update the embedding_dimension field
            embedding.embedding_dimension = dimension
            embedding.save(update_fields=['embedding_dimension'])
            
        except Exception:
            # If parsing fails, use default dimension
            embedding.embedding_dimension = 1280
            embedding.save(update_fields=['embedding_dimension'])


def reverse_backfill_embedding_dimensions(apps, schema_editor):
    """
    Reverse migration - nothing to do since we're just setting calculated values.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0008_add_multi_model_support'),
    ]

    operations = [
        migrations.RunPython(
            backfill_embedding_dimensions,
            reverse_backfill_embedding_dimensions,
        ),
    ]
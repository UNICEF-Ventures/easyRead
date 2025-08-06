# Data migration to pad existing embeddings to 2000 dimensions

from django.db import migrations
import numpy as np
import logging

logger = logging.getLogger(__name__)

def pad_existing_embeddings(apps, schema_editor):
    """
    Pad all existing embeddings to 2000 dimensions if they're not already padded.
    """
    Embedding = apps.get_model('api', 'Embedding')
    
    embeddings_to_update = []
    processed = 0
    skipped = 0
    
    for embedding in Embedding.objects.all():
        try:
            # Get the current vector
            vector = embedding.vector
            
            if isinstance(vector, str):
                # If stored as string, parse it
                import json
                vector = json.loads(vector)
            
            # Convert to numpy array
            vector_array = np.array(vector, dtype=np.float32)
            
            # Check if already padded
            if len(vector_array) == 2000:
                skipped += 1
                continue
            
            # Check if dimension matches what's stored
            if len(vector_array) != embedding.embedding_dimension:
                logger.warning(
                    f"Embedding {embedding.id} has mismatched dimensions: "
                    f"vector length {len(vector_array)} vs stored {embedding.embedding_dimension}"
                )
            
            # Pad to 2000
            padded = np.zeros(2000, dtype=np.float32)
            padded[:len(vector_array)] = vector_array
            
            # Update the embedding
            embedding.vector = padded.tolist()
            embeddings_to_update.append(embedding)
            processed += 1
            
            # Batch update every 100 records
            if len(embeddings_to_update) >= 100:
                Embedding.objects.bulk_update(embeddings_to_update, ['vector'])
                logger.info(f"Updated {len(embeddings_to_update)} embeddings")
                embeddings_to_update = []
                
        except Exception as e:
            logger.error(f"Failed to pad embedding {embedding.id}: {e}")
    
    # Update remaining embeddings
    if embeddings_to_update:
        Embedding.objects.bulk_update(embeddings_to_update, ['vector'])
        logger.info(f"Updated final {len(embeddings_to_update)} embeddings")
    
    logger.info(f"Padding complete: {processed} padded, {skipped} already padded")

def reverse_padding(apps, schema_editor):
    """
    Reverse operation - truncate vectors back to original dimension.
    """
    Embedding = apps.get_model('api', 'Embedding')
    
    embeddings_to_update = []
    
    for embedding in Embedding.objects.all():
        try:
            vector = embedding.vector
            
            if isinstance(vector, str):
                import json
                vector = json.loads(vector)
            
            # Truncate to original dimension
            original_dim = embedding.embedding_dimension
            if original_dim and original_dim < len(vector):
                truncated = vector[:original_dim]
                embedding.vector = truncated
                embeddings_to_update.append(embedding)
                
                if len(embeddings_to_update) >= 100:
                    Embedding.objects.bulk_update(embeddings_to_update, ['vector'])
                    embeddings_to_update = []
                    
        except Exception as e:
            logger.error(f"Failed to truncate embedding {embedding.id}: {e}")
    
    if embeddings_to_update:
        Embedding.objects.bulk_update(embeddings_to_update, ['vector'])

class Migration(migrations.Migration):
    dependencies = [
        ('api', '0012_update_vector_field_to_2000_dimensions'),
    ]

    operations = [
        migrations.RunPython(
            pad_existing_embeddings,
            reverse_padding,
            elidable=True
        ),
    ]
# Migration to switch from IVFFlat to HNSW indexes for better high-dimensional vector support

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0013_pad_existing_embeddings'),
    ]

    operations = [
        # Drop the problematic IVFFlat cosine index that can't handle >2000 dimensions
        migrations.RunSQL(
            sql="DROP INDEX IF EXISTS embedding_vector_cosine_idx;",
            reverse_sql="CREATE INDEX embedding_vector_cosine_idx ON api_embedding USING ivfflat (vector vector_cosine_ops) WITH (lists = 100);"
        ),
        
        # Note: HNSW index creation is deferred until after vector field dimension is corrected  
        # This migration only removes the IVFFlat index
        migrations.RunSQL(
            sql="SELECT 1;",  # No-op SQL statement
            reverse_sql="SELECT 1;"
        ),
    ]
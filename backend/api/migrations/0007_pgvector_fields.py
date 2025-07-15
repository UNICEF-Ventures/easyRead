# Migration to update Embedding model to use pgvector VectorField
# This migration should be run AFTER pgvector extension is installed in PostgreSQL

from django.db import migrations


class Migration(migrations.Migration):
    """
    Migration to update Embedding model to use proper pgvector VectorField.
    
    IMPORTANT: This migration requires:
    1. PostgreSQL database with pgvector extension installed
    2. pgvector Python package installed
    
    To apply this migration:
    1. Ensure pgvector extension is created in PostgreSQL: CREATE EXTENSION vector;
    2. Install pgvector: pip install pgvector
    3. Run: python manage.py migrate
    """

    dependencies = [
        ('api', '0006_new_embedding_models'),
    ]

    operations = [
        # Note: The actual field changes are commented out because they require pgvector
        # Uncomment these operations once pgvector is properly installed
        
        # migrations.AlterField(
        #     model_name='embedding',
        #     name='vector',
        #     field=pgvector.django.VectorField(dimensions=1024),  # Adjust dimensions based on model
        # ),
        
        # Add vector index for efficient similarity search
        # migrations.RunSQL(
        #     "CREATE INDEX embedding_vector_idx ON api_embedding USING ivfflat (vector vector_cosine_ops) WITH (lists = 100);",
        #     reverse_sql="DROP INDEX IF EXISTS embedding_vector_idx;"
        # ),
        
        # Add regular indexes for common queries
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS api_embedding_image_type_idx ON api_embedding (image_id, embedding_type);",
            reverse_sql="DROP INDEX IF EXISTS api_embedding_image_type_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS api_image_set_filename_idx ON api_image (set_id, filename);",
            reverse_sql="DROP INDEX IF EXISTS api_image_set_filename_idx;"
        ),
        
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS api_image_format_idx ON api_image (file_format);",
            reverse_sql="DROP INDEX IF EXISTS api_image_format_idx;"
        ),
    ]
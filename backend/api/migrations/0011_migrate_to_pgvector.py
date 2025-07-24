# Fixed migration to convert embeddings from JSONField to pgvector VectorField
# This migration drops and recreates the table to avoid casting issues

from django.db import migrations, models
import pgvector.django


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0010_usersession_sessionevent_imagesetselection_and_more'),
    ]

    operations = [
        # First, create the vector extension if it doesn't exist
        migrations.RunSQL(
            "CREATE EXTENSION IF NOT EXISTS vector;",
            reverse_sql="DROP EXTENSION IF EXISTS vector;"
        ),
        
        # Drop the existing embedding table to avoid casting issues
        migrations.RunSQL(
            "DROP TABLE IF EXISTS api_embedding CASCADE;",
            reverse_sql="-- Cannot reverse dropping table"
        ),
        
        # Recreate the embedding table with proper pgvector field
        migrations.CreateModel(
            name='Embedding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('embedding_type', models.CharField(choices=[('image', 'Image Embedding'), ('text', 'Text Embedding')], max_length=10)),
                ('vector', pgvector.django.VectorField(dimensions=1024)),
                ('provider_name', models.CharField(default='openclip', max_length=100)),
                ('model_name', models.CharField(default='openclip-vit-b-32', max_length=100)),
                ('embedding_dimension', models.IntegerField(default=1024)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('image', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='embeddings', to='api.image')),
            ],
            options={
                'ordering': ['image', 'embedding_type', 'provider_name', 'model_name'],
            },
        ),
        
        # Add unique constraint
        migrations.AlterUniqueTogether(
            name='embedding',
            unique_together={('image', 'embedding_type', 'provider_name', 'model_name')},
        ),
        
        # Add model meta indexes
        migrations.AddIndex(
            model_name='embedding',
            index=models.Index(fields=['provider_name', 'model_name', 'embedding_type'], name='api_embedding_provider_model_type_idx'),
        ),
        migrations.AddIndex(
            model_name='embedding',
            index=models.Index(fields=['image', 'embedding_type', 'provider_name'], name='api_embedding_image_type_provider_idx'),
        ),
        migrations.AddIndex(
            model_name='embedding',
            index=models.Index(fields=['embedding_dimension'], name='api_embedding_dimension_idx'),
        ),
        
        # Create pgvector-specific indexes for efficient similarity search
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS embedding_vector_cosine_idx 
            ON api_embedding 
            USING ivfflat (vector vector_cosine_ops) 
            WITH (lists = 100);
            """,
            reverse_sql="DROP INDEX IF EXISTS embedding_vector_cosine_idx;"
        ),
        
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS embedding_vector_l2_idx 
            ON api_embedding 
            USING hnsw (vector vector_l2_ops) 
            WITH (m = 16, ef_construction = 64);
            """,
            reverse_sql="DROP INDEX IF EXISTS embedding_vector_l2_idx;"
        ),
        
        # Add composite index for filtered similarity searches
        migrations.RunSQL(
            """
            CREATE INDEX IF NOT EXISTS embedding_type_provider_idx 
            ON api_embedding (embedding_type, provider_name) 
            INCLUDE (vector);
            """,
            reverse_sql="DROP INDEX IF EXISTS embedding_type_provider_idx;"
        ),
    ]
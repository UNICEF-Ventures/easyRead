# Migration to create HNSW indexes for 2000-dimensional vectors

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0015_fix_vector_dimensions_for_pgvector_limits'),
    ]

    operations = [
        # Create HNSW index for cosine similarity (2000 dimensions supported)
        migrations.RunSQL(
            sql="""
                CREATE INDEX IF NOT EXISTS embedding_vector_cosine_hnsw_idx 
                ON api_embedding 
                USING hnsw (vector vector_cosine_ops) 
                WITH (m = 16, ef_construction = 64);
            """,
            reverse_sql="DROP INDEX IF EXISTS embedding_vector_cosine_hnsw_idx;"
        ),
        
        # Create HNSW index for L2 distance
        migrations.RunSQL(
            sql="""
                CREATE INDEX IF NOT EXISTS embedding_vector_l2_hnsw_idx 
                ON api_embedding 
                USING hnsw (vector vector_l2_ops) 
                WITH (m = 16, ef_construction = 64);
            """,
            reverse_sql="DROP INDEX IF EXISTS embedding_vector_l2_hnsw_idx;"
        ),
        
        # Create HNSW index for inner product (dot product) similarity
        migrations.RunSQL(
            sql="""
                CREATE INDEX IF NOT EXISTS embedding_vector_inner_hnsw_idx 
                ON api_embedding 
                USING hnsw (vector vector_ip_ops) 
                WITH (m = 16, ef_construction = 64);
            """,
            reverse_sql="DROP INDEX IF EXISTS embedding_vector_inner_hnsw_idx;"
        ),
    ]
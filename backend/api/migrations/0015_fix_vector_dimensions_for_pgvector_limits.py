# Migration to fix vector field dimensions for pgvector 0.8.0 constraints

from django.db import migrations
import pgvector.django.vector


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0014_switch_to_hnsw_indexes'),
    ]

    operations = [
        # Change vector field to 2000 dimensions (maximum supported by pgvector 0.8.0)
        migrations.AlterField(
            model_name='embedding',
            name='vector',
            field=pgvector.django.vector.VectorField(dimensions=2000),
        ),
    ]
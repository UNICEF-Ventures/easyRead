import os
import shutil
from django.core.management.base import BaseCommand
from django.conf import settings
import chromadb
from api.models import ImageMetadata
import logging

# Setup logger for this command
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO) # Ensure info level logs are shown

class Command(BaseCommand):
    help = 'Deletes all uploaded/generated image files, their database records, and their ChromaDB embeddings.'

    def handle(self, *args, **options):
        image_dir = settings.MEDIA_ROOT / "uploaded_images"
        chroma_db_path = settings.BASE_DIR.parent / "chroma_db"
        collection_name = "image_embeddings" # Make sure this matches settings/views

        self.stdout.write(self.style.WARNING("This command will permanently delete:"))
        self.stdout.write(self.style.WARNING(f"- All files in {image_dir}"))
        self.stdout.write(self.style.WARNING("- All records from the ImageMetadata table"))
        self.stdout.write(self.style.WARNING(f"- The ChromaDB collection '{collection_name}' at {chroma_db_path}"))
        
        confirmation = input("Are you sure you want to continue? (yes/no): ")
        if confirmation.lower() != 'yes':
            self.stdout.write(self.style.ERROR("Operation cancelled."))
            return

        # 1. Delete files in the image directory
        self.stdout.write(f"Deleting files in {image_dir}...")
        deleted_files = 0
        failed_files = 0
        if os.path.exists(image_dir):
            for filename in os.listdir(image_dir):
                file_path = os.path.join(image_dir, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                        deleted_files += 1
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path) # Remove subdirectories if any
                        deleted_files += 1 # Count dir as one item
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"Failed to delete {file_path}. Reason: {e}"))
                    failed_files += 1
            self.stdout.write(self.style.SUCCESS(f"Deleted {deleted_files} items from {image_dir}. Failed: {failed_files}."))
        else:
            self.stdout.write(self.style.WARNING(f"Directory {image_dir} not found. Skipping file deletion."))

        # 2. Delete ImageMetadata records
        self.stdout.write("Deleting ImageMetadata records from the database...")
        try:
            count, _ = ImageMetadata.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted {count} ImageMetadata records."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to delete ImageMetadata records. Reason: {e}"))
            # Consider stopping if DB deletion fails critically

        # 3. Delete ChromaDB collection
        self.stdout.write(f"Deleting ChromaDB collection '{collection_name}'...")
        try:
            chroma_client = chromadb.PersistentClient(path=str(chroma_db_path))
            # Check if collection exists before trying to delete
            collections = chroma_client.list_collections()
            collection_exists = any(c.name == collection_name for c in collections)
            
            if collection_exists:
                chroma_client.delete_collection(name=collection_name)
                self.stdout.write(self.style.SUCCESS(f"Deleted ChromaDB collection '{collection_name}'."))
                # Recreate the collection immediately
                chroma_client.create_collection(name=collection_name)
                self.stdout.write(self.style.SUCCESS(f"Recreated empty ChromaDB collection '{collection_name}'."))
            else:
                 self.stdout.write(self.style.WARNING(f"ChromaDB collection '{collection_name}' does not exist. Skipping deletion, but creating it."))
                 chroma_client.create_collection(name=collection_name)
                 self.stdout.write(self.style.SUCCESS(f"Created empty ChromaDB collection '{collection_name}'."))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to delete/recreate ChromaDB collection '{collection_name}'. Reason: {e}"))

        self.stdout.write(self.style.SUCCESS("Image clearing process finished.")) 
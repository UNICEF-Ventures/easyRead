import os
import shutil
from django.core.management.base import BaseCommand
from django.conf import settings
from api.models import ImageSet, Image, Embedding
import logging

# Setup logger for this command
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO) # Ensure info level logs are shown

class Command(BaseCommand):
    help = 'Deletes all uploaded/generated image files, their database records, and their PostgreSQL embeddings.'

    def handle(self, *args, **options):
        image_dir = settings.MEDIA_ROOT / "uploaded_images"
        generated_dir = settings.MEDIA_ROOT / "images"

        self.stdout.write(self.style.WARNING("This command will permanently delete:"))
        self.stdout.write(self.style.WARNING(f"- All files in {image_dir}"))
        self.stdout.write(self.style.WARNING(f"- All files in {generated_dir}"))
        self.stdout.write(self.style.WARNING("- All records from the Image table"))
        self.stdout.write(self.style.WARNING("- All records from the ImageSet table"))
        self.stdout.write(self.style.WARNING("- All records from the Embedding table"))
        
        confirmation = input("Are you sure you want to continue? (yes/no): ")
        if confirmation.lower() != 'yes':
            self.stdout.write(self.style.ERROR("Operation cancelled."))
            return

        # 1. Delete files in image directories
        self.stdout.write(f"Deleting files in {image_dir}...")
        deleted_files = self._delete_directory_files(image_dir)
        
        self.stdout.write(f"Deleting files in {generated_dir}...")
        deleted_generated = self._delete_directory_files(generated_dir)

        # 2. Delete database records (in correct order due to foreign keys)
        self.stdout.write("Deleting Embedding records from the database...")
        try:
            embedding_count, _ = Embedding.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted {embedding_count} Embedding records."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to delete Embedding records. Reason: {e}"))

        self.stdout.write("Deleting Image records from the database...")
        try:
            image_count, _ = Image.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted {image_count} Image records."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to delete Image records. Reason: {e}"))

        self.stdout.write("Deleting ImageSet records from the database...")
        try:
            imageset_count, _ = ImageSet.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted {imageset_count} ImageSet records."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to delete ImageSet records. Reason: {e}"))

        self.stdout.write(self.style.SUCCESS("Image clearing process finished."))

    def _delete_directory_files(self, directory):
        """Helper method to delete all files in a directory."""
        deleted_files = 0
        failed_files = 0
        
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                        deleted_files += 1
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                        deleted_files += 1
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"Failed to delete {file_path}. Reason: {e}"))
                    failed_files += 1
            self.stdout.write(self.style.SUCCESS(f"Deleted {deleted_files} items from {directory}. Failed: {failed_files}."))
        else:
            self.stdout.write(self.style.WARNING(f"Directory {directory} not found. Skipping file deletion."))
        
        return deleted_files 
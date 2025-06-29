import json
from django.core.management.base import BaseCommand
from api.models import ProcessedContent
import logging

# Setup logger for this command
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO) # Ensure info level logs are shown

class Command(BaseCommand):
    help = 'Clears selected_image_path and alternative_images from all saved ProcessedContent records.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            "This command will iterate through all saved ProcessedContent records and remove image references "
            "(selected_image_path and alternative_images) from their easy_read_json data."
        ))
        
        confirmation = input("Are you sure you want to continue? (yes/no): ")
        if confirmation.lower() != 'yes':
            self.stdout.write(self.style.ERROR("Operation cancelled."))
            return

        updated_count = 0
        skipped_count = 0
        error_count = 0

        all_content = ProcessedContent.objects.all()
        total_count = all_content.count()
        self.stdout.write(f"Found {total_count} saved content records to process...")

        for content in all_content.iterator(): # Use iterator for potentially large datasets
            try:
                needs_update = False
                if isinstance(content.easy_read_json, list):
                    for sentence_data in content.easy_read_json:
                        if isinstance(sentence_data, dict):
                            # Check if keys exist and have non-null/non-empty values before clearing
                            if sentence_data.get('selected_image_path'):
                                sentence_data['selected_image_path'] = None
                                needs_update = True
                            if sentence_data.get('alternative_images'): # Check if list exists and is not empty
                                sentence_data['alternative_images'] = []
                                needs_update = True
                else:
                    self.stdout.write(self.style.WARNING(f"Skipping content ID {content.id}: easy_read_json is not a list."))
                    skipped_count += 1
                    continue # Skip this record

                if needs_update:
                    content.save()
                    updated_count += 1
                    self.stdout.write(f"Updated image paths for content ID: {content.id}")
                else:
                     skipped_count += 1 # Count as skipped if no update was needed
                     self.stdout.write(f"Skipping content ID {content.id}: No image paths found to clear.")

            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Failed to process content ID {content.id}. Reason: {e}"))
                error_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Finished processing. Updated: {updated_count}, Skipped (no paths found or invalid format): {skipped_count}, Errors: {error_count}."
        )) 
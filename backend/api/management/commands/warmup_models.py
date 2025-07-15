"""
Django management command to warmup models for better performance.
"""

from django.core.management.base import BaseCommand
from api.warmup import warmup_all_models


class Command(BaseCommand):
    help = 'Warmup models to improve performance'

    def add_arguments(self, parser):
        parser.add_argument(
            '--background',
            action='store_true',
            help='Run warmup in background (non-blocking)',
        )

    def handle(self, *args, **options):
        self.stdout.write('Starting model warmup...')
        
        if options['background']:
            import threading
            def warmup_thread():
                success = warmup_all_models()
                if success:
                    self.stdout.write(self.style.SUCCESS('Model warmup completed successfully'))
                else:
                    self.stdout.write(self.style.WARNING('Model warmup completed with warnings'))
            
            thread = threading.Thread(target=warmup_thread)
            thread.daemon = True
            thread.start()
            self.stdout.write('Model warmup started in background')
        else:
            success = warmup_all_models()
            if success:
                self.stdout.write(self.style.SUCCESS('Model warmup completed successfully'))
            else:
                self.stdout.write(self.style.WARNING('Model warmup completed with warnings'))
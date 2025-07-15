"""
Django management command to start the development server with environment-configured port.
"""

import os
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings

class Command(BaseCommand):
    help = 'Start Django development server with environment-configured port'

    def add_arguments(self, parser):
        parser.add_argument(
            '--port',
            type=int,
            help='Port to run the server on (overrides environment variable)',
        )
        parser.add_argument(
            '--host',
            type=str,
            help='Host to run the server on (overrides environment variable)',
        )

    def handle(self, *args, **options):
        # Get port from command line argument, environment variable, or default
        port = options.get('port') or os.environ.get('DJANGO_PORT', '8000')
        host = options.get('host') or os.environ.get('DJANGO_HOST', 'localhost')
        
        # Convert port to int if it's a string
        if isinstance(port, str):
            try:
                port = int(port)
            except ValueError:
                self.stdout.write(
                    self.style.ERROR(f'Invalid port number: {port}')
                )
                return
        
        address = f"{host}:{port}"
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting Django development server on http://{address}')
        )
        
        # Show configuration info
        self.stdout.write(f'Port source: {"command line" if options.get("port") else "environment" if os.environ.get("DJANGO_PORT") else "default"}')
        self.stdout.write(f'Host source: {"command line" if options.get("host") else "environment" if os.environ.get("DJANGO_HOST") else "default"}')
        self.stdout.write('')
        
        try:
            # Call the runserver command with the configured address
            call_command('runserver', address, verbosity=1)
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to start server: {e}')
            )
            self.stdout.write(
                self.style.ERROR(f'Make sure port {port} is available and you have the necessary permissions')
            )
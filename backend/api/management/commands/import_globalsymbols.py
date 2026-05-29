"""
Import the Global Symbols dataset (images/globalsymbols_data) into the database.

Each set lives in its own subfolder. Symbols often ship in several formats
(PNG + SVG) plus a sidecar JSON with clean human-readable metadata. This command:

  * groups files by stem so each symbol is imported once (PNG preferred),
  * uses the sidecar JSON `name` as the description (falls back to the filename),
  * names each ImageSet after its folder.

Examples:
    # Dry run a single set
    python manage.py import_globalsymbols --base-dir /app/images/globalsymbols_data \
        --only Mulberry_Symbols --dry-run

    # Import everything, skipping symbols already in the DB
    python manage.py import_globalsymbols --base-dir /app/images/globalsymbols_data
"""

import json
import logging
from pathlib import Path

from django.core.management.base import BaseCommand

from api.upload_handlers import handle_image_upload
from api.image_utils import generate_description_from_filename

logger = logging.getLogger(__name__)

# Preference order when a symbol exists in multiple formats (lower index wins).
FORMAT_PREFERENCE = ['.png', '.webp', '.jpg', '.jpeg', '.svg']


class FakeUploadedFile:
    """Minimal stand-in for a Django UploadedFile backed by a local path."""

    def __init__(self, path):
        self.path = Path(path)
        self.name = self.path.name
        self.size = self.path.stat().st_size

    def chunks(self):
        with open(self.path, 'rb') as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                yield chunk

    def read(self):
        with open(self.path, 'rb') as f:
            return f.read()


class Command(BaseCommand):
    help = 'Import the Global Symbols dataset into image sets (one set per folder)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--base-dir',
            type=str,
            default='/app/images/globalsymbols_data',
            help='Path to the globalsymbols_data directory',
        )
        parser.add_argument(
            '--only',
            type=str,
            nargs='+',
            default=None,
            help='Only import these set folder name(s)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without writing anything',
        )
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            default=True,
            help='Skip symbols already present in the DB (default: on)',
        )
        parser.add_argument(
            '--no-skip-existing',
            dest='skip_existing',
            action='store_false',
            help='Re-import symbols even if a matching filename already exists',
        )

    def describe(self, image_path):
        """Return a description for an image, preferring its sidecar JSON name."""
        json_path = image_path.with_suffix('.json')
        if json_path.exists():
            try:
                data = json.loads(json_path.read_text(encoding='utf-8'))
                name = (data.get('name') or '').strip()
                if name:
                    return name
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f'Could not read metadata {json_path}: {e}')
        return generate_description_from_filename(image_path.name)

    def collect_symbols(self, set_dir):
        """Group image files in a set folder by stem, picking one per symbol."""
        candidates = {}
        for f in set_dir.iterdir():
            ext = f.suffix.lower()
            if ext not in FORMAT_PREFERENCE:
                continue
            candidates.setdefault(f.stem, []).append(f)

        chosen = []
        for stem, files in candidates.items():
            files.sort(key=lambda p: FORMAT_PREFERENCE.index(p.suffix.lower()))
            chosen.append(files[0])
        chosen.sort(key=lambda p: p.name)
        return chosen

    def handle(self, *args, **options):
        base_dir = Path(options['base_dir'])
        if not base_dir.is_dir():
            self.stdout.write(self.style.ERROR(f'Not a directory: {base_dir}'))
            return

        set_dirs = sorted(d for d in base_dir.iterdir() if d.is_dir())
        if options['only']:
            wanted = set(options['only'])
            set_dirs = [d for d in set_dirs if d.name in wanted]
            missing = wanted - {d.name for d in set_dirs}
            if missing:
                self.stdout.write(self.style.ERROR(f'Set(s) not found: {sorted(missing)}'))
                return

        if not set_dirs:
            self.stdout.write(self.style.WARNING('No set folders to import'))
            return

        dry_run = options['dry_run']
        skip_existing = options['skip_existing']

        total_uploaded = total_failed = total_skipped = 0

        for set_dir in set_dirs:
            set_name = set_dir.name
            symbols = self.collect_symbols(set_dir)
            self.stdout.write(self.style.HTTP_INFO(
                f'\n=== {set_name}: {len(symbols)} symbols ==='
            ))

            if dry_run:
                for img in symbols[:5]:
                    self.stdout.write(f'  {img.name} -> "{self.describe(img)}"')
                if len(symbols) > 5:
                    self.stdout.write(f'  ... and {len(symbols) - 5} more')
                continue

            for img in symbols:
                description = self.describe(img)

                if skip_existing:
                    from api.models import Image
                    if Image.objects.filter(filename=img.name, set__name=set_name).exists():
                        total_skipped += 1
                        continue

                try:
                    result = handle_image_upload(
                        FakeUploadedFile(img), description, set_name
                    )
                    if result.get('success'):
                        total_uploaded += 1
                    else:
                        total_failed += 1
                        errs = result.get('errors', result.get('error', 'Unknown error'))
                        self.stdout.write(self.style.ERROR(f'  ✗ {img.name}: {errs}'))
                except Exception as e:
                    total_failed += 1
                    self.stdout.write(self.style.ERROR(f'  ✗ {img.name}: {e}'))

            self.stdout.write(
                f'  set done — uploaded={total_uploaded} '
                f'failed={total_failed} skipped={total_skipped} (running totals)'
            )

        self.stdout.write('')
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — nothing was written'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Import complete: uploaded={total_uploaded} '
                f'failed={total_failed} skipped={total_skipped}'
            ))

from django.core.management.base import BaseCommand
from books.models import Book, UserBook
from books.visual_search import extract_features_from_path, extract_features_from_url
import logging
import os

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Compute and store simple image features (color histogram) for Book and UserBook images'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Recompute features even if present')

    def handle(self, *args, **options):
        force = options.get('force', False)

        self.stdout.write('Computing image features for Book model...')
        updated = 0
        for book in Book.objects.all():
            try:
                if book.image_features and not force:
                    continue

                # Prefer ImageField
                processed = False
                if getattr(book, 'image', None) and getattr(book.image, 'path', None):
                    p = book.image.path
                    if os.path.exists(p):
                        feats = extract_features_from_path(p)
                        if feats:
                            book.image_features = feats
                            book.save()
                            updated += 1
                            processed = True
                            self.stdout.write(f'Computed features for book: {book.title}')

                if processed:
                    continue

                # Fallback to cover_image_url (only HTTP URLs)
                if book.cover_image_url:
                    url = book.cover_image_url
                    if url.startswith('http://') or url.startswith('https://'):
                        feats = extract_features_from_url(url)
                        if feats:
                            book.image_features = feats
                            book.save()
                            updated += 1
                            self.stdout.write(f'Computed features from URL for book: {book.title}')

            except Exception as e:
                logger.error(f'Error computing features for book {book.title}: {e}')

        self.stdout.write(f'Updated {updated} Book records')

        self.stdout.write('Computing image features for UserBook model...')
        updated = 0
        for ub in UserBook.objects.filter(is_available=True):
            try:
                if ub.image_features and not force:
                    continue

                if getattr(ub, 'cover_image', None) and getattr(ub.cover_image, 'path', None):
                    p = ub.cover_image.path
                    if os.path.exists(p):
                        feats = extract_features_from_path(p)
                        if feats:
                            ub.image_features = feats
                            ub.save()
                            updated += 1
                            self.stdout.write(f'Computed features for user book: {ub.title}')
            except Exception as e:
                logger.error(f'Error computing features for user book {ub.title}: {e}')

        self.stdout.write(f'Updated {updated} UserBook records')

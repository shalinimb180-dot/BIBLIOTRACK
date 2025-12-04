from django.core.management.base import BaseCommand
from books.models import Book, UserBook
import imagehash
from PIL import Image
import os
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def generate_image_hash_from_path(path_or_file):
    try:
        img = Image.open(path_or_file)
        img = img.convert('RGB')
        return str(imagehash.phash(img))
    except Exception as e:
        logger.warning(f"Failed to hash image {path_or_file}: {e}")
        return None


class Command(BaseCommand):
    help = 'Compute and store perceptual image hashes for Book and UserBook models'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Recompute hashes even if present')

    def handle(self, *args, **options):
        force = options.get('force', False)

        self.stdout.write('Computing image hashes for Book model...')
        updated = 0
        for book in Book.objects.all():
            try:
                if book.image_hash and not force:
                    continue

                # Prefer ImageField stored locally
                processed = False
                if getattr(book, 'image', None) and getattr(book.image, 'path', None):
                    p = book.image.path
                    if os.path.exists(p):
                        h = generate_image_hash_from_path(p)
                        if h:
                            book.image_hash = h
                            book.save()
                            updated += 1
                            processed = True
                            self.stdout.write(f'Hashed local image for book: {book.title}')

                if processed:
                    continue

                # Try MEDIA-relative cover_image_url
                if book.cover_image_url and not book.image_hash:
                    url = book.cover_image_url
                    media_url = str(getattr(settings, 'MEDIA_URL', '/media/'))
                    if url.startswith(media_url) or url.startswith('/media/') or url.startswith('media/'):
                        rel = url.replace(media_url, '').lstrip('/')
                        local_path = os.path.join(settings.MEDIA_ROOT, rel)
                        if os.path.exists(local_path):
                            h = generate_image_hash_from_path(local_path)
                            if h:
                                book.image_hash = h
                                book.save()
                                updated += 1
                                self.stdout.write(f'Hashed media image for book: {book.title}')
                                continue

                # Skip remote download here to keep command fast and offline-safe
            except Exception as e:
                logger.error(f'Error processing book {book.title}: {e}')

        self.stdout.write(f'Updated {updated} Book records')

        self.stdout.write('Computing image hashes for UserBook model...')
        updated = 0
        for ub in UserBook.objects.filter(is_available=True):
            try:
                if ub.image_hash and not force:
                    continue

                if getattr(ub, 'cover_image', None) and getattr(ub.cover_image, 'path', None):
                    p = ub.cover_image.path
                    if os.path.exists(p):
                        h = generate_image_hash_from_path(p)
                        if h:
                            ub.image_hash = h
                            ub.save()
                            updated += 1
                            self.stdout.write(f'Hashed user book image: {ub.title}')
            except Exception as e:
                logger.error(f'Error processing user book {ub.title}: {e}')

        self.stdout.write(f'Updated {updated} UserBook records')

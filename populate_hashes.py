import os
import django
import imagehash
import logging
from PIL import Image

logger = logging.getLogger(__name__)

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bookstore.settings')
django.setup()

from books.models import Book, UserBook

def generate_image_hash(image_path):
    """Generate perceptual hash for an image."""
    try:
        img = Image.open(image_path)
        img = img.convert('RGB')
        hash_value = imagehash.phash(img)
        return str(hash_value)
    except (OSError, IOError) as e:
        logger.error(f"Error processing image {image_path}: {e}")
        return None

def populate_book_hashes():
    """Populate image hashes for Book model."""
    logger.info("Populating image hashes for Book model...")
    books = Book.objects.all()
    updated_count = 0

    for book in books:
        # Prefer ImageField if present
        try:
            if getattr(book, 'image') and getattr(book.image, 'path', None) and not book.image_hash:
                image_path = book.image.path
                hash_value = generate_image_hash(image_path)
                if hash_value:
                    book.image_hash = hash_value
                    book.save()
                    updated_count += 1
                    logger.info(f"Updated hash for book (local image): {book.title}")
                continue
        except Exception as e:
            logger.debug(f"Local image not processed for book {book.title}: {e}")

        # If cover_image_url exists, try to download and hash or load from MEDIA
        if book.cover_image_url and not book.image_hash:
            try:
                from django.conf import settings
                # If it's a relative media path, build local path
                url = book.cover_image_url
                local_path = None
                if url.startswith(str(getattr(settings, 'MEDIA_URL', '/media/')) ) or url.startswith('/media/') or url.startswith('media/'):
                    # Strip leading MEDIA_URL or /media/
                    rel = url.replace(str(getattr(settings, 'MEDIA_URL', '/media/')), '').lstrip('/')
                    local_path = os.path.join(settings.MEDIA_ROOT, rel)

                if local_path and os.path.exists(local_path):
                    hash_value = generate_image_hash(local_path)
                    if hash_value:
                        book.image_hash = hash_value
                        book.save()
                        updated_count += 1
                        logger.info(f"Updated hash for book (local media path): {book.title}")
                        continue

                # If url looks like an absolute HTTP URL, download it
                if url.startswith('http://') or url.startswith('https://'):
                    import requests
                    resp = requests.get(url, timeout=10)
                    resp.raise_for_status()
                    from io import BytesIO
                    img_buf = BytesIO(resp.content)
                    hash_value = generate_image_hash(img_buf)
                    if hash_value:
                        book.image_hash = hash_value
                        book.save()
                        updated_count += 1
                        logger.info(f"Updated hash for book (downloaded URL): {book.title}")
                        continue
            except Exception as e:
                logger.warning(f"Failed to download/hash cover_image_url for {book.title}: {e}")

        logger.debug(f"No image found or already hashed for book: {book.title}")

    logger.info(f"Updated {updated_count} books with image hashes")

def populate_user_book_hashes():
    """Populate image hashes for UserBook model."""
    logger.info("Populating image hashes for UserBook model...")
    user_books = UserBook.objects.filter(is_available=True)
    updated_count = 0

    for user_book in user_books:
        if user_book.cover_image and not user_book.image_hash:
            try:
                # Get the full path to the image
                image_path = user_book.cover_image.path
                hash_value = generate_image_hash(image_path)

                if hash_value:
                    user_book.image_hash = hash_value
                    user_book.save()
                    updated_count += 1
                    logger.info(f"Updated hash for user book: {user_book.title}")
                else:
                    logger.warning(f"Failed to generate hash for user book: {user_book.title}")

            except Exception as e:
                logger.error(f"Error processing user book {user_book.title}: {e}")

        else:
            logger.debug(f"No cover_image for user book or already hashed: {user_book.title}")

    logger.info(f"Updated {updated_count} user books with image hashes")

if __name__ == '__main__':
    populate_book_hashes()
    populate_user_book_hashes()
    logger.info("Image hash population completed!")

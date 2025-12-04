from django.core.management.base import BaseCommand
from books.models import Book, UserBook
from django.conf import settings
import os
import logging
import json

logger = logging.getLogger(__name__)


def compute_with_openai(texts, api_key, model='text-embedding-3-small'):
    import requests
    url = 'https://api.openai.com/v1/embeddings'
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    payload = {'model': model, 'input': texts}
    resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    embeddings = [item['embedding'] for item in data['data']]
    return embeddings


class Command(BaseCommand):
    help = 'Compute semantic embeddings for Book and UserBook records using OpenAI (if OPENAI_API_KEY set) or sentence-transformers when available.'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Recompute embeddings even if present')

    def handle(self, *args, **options):
        force = options.get('force', False)
        api_key = os.environ.get('OPENAI_API_KEY')

        use_openai = bool(api_key)

        # Helper to compute embedding for a single text
        def embed_texts(text_list):
            if not text_list:
                return []
            if use_openai:
                try:
                    return compute_with_openai(text_list, api_key)
                except Exception as e:
                    logger.warning(f'OpenAI embedding failed: {e}')
            # Try sentence-transformers locally
            try:
                from sentence_transformers import SentenceTransformer
                model = SentenceTransformer('all-MiniLM-L6-v2')
                embs = model.encode(text_list, convert_to_numpy=False)
                return [list(e) for e in embs]
            except Exception as e:
                logger.error(f'Local sentence-transformers embedding failed: {e}')
                return []

        # Process Books
        self.stdout.write('Computing semantic embeddings for Book model...')
        batch = []
        batch_objs = []
        updated = 0

        for book in Book.objects.all():
            try:
                if book.semantic_embedding and not force:
                    continue
                text = f"{book.title} {book.author} {book.genre} {book.category} {book.description or ''}"
                batch.append(text)
                batch_objs.append(book)

                if len(batch) >= 16:
                    embs = embed_texts(batch)
                    for obj, emb in zip(batch_objs, embs):
                        if emb:
                            obj.semantic_embedding = emb
                            obj.save()
                            updated += 1
                    batch = []
                    batch_objs = []

            except Exception as e:
                logger.error(f'Error processing book {book.title}: {e}')

        if batch:
            embs = embed_texts(batch)
            for obj, emb in zip(batch_objs, embs):
                if emb:
                    obj.semantic_embedding = emb
                    obj.save()
                    updated += 1

        self.stdout.write(f'Updated {updated} Book embeddings')

        # Process UserBook
        self.stdout.write('Computing semantic embeddings for UserBook model...')
        batch = []
        batch_objs = []
        updated = 0

        for ub in UserBook.objects.filter(is_available=True):
            try:
                if ub.semantic_embedding and not force:
                    continue
                text = f"{ub.title} {ub.author} {ub.genre} {ub.category} {ub.description or ''}"
                batch.append(text)
                batch_objs.append(ub)

                if len(batch) >= 16:
                    embs = embed_texts(batch)
                    for obj, emb in zip(batch_objs, embs):
                        if emb:
                            obj.semantic_embedding = emb
                            obj.save()
                            updated += 1
                    batch = []
                    batch_objs = []

            except Exception as e:
                logger.error(f'Error processing user book {ub.title}: {e}')

        if batch:
            embs = embed_texts(batch)
            for obj, emb in zip(batch_objs, embs):
                if emb:
                    obj.semantic_embedding = emb
                    obj.save()
                    updated += 1

        self.stdout.write(f'Updated {updated} UserBook embeddings')

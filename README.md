# Bookstore Project — Documentation

## Overview

This repository contains a Django-based bookstore application with additional components for visual search, semantic search, recommendations and chat/chatbot features. The project mixes a standard web application stack (Django, Django REST Framework) with machine learning components (TensorFlow/Keras, PyTorch, sentence-transformers) used for search and recommendation features.

## Technologies

- Python 3.11 (recommended) — a `.venv311` virtual environment is provided in the project root.
- Django 4.2.x — web application framework.
- Django REST Framework — API endpoints.
- SQLite (`db.sqlite3`) — default development database.
- ML / NLP libraries: `transformers`, `sentence-transformers`, `scikit-learn`, `tensorflow`, `torch` (used by parts of the project; heavy dependencies in `requirements.txt`).
- Image processing: `Pillow`, `ImageHash`.
- Other utilities: `requests`, `joblib`, `numpy`, `scipy`.

## High-level Architecture

- `bookstore_project/` — Django project settings and WSGI/ASGI entries.
- `books/` — Book models, visual search implementations, semantic search code, views and utilities.
- `accounts/` — user accounts, profiles, authentication related code.
- `chat/`, `chatbot/` — chat and chatbot features, consumers and routing (if using websockets/Channels).
- `recommendations/` — recommendation engine code and models.
- `store/`, `orders/` — storefront and ordering logic.
- `media/`, `static/` — assets and static files.

## Key Modules & Files

- `books/visual_search.py` — Implements feature extraction from images and visual similarity using cosine similarity over flattened image histograms or stored feature vectors. Contains:
  - `extract_features_from_image` — resizes images to 64x64, flattens RGB channels and normalizes values to [0,1].
  - `cosine_similarity_manual` — manual cosine similarity implementation using NumPy.
  - `find_similar_books_enhanced` — queries `Book` and `UserBook` models, caches precomputed image features, computes similarities and returns top results.

- `books/semantic_search.py` — (if present) likely uses sentence-transformers or transformers to embed text (book titles, descriptions) and compute semantic similarities using cosine similarity.

- `recommendations/recommendation_engine.py` — contains logic for recommending books; may include content-based and collaborative filtering approaches.

- `chatbot/chatbot_engine.py` — contains chatbot logic and uses any models or rules to respond to user queries.

## Data Models (high level)

- `Book` — core model for books; stores metadata and (optionally) `image_features` (a serialized list/array) used by visual search.
- `UserBook` — user-provided book listings with optional `image_features` and an `is_available` flag.
- `User` / `Profile` — from `accounts` app, contains user information and possibly address data.

## Algorithms and ML Components

1. Visual Search
   - Feature extraction: images are resized to a fixed small size (64x64) and the RGB pixel values are flattened and normalized. This simple approach produces a compact feature vector (64*64*3 = 12,288 floats) per image.
   - Similarity: cosine similarity between the uploaded (query) image feature vector and stored image feature vectors. The code provides both a legacy per-row loop and an enhanced cached version that precomputes feature arrays and filters items by a similarity threshold.
   - Caching: book features are cached (Django cache backend) to reduce DB and conversion overhead.

2. Semantic Search
   - Embedding text fields (titles, descriptions, authors) using `sentence-transformers` or other transformer models to produce dense vectors.
   - Nearest-neighbor search (cosine similarity) on text embeddings to find semantically related books.

3. Recommendations
   - The repository includes a `recommendation_engine.py`. Typical strategies used:
     - Content-based: use book metadata embeddings (text + visual) and recommend similar items.
     - Collaborative filtering / popularity: use interactions (views, purchases) to compute popularity or collaborative signals.
   - If `model.pkl` or saved model files are present, they may contain precomputed trained models (use `joblib` or `pickle` to load when trusted).

4. Chatbot / NLP
   - Chat features may use rule-based logic or transformer-based models (lightweight or heavier models from `transformers`) to answer questions or provide search assistance.

## Safety: handling `pickle` / `model.pkl`

- Pickle files (e.g., `model.pkl`) can execute arbitrary code when unpickled. Only `pickle.load()` files you trust.
- Safer inspection steps:
  - Disassemble with `pickletools.dis()` to inspect opcodes without executing arbitrary object constructors.
  - If you trust the file and it is a scikit-learn model, prefer `joblib.load()` (still unsafe for untrusted content).

## Setup and Run (development)

1. Use the provided virtual environment or create one:
   - Provided (already created in this environment): ` .venv311` at the project root.
   - To create yourself: `py -3.11 -m venv .venv311`

2. Activate the venv (PowerShell):
```
& ".\.venv311\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
& ".\.venv311\Scripts\python.exe" -m pip install -r .\requirements.txt
```

3. Run migrations and start the dev server:
```
& ".\.venv311\Scripts\python.exe" manage.py migrate
& ".\.venv311\Scripts\python.exe" manage.py runserver 127.0.0.1:8000
```

4. Access the site at `http://127.0.0.1:8000` (do not type `0.0.0.0` in the browser — use localhost or 127.0.0.1).

## Testing

- Run Django tests:
```
& ".\.venv311\Scripts\python.exe" manage.py test
```

## Troubleshooting

- If the server says `Starting development server at http://0.0.0.0:8000/` but you cannot reach it:
  - Open `http://127.0.0.1:8000` instead of `0.0.0.0`.
  - Ensure the process is still running in the terminal where `runserver` was started.
  - Use `netstat -ano | Select-String ":8000"` to check listeners.

- If `pip install -r requirements.txt` is slow or you want a minimal dev environment, create a smaller `requirements-light.txt` that contains only:
  - `Django`, `djangorestframework`, `Pillow`, `numpy`, `requests`

## Contribution Guidelines

- Use feature branches, run tests before opening pull requests, and keep changes small and focused.

## Where to look next in the codebase

- Visual search: `books/visual_search.py` — feature extraction & similarity logic.
- Semantic / text search: `books/semantic_search.py` (and usages in views).
- Recommendation engine: `recommendations/recommendation_engine.py`.
- Chatbot entry: `chatbot/chatbot_engine.py` or `chat/consumers.py`.

## Contact / Maintainers

Maintainership info may be in the repository `README.md` or `TODO.md`. Open an issue or reach the repo owner for questions about production deployment or model re-training.


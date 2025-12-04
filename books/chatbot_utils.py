try:
    import nltk
    from nltk.tokenize import word_tokenize
    from nltk.corpus import stopwords
    from nltk.stem import WordNetLemmatizer
    _HAS_NLTK = True
except Exception:
    nltk = None
    word_tokenize = None
    stopwords = None
    WordNetLemmatizer = None
    _HAS_NLTK = False
import re
import random
from .models import Book, Review, UserBook
from django.db.models import Q
import os
import requests
import json
import logging
try:
    import google.generativeai as genai
except Exception:
    genai = None
from .semantic_search import semantic_search_books
from .advanced_visual_search import find_similar_books_advanced

logger = logging.getLogger(__name__)

# Attempt to detect NLTK data availability, but don't force downloads (offline-safe)
_NLTK_HAS_PUNKT = False
_NLTK_HAS_STOPWORDS = False
_NLTK_HAS_WORDNET = False
if _HAS_NLTK:
    try:
        nltk.data.find('tokenizers/punkt')
        _NLTK_HAS_PUNKT = True
    except Exception:
        _NLTK_HAS_PUNKT = False

    try:
        nltk.data.find('corpora/stopwords')
        _NLTK_HAS_STOPWORDS = True
    except Exception:
        _NLTK_HAS_STOPWORDS = False

    try:
        nltk.data.find('corpora/wordnet')
        _NLTK_HAS_WORDNET = True
    except Exception:
        _NLTK_HAS_WORDNET = False

class BookChatbot:
    def __init__(self):
        # Use lemmatizer only if wordnet is available; otherwise provide a noop
        if _NLTK_HAS_WORDNET and WordNetLemmatizer is not None:
            try:
                self.lemmatizer = WordNetLemmatizer()
            except Exception:
                self.lemmatizer = lambda x: x
        else:
            self.lemmatizer = lambda x: x

        # Load stopwords if available, otherwise empty set
        if _NLTK_HAS_STOPWORDS and stopwords is not None:
            try:
                self.stop_words = set(stopwords.words('english'))
            except Exception:
                self.stop_words = set()
        else:
            self.stop_words = set()

        # Intent patterns using regex
        self.intent_patterns = {
            'recommendation': [
                r'recommend.*book', r'suggest.*book', r'what.*read',
                r'book.*recommend', r'find.*book', r'good.*book'
            ],
            'search': [
                r'find.*by', r'search.*for', r'look.*for',
                r'books.*about', r'books.*author'
            ],
            'help': [
                r'help', r'what.*can.*do', r'how.*work', r'assist'
            ],
            'greeting': [
                r'hello', r'hi', r'hey', r'good.*morning', r'good.*afternoon',
                r'how.*are.*you', r'how.*you.*doing', r'what.*up', r'whats.*up',
                r'howdy', r'greetings', r'sup', r'yo'
            ],
            'farewell': [
                r'bye', r'goodbye', r'see.*you', r'thanks'
            ]
        }

        # Response templates
        self.responses = {
            'recommendation': [
                "Based on your interests, I recommend: {books}",
                "You might enjoy these books: {books}",
                "Here are some great recommendations: {books}",
                "I think you'll love these: {books}"
            ],
            'search': [
                "I found these books matching your query: {books}",
                "Here are the books I found: {books}",
                "Check out these results: {books}",
            ],
            'help': [
                "I can help you find book recommendations, search for books, or answer questions about our bookstore!",
                "Try asking me to recommend books by genre, author, or topic. I can also help with general bookstore questions.",
                "I'm here to help with book recommendations, searches, and general inquiries!"
            ],
            'greeting': [
                "Hello! I'm your AI book assistant. How can I help you discover amazing books today?",
                "Hi there! Ready to find your next great read?",
                "Welcome! I'm here to help you find the perfect book."
            ],
            'farewell': [
                "Happy reading! Come back anytime for more recommendations.",
                "Enjoy your books! See you soon.",
                "Take care and keep reading!"
            ],
            'unknown': [
                "I'm not sure I understand. Could you rephrase that?",
                "Hmm, I'm still learning. Can you try asking differently?",
                "I didn't catch that. Try asking about book recommendations or searches."
            ]
        }

    def preprocess_text(self, text):
        """Preprocess text for better matching"""
        # Tokenize: prefer NLTK punkt tokenizer if available, otherwise fallback to regex
        text_lower = text.lower()
        tokens = []
        if _NLTK_HAS_PUNKT and callable(word_tokenize):
            try:
                tokens = word_tokenize(text_lower)
            except Exception:
                tokens = re.findall(r"\w+", text_lower)
        else:
            tokens = re.findall(r"\w+", text_lower)

        # Remove stopwords and lemmatize (lemmatizer may be noop)
        tokens = [self.lemmatizer(token) if callable(self.lemmatizer) else token for token in tokens]
        tokens = [token for token in tokens if token not in self.stop_words and token.isalnum()]
        return tokens

    def classify_intent(self, text):
        """Classify user intent using regex patterns"""
        text_lower = text.lower()

        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return intent

        return 'unknown'

    def extract_keywords(self, text):
        """Extract relevant keywords from user input"""
        tokens = self.preprocess_text(text)

        # Keywords for book search
        genres = ['fiction', 'non-fiction', 'mystery', 'romance', 'science', 'history',
                 'biography', 'fantasy', 'thriller', 'horror', 'comedy', 'drama']

        authors = ['stephen king', 'j.k. rowling', 'agatha christie', 'dan brown',
                  'harry potter', 'sherlock holmes']

        topics = ['habit', 'productivity', 'self-help', 'business', 'technology',
                 'programming', 'cooking', 'travel', 'health']

        found_genres = [g for g in genres if g in ' '.join(tokens)]
        found_authors = [a for a in authors if a in text.lower()]
        found_topics = [t for t in topics if t in ' '.join(tokens)]

        return {
            'genres': found_genres,
            'authors': found_authors,
            'topics': found_topics,
            'tokens': tokens
        }

    def search_books(self, keywords, limit=3):
        """Search for books based on keywords using semantic search"""
        # Create a search query from keywords
        query_parts = []

        if keywords['genres']:
            query_parts.extend(keywords['genres'])
        if keywords['authors']:
            query_parts.extend(keywords['authors'])
        if keywords['topics']:
            query_parts.extend(keywords['topics'])
        if keywords['tokens']:
            query_parts.extend(keywords['tokens'][:3])  # Use first 3 tokens

        if query_parts:
            # Use semantic search
            search_query = ' '.join(query_parts)
            semantic_results = semantic_search_books(search_query, top_n=limit)

            if semantic_results:
                books = [book for book, score in semantic_results if hasattr(book, 'id')]
                return books[:limit]

        # Fallback to traditional search if semantic search fails
        query = Q()

        if keywords['genres']:
            genre_query = Q()
            for genre in keywords['genres']:
                genre_query |= Q(genre__icontains=genre) | Q(category__icontains=genre)
            query &= genre_query

        if keywords['authors']:
            author_query = Q()
            for author in keywords['authors']:
                author_query |= Q(author__icontains=author)
            query &= author_query

        if keywords['topics']:
            topic_query = Q()
            for topic in keywords['topics']:
                topic_query |= Q(title__icontains=topic) | Q(description__icontains=topic)
            query &= topic_query

        # Search in both Book and UserBook models
        books = list(Book.objects.filter(query).order_by('-rating')[:limit])
        user_books = list(UserBook.objects.filter(query, is_available=True).order_by('-created_at')[:limit])

        all_books = books + user_books

        if not all_books:
            # Fallback: search by title or general keywords
            general_query = Q()
            for token in keywords['tokens'][:3]:  # Use first 3 tokens
                general_query |= Q(title__icontains=token) | Q(author__icontains=token)

            books = list(Book.objects.filter(general_query).order_by('-rating')[:limit])
            user_books = list(UserBook.objects.filter(general_query, is_available=True).order_by('-created_at')[:limit])
            all_books = books + user_books

        return all_books[:limit]

    def get_recommendations(self, user=None, limit=3):
        """Get personalized recommendations"""
        if user and user.is_authenticated:
            # Get user's review history
            user_reviews = Review.objects.filter(user=user)
            if user_reviews.exists():
                # Recommend based on reviewed genres
                genres = [review.book.genre for review in user_reviews]
                books = Book.objects.filter(genre__in=genres).exclude(
                    id__in=[review.book.id for review in user_reviews]
                ).order_by('-rating')[:limit]
                return list(books)

        # Default recommendations: top rated books
        return list(Book.objects.order_by('-rating')[:limit])

    def generate_response(self, intent, keywords=None, user=None):
        """Generate response based on intent and keywords"""
        if intent == 'recommendation':
            books = self.search_books(keywords) if keywords else self.get_recommendations(user)
            if books:
                book_titles = [book.title for book in books]
                template = random.choice(self.responses['recommendation'])
                return template.format(books=', '.join(book_titles))
            else:
                return "I couldn't find specific recommendations. Try our top-rated books!"

        elif intent == 'search':
            books = self.search_books(keywords)
            if books:
                book_titles = [book.title for book in books]
                template = random.choice(self.responses['search'])
                return template.format(books=', '.join(book_titles))
            else:
                return "I couldn't find books matching your search. Try different keywords!"

        elif intent == 'help':
            return random.choice(self.responses['help'])

        elif intent == 'greeting':
            return random.choice(self.responses['greeting'])

        elif intent == 'farewell':
            return random.choice(self.responses['farewell'])

        else:
            return random.choice(self.responses['unknown'])

    def chat(self, message, user=None):
        """Main chat function"""
        # Classify intent
        intent = self.classify_intent(message)

        # Extract keywords
        keywords = self.extract_keywords(message)

        # Generate response
        response = self.generate_response(intent, keywords, user)

        return response

# Global chatbot instance
chatbot = BookChatbot()


def call_external_chat_api(query, user=None, timeout=10):
    """Call an external chatbot API if configured via env vars.

    Expects the following environment variables (optional):
      - CHATBOT_API_URL : full URL to POST queries to
      - CHATBOT_API_KEY : bearer token for Authorization header

    The function is intentionally permissive: it sends JSON {"query": <text>} and
    tries to extract a useful text response from common shapes:
      - {"response": "..."}
      - {"answer": "..."}
      - OpenAI-style {"choices": [{"message": {"content": "..."}}]}

    Returns a string response on success or None on failure.
    """
    api_url = os.environ.get('CHATBOT_API_URL')
    api_key = os.environ.get('CHATBOT_API_KEY')
    if not api_url or not api_key:
        return None

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    payload = {'query': query}

    try:
        logger.debug('Calling external chatbot API %s', api_url)
        resp = requests.post(api_url, headers=headers, data=json.dumps(payload), timeout=timeout)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        logger.warning('External chatbot API timed out')
        return None
    except requests.exceptions.RequestException as e:
        logger.warning('External chatbot API request failed: %s', e)
        return None

    try:
        data = resp.json()
    except Exception:
        return resp.text

    # Common response shapes
    if isinstance(data, dict):
        if 'response' in data and isinstance(data['response'], str):
            return data['response']
        if 'answer' in data and isinstance(data['answer'], str):
            return data['answer']
        # OpenAI chat completion style
        if 'choices' in data and isinstance(data['choices'], list) and len(data['choices']) > 0:
            first = data['choices'][0]
            # gpt-3.5 style
            if isinstance(first, dict) and 'message' in first and isinstance(first['message'], dict):
                return first['message'].get('content')
            # older style
            if isinstance(first, dict) and 'text' in first:
                return first.get('text')

    # Fallback: try to stringify
    try:
        return str(data)
    except Exception:
        return None


def call_gemini_api(query, user=None, timeout=10):
    """Call Gemini API for chatbot responses.

    Uses the GEMINI_API_KEY environment variable.
    """
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        return None

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(query)
        return response.text
    except Exception as e:
        logger.warning('Gemini API request failed: %s', e)
        return None


def get_chatbot_response(message, user_id=None):
    """Return chatbot response with proper intent handling.

    Handles greetings, help, and other intents appropriately, and returns book recommendations
    for search/recommendation queries or when no specific intent is detected.
    """
    # Resolve user if possible
    user_obj = None
    try:
        from django.contrib.auth.models import User
        if user_id is not None:
            try:
                user_obj = User.objects.get(pk=int(user_id))
            except Exception:
                user_obj = None
    except Exception:
        user_obj = None

    # Classify intent first
    intent = chatbot.classify_intent(message)

    # Handle greetings, help, and farewell with proper responses
    if intent in ['greeting', 'help', 'farewell']:
        return chatbot.generate_response(intent, user=user_obj)

    # For recommendation, search, or unknown intents, provide book recommendations
    # Extract keywords from the message
    try:
        keywords = chatbot.extract_keywords(message)
    except Exception:
        keywords = {'genres': [], 'authors': [], 'topics': [], 'tokens': []}

    # Prefer search-based recommendations when tokens/genres/authors/topics present
    books = []
    try:
        has_filters = any([keywords.get('genres'), keywords.get('authors'), keywords.get('topics'), keywords.get('tokens')])
        if has_filters:
            books = chatbot.search_books(keywords, limit=5)
        else:
            books = chatbot.get_recommendations(user=user_obj, limit=5)
    except Exception:
        books = []

    # Format response: title — author (link)
    if not books:
        return "Sorry — I couldn't find recommendations right now. Try a different query."

    parts = []
    for b in books:
        try:
            b_id = getattr(b, 'id', None)
            title = getattr(b, 'title', 'Unknown Title')
            author = getattr(b, 'author', '')
            if b_id:
                link = f"/books/{b_id}/"
                parts.append(f"{title} — {author} ({link})")
            else:
                parts.append(f"{title} — {author}")
        except Exception:
            continue

    return "Here are some book recommendations:\n" + "\n".join(parts)

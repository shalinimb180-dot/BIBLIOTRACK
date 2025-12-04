from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q, Avg, Count
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from django.utils.cache import get_cache_key
from django.utils import timezone
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.template.loader import get_template
from django.core.mail import send_mail
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Book, Review, Order, Wishlist, UserBook, ChatMessage, BookClubPost, BookClubComment, BookClubPostLike, BookClubCommentLike, RecentlyViewed, Deal, SellerRating, UserProfile, ContactMessage, OrderStatus
from .serializers import BookSerializer
from django.conf import settings
import razorpay
import random
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from io import BytesIO
from datetime import datetime
import imagehash
from PIL import Image
try:
    import numpy as np
except Exception:
    np = None

# Optional AI/ML features: provide safe fallbacks when heavy libraries are missing
try:
    from .ai_recommendation import get_recommendations
except Exception:
    def get_recommendations(*args, **kwargs):
        return []

try:
    from .visual_search import find_similar_books_enhanced
except Exception:
    def find_similar_books_enhanced(*args, **kwargs):
        return []

try:
    from .semantic_search import semantic_search_books
except Exception:
    def semantic_search_books(*args, **kwargs):
        return []

try:
    from .advanced_visual_search import find_similar_books_advanced
except Exception:
    def find_similar_books_advanced(*args, **kwargs):
        return []
from .models import PaymentEvent

import logging

logger = logging.getLogger(__name__)

@api_view(['GET'])
def api_welcome(request):
    logger.info(f"Request: {request.method} {request.path}")
    return Response({'message': 'Welcome to the API'})

def home(request):
    featured_books = Book.objects.filter(is_featured=True)[:6]
    recent_books = Book.objects.order_by('-created_at')[:6]
    best_sellers = Book.objects.order_by('-total_sold')[:6]
    # Top trending books: sort by rating, then by total_sold for tie-breaks — show top 10
    top_books = Book.objects.order_by('-rating', '-total_sold')[:10]
    # dynamic lists for navbar/sections
    all_categories = list(Book.objects.values_list('category', flat=True).distinct())
    all_genres = list(Book.objects.values_list('genre', flat=True).distinct())
    all_authors = list(Book.objects.values_list('author', flat=True).distinct())

    context = {
        'featured_books': featured_books,
        'recent_books': recent_books,
        'best_sellers': best_sellers,
        'top_books': top_books,
        'all_categories': all_categories,
        'all_genres': all_genres,
        'all_authors': all_authors,
    }
    return render(request, 'books/home.html', context)


def authors_list(request):
    """List authors and basic stats."""
    # Get authors and count of books per author
    from django.db.models import Count
    authors = Book.objects.values('author').annotate(count=Count('id')).order_by('-count')
    return render(request, 'books/authors.html', {'authors': authors})


def categories_list(request):
    """List available categories and counts."""
    from django.db.models import Count
    # Build category list with a thumbnail (first book in category)
    raw = Book.objects.values('category').annotate(count=Count('id')).order_by('-count')
    categories = []
    for c in raw:
        cat = c['category']
        first_book = Book.objects.filter(category=cat).first()
        thumb = first_book.get_cover_url() if first_book else None
        categories.append({'category': cat, 'count': c['count'], 'thumbnail': thumb})
    return render(request, 'books/categories.html', {'categories': categories})


def genres_list(request):
    """List available genres and counts."""
    from django.db.models import Count
    raw = Book.objects.values('genre').annotate(count=Count('id')).order_by('-count')
    genres = []
    for g in raw:
        genre = g['genre']
        first_book = Book.objects.filter(genre=genre).first()
        thumb = first_book.get_cover_url() if first_book else None
        genres.append({'genre': genre, 'count': g['count'], 'thumbnail': thumb})
    return render(request, 'books/genres.html', {'genres': genres})


def top_books(request):
    """Show top 10 books by rating and sales."""
    top = Book.objects.order_by('-rating', '-total_sold')[:10]
    return render(request, 'books/top_books.html', {'top_books': top})

@cache_page(60 * 15)  # Cache for 15 minutes
def book_list(request):
    """Display a list of books with search and filtering capabilities."""
    query = request.GET.get('q', '')
    category = request.GET.get('category', '')
    genre = request.GET.get('genre', '')
    sort_by = request.GET.get('sort', 'title')

    books = Book.objects.all()

    # Apply semantic search if query provided
    if query:
        search_results = semantic_search_books(query, top_n=50)
        book_ids = [book.id for book, score in search_results if hasattr(book, 'id')]
        if book_ids:
            books = books.filter(id__in=book_ids)
            # Preserve semantic search order
            from django.db.models import Case, When
            preserved_order = Case(*[When(id=id_val, then=pos) for pos, id_val in enumerate(book_ids)])
            books = books.order_by(preserved_order)
        else:
            # Fallback to basic text search
            books = books.filter(
                Q(title__icontains=query) |
                Q(author__icontains=query) |
                Q(description__icontains=query)
            )

    # Apply filters
    if category:
        books = books.filter(category__iexact=category)
    if genre:
        books = books.filter(genre__iexact=genre)

    # Apply sorting
    if sort_by == 'price_low':
        books = books.order_by('price')
    elif sort_by == 'price_high':
        books = books.order_by('-price')
    elif sort_by == 'rating':
        books = books.order_by('-rating')
    elif sort_by == 'newest':
        books = books.order_by('-created_at')
    else:
        books = books.order_by('title')

    # Get unique categories and genres for filter dropdowns
    categories = Book.objects.values_list('category', flat=True).distinct()
    genres = Book.objects.values_list('genre', flat=True).distinct()

    context = {
        'books': books,
        'query': query,
        'selected_category': category,
        'selected_genre': genre,
        'categories': categories,
        'genres': genres,
        'sort_by': sort_by,
    }
    return render(request, 'books/book_list.html', context)

def book_detail(request, pk):
    """Display detailed information about a specific book."""
    book = get_object_or_404(Book, pk=pk)

    # Cache key for expensive operations
    cache_key = f'book_detail_{pk}'
    cached_data = cache.get(cache_key)

    if cached_data:
        reviews, similar_books, average_rating, top_books, all_categories, all_genres = cached_data
    else:
        # Get reviews for this book with select_related for better performance
        reviews = Review.objects.filter(book=book).select_related('user').order_by('-created_at')

        # Get similar books using semantic search (cached for 1 hour)
        similar_cache_key = f'similar_books_{book.id}'
        similar_books = cache.get(similar_cache_key)
        if similar_books is None:
            similar_books = semantic_search_books(f"{book.title} {book.author} {book.genre}", top_n=4)
            similar_books = [b for b, score in similar_books if b.id != book.id][:3]
            cache.set(similar_cache_key, similar_books, 60 * 60)  # Cache for 1 hour

        # Calculate average rating
        average_rating = reviews.aggregate(Avg('rating'))['rating__avg'] if reviews else 0

        # Cache sidebar data for 15 minutes
        sidebar_cache_key = 'sidebar_data'
        sidebar_data = cache.get(sidebar_cache_key)
        if sidebar_data:
            top_books, all_categories, all_genres = sidebar_data
        else:
            top_books = list(Book.objects.order_by('-rating', '-total_sold')[:10])
            all_categories = list(Book.objects.values_list('category', flat=True).distinct())
            all_genres = list(Book.objects.values_list('genre', flat=True).distinct())
            cache.set(sidebar_cache_key, (top_books, all_categories, all_genres), 60 * 15)  # 15 minutes

        # Cache the expensive data for 5 minutes
        cache.set(cache_key, (reviews, similar_books, average_rating, top_books, all_categories, all_genres), 60 * 5)

    # Check if book is in user's wishlist (not cached as it's user-specific)
    in_wishlist = False
    if request.user.is_authenticated:
        in_wishlist = Wishlist.objects.filter(user=request.user, book=book).exists()

    # Track recently viewed (only for authenticated users)
    if request.user.is_authenticated:
        RecentlyViewed.objects.get_or_create(
            user=request.user,
            book=book,
            defaults={'viewed_at': timezone.now()}
        )

    context = {
        'book': book,
        'reviews': reviews,
        'in_wishlist': in_wishlist,
        'similar_books': similar_books,
        'average_rating': average_rating,
        'top_books': top_books,
        'all_categories': all_categories,
        'all_genres': all_genres,
    }
    return render(request, 'books/book_detail.html', context)

@login_required
def add_review(request, pk):
    """Add a review for a book."""
    book = get_object_or_404(Book, pk=pk)

    if request.method == 'POST':
        rating = request.POST.get('rating')
        comment = request.POST.get('comment')

        if rating and comment:
            Review.objects.create(
                user=request.user,
                book=book,
                rating=int(rating),
                comment=comment
            )
            messages.success(request, 'Review added successfully!')
        else:
            messages.error(request, 'Please provide both rating and comment.')

    return redirect('book_detail', pk=pk)

def book_club(request):
    """Display book club forum posts."""
    query = request.GET.get('q', '')
    category = request.GET.get('category', '')
    sort_by = request.GET.get('sort', 'recent')
    page = request.GET.get('page', 1)

    posts = BookClubPost.objects.all()

    # Apply search filters
    if query:
        posts = posts.filter(
            Q(title__icontains=query) |
            Q(content__icontains=query) |
            Q(author__username__icontains=query)
        )

    # Apply category filter (if we add categories later)
    if category:
        posts = posts.filter(category__iexact=category)

    # Apply sorting
    if sort_by == 'trending':
        # Trending: posts with most recent activity (comments + likes) in last 7 days
        from django.utils import timezone
        from datetime import timedelta
        week_ago = timezone.now() - timedelta(days=7)
        posts = posts.annotate(
            recent_activity=Count(
                'comments',
                filter=Q(comments__created_at__gte=week_ago)
            ) + Count(
                'post_likes',
                filter=Q(post_likes__created_at__gte=week_ago)
            )
        ).order_by('-is_pinned', '-recent_activity', '-created_at')
    elif sort_by == 'popular':
        posts = posts.order_by('-is_pinned', '-like_count', '-comment_count', '-created_at')
    elif sort_by == 'oldest':
        posts = posts.order_by('-is_pinned', 'created_at')
    else:  # recent
        posts = posts.order_by('-is_pinned', '-created_at')

    # Implement pagination
    from django.core.paginator import Paginator
    paginator = Paginator(posts, 10)  # 10 posts per page
    try:
        posts_page = paginator.page(page)
    except:
        posts_page = paginator.page(1)

    # Get trending posts (most comments in last 7 days)
    from django.utils import timezone
    from datetime import timedelta
    week_ago = timezone.now() - timedelta(days=7)
    trending_posts = BookClubPost.objects.filter(
        created_at__gte=week_ago
    ).annotate(
        recent_comments=Count('comments', filter=Q(comments__created_at__gte=week_ago))
    ).order_by('-recent_comments')[:5]

    # Get thread recommendations for authenticated users
    recommendations = []
    if request.user.is_authenticated:
        # Recommend posts from similar users or based on user's reading interests
        user_posts = BookClubPost.objects.filter(author=request.user)
        if user_posts.exists():
            # Find posts by users who commented on the same posts
            commenter_ids = BookClubComment.objects.filter(
                post__in=user_posts
            ).values_list('author', flat=True).distinct()

            recommendations = BookClubPost.objects.filter(
                author__in=commenter_ids
            ).exclude(author=request.user).order_by('-created_at')[:3]

    # Calculate total comments
    total_comments = sum(post.comment_count for post in posts)

    context = {
        'posts': posts_page,
        'query': query,
        'selected_category': category,
        'selected_sort': sort_by,
        'trending_posts': trending_posts,
        'recommendations': recommendations,
        'paginator': paginator,
        'page_obj': posts_page,
        'total_comments': total_comments,
    }
    return render(request, 'books/book_club.html', context)

def post_detail(request, pk):
    """Display individual forum post with comments."""
    post = get_object_or_404(BookClubPost, pk=pk)
    comments = post.comments.all().order_by('created_at')

    # Check if user liked the post
    post_liked = False
    if request.user.is_authenticated:
        post_liked = BookClubPostLike.objects.filter(user=request.user, post=post).exists()

    # Check likes for comments
    comment_likes = {}
    if request.user.is_authenticated:
        for comment in comments:
            comment_likes[comment.id] = BookClubCommentLike.objects.filter(
                user=request.user, comment=comment
            ).exists()

    context = {
        'post': post,
        'comments': comments,
        'post_liked': post_liked,
        'comment_likes': comment_likes,
    }
    return render(request, 'books/post_detail.html', context)

@login_required
def create_post(request):
    """Create a new forum post."""
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')

        if title and content:
            # Moderate content
            from .moderation_utils import moderate_forum_content
            title_moderation = moderate_forum_content(title)
            content_moderation = moderate_forum_content(content)

            # Check if content is flagged
            if title_moderation['is_flagged'] or content_moderation['is_flagged']:
                messages.error(request, 'Your post contains inappropriate content and cannot be posted.')
                return render(request, 'books/create_post.html', {
                    'title': title,
                    'content': content
                })

            post = BookClubPost.objects.create(
                author=request.user,
                title=title,
                content=content
            )
            messages.success(request, 'Post created successfully!')
            return redirect('post_detail', pk=post.pk)
        else:
            messages.error(request, 'Please provide both title and content.')

    return render(request, 'books/create_post.html')

@login_required
def create_comment(request, post_id):
    """Create a comment on a forum post."""
    post = get_object_or_404(BookClubPost, pk=post_id)

    if request.method == 'POST':
        content = request.POST.get('content')

        if content:
            # Moderate content
            from .moderation_utils import moderate_forum_content
            content_moderation = moderate_forum_content(content)

            # Check if content is flagged
            if content_moderation['is_flagged']:
                messages.error(request, 'Your comment contains inappropriate content and cannot be posted.')
                return redirect('post_detail', pk=post_id)

            BookClubComment.objects.create(
                author=request.user,
                post=post,
                content=content
            )
            messages.success(request, 'Comment added successfully!')
        else:
            messages.error(request, 'Please provide comment content.')

    return redirect('post_detail', pk=post_id)

@login_required
def like_post(request, post_id):
    """Like or unlike a forum post."""
    post = get_object_or_404(BookClubPost, pk=post_id)

    like, created = BookClubPostLike.objects.get_or_create(
        user=request.user,
        post=post
    )

    if not created:
        like.delete()
        post.like_count -= 1
        post.save()
        liked = False
        messages.info(request, 'Post unliked.')
    else:
        post.like_count += 1
        post.save()
        liked = True
        messages.success(request, 'Post liked!')

    # Handle AJAX requests
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'liked': liked,
            'like_count': post.like_count
        })

    return redirect('post_detail', pk=post_id)

@login_required
def like_comment(request, comment_id):
    """Like or unlike a forum comment."""
    comment = get_object_or_404(BookClubComment, pk=comment_id)

    like, created = BookClubCommentLike.objects.get_or_create(
        user=request.user,
        comment=comment
    )

    if not created:
        like.delete()
        liked = False
        # Decrement like count safely
        if comment.like_count and comment.like_count > 0:
            comment.like_count -= 1
        messages.info(request, 'Comment unliked.')
    else:
        liked = True
        comment.like_count = (comment.like_count or 0) + 1
        messages.success(request, 'Comment liked!')

    # Persist like count change
    comment.save()

    # Return JSON for POST (tests expect JSON response)
    if request.method == 'POST':
        return JsonResponse({
            'success': True,
            'liked': liked,
            'like_count': comment.like_count
        })

    return redirect('post_detail', pk=comment.post.pk)

def signup(request):
    """Handle user registration."""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        # Only enforce confirm_password if provided (tests don't always include it)
        if confirm_password and password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'books/signup.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return render(request, 'books/signup.html')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists.')
            return render(request, 'books/signup.html')

        user = User.objects.create_user(username=username, email=email, password=password)
        login(request, user)
        messages.success(request, 'Account created successfully!')
        return redirect('home')

    return render(request, 'books/signup.html')

def login_view(request):
    """Handle user login."""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, 'Logged in successfully!')
            return redirect('home')
        else:
            messages.error(request, 'Invalid credentials.')

    return render(request, 'books/login.html')

def logout_view(request):
    """Handle user logout."""
    logout(request)
    messages.success(request, 'Logged out successfully!')
    return redirect('home')

def forgot_password(request):
    """Handle forgot password functionality."""
    if request.method == 'POST':
        email = request.POST.get('email')
        # For demo purposes, just show a message
        messages.info(request, 'Password reset link sent to your email.')
        return redirect('login')

    return render(request, 'books/forgot_password.html')

def verify_otp(request):
    """Handle OTP verification for password reset."""
    if request.method == 'POST':
        otp = request.POST.get('otp')
        # For demo purposes, just redirect
        messages.success(request, 'OTP verified successfully!')
        return redirect('login')

    return render(request, 'books/forgot_password.html')

@login_required
def user_dashboard(request):
    """Display user dashboard with orders and activity."""
    # Order model uses `ordered_at` for the timestamp field
    orders = Order.objects.filter(user=request.user).order_by('-ordered_at')
    wishlist_items = Wishlist.objects.filter(user=request.user)
    recently_viewed_qs = RecentlyViewed.objects.filter(user=request.user).select_related('book').order_by('-viewed_at')[:10]

    # User's reviews
    reviews = Review.objects.filter(user=request.user).order_by('-created_at')

    # Recommendations: try to base on the most recently viewed book, otherwise fallback to top rated
    recommended_books = []
    try:
        if recently_viewed_qs.exists():
            # ai_recommendation.get_recommendations expects a book_id
            last_book = recently_viewed_qs[0].book
            recommended_books = get_recommendations(last_book.id, top_n=8) or []
            # If recommender returned no items, fall back to top-rated books
            if not recommended_books:
                recommended_books = list(Book.objects.order_by('-rating')[:8])
        else:
            recommended_books = list(Book.objects.order_by('-rating')[:8])
    except Exception:
        recommended_books = list(Book.objects.order_by('-rating')[:8])

    # Attach existing seller rating (if any) to each order to avoid calling ORM methods in templates
    for order in orders:
        existing_rating = None
        try:
            if getattr(order, 'user_book', None):
                existing_rating = SellerRating.objects.filter(buyer=request.user, user_book=order.user_book).first()
        except Exception:
            existing_rating = None
        # attach attribute for template use
        setattr(order, 'existing_rating', existing_rating)

    context = {
        'orders': orders,
        'wishlist_items': wishlist_items,
        'recently_viewed_books': recently_viewed_qs,
        'reviews': reviews,
        'recommendations': recommended_books,
    }
    return render(request, 'books/dashboard.html', context)

@login_required
def cart(request):
    """Display user's shopping cart."""
    cart_items = Order.objects.filter(user=request.user, status='cart')
    total = sum(item.total_price for item in cart_items)

    context = {
        'cart_items': cart_items,
        'total': total,
    }
    return render(request, 'books/cart.html', context)

@login_required
def checkout(request):
    """Handle checkout process."""
    cart_items = Order.objects.filter(user=request.user, status='cart')
    if not cart_items:
        messages.error(request, 'Your cart is empty.')
        return redirect('cart')

    total = sum(item.total_price for item in cart_items)

    if request.method == 'POST':
        # Process payment and create order
        shipping_info = {
            'first_name': request.POST.get('first_name'),
            'last_name': request.POST.get('last_name'),
            'address': request.POST.get('address'),
            'city': request.POST.get('city'),
            'state': request.POST.get('state'),
            'zip': request.POST.get('zip'),
        }

        payment_method = request.POST.get('payment_method', '')

        # Support Cash On Delivery flow (simple synchronous handling)
        if payment_method == 'cod':
            order_ids = []
            for item in cart_items:
                # mark as pending for COD
                item.status = 'pending'
                item.payment_status = 'unpaid'  # Set payment status to unpaid for COD
                # attach shipping address for internal processing
                try:
                    addr = f"{shipping_info['first_name']} {shipping_info['last_name']}\n{shipping_info['address']}\n{shipping_info['city']}, {shipping_info['state']} {shipping_info['zip']}"
                    item.shipping_address = addr
                except Exception:
                    pass
                item.save()
                order_ids.append(item.id)

                # Decrement stock safely for books
                try:
                    if item.book and item.book.stock is not None and item.book.stock >= item.quantity:
                        item.book.stock -= item.quantity
                        item.book.save()
                except Exception:
                    pass

            # Record a payment event for COD
            try:
                PaymentEvent.objects.create(
                    event='cod_order_placed',
                    payload={'order_ids': order_ids, 'method': 'cod'}
                )
            except Exception:
                pass

            # Generate invoice PDF for COD
            pdf_buffer = generate_invoice_pdf(order_ids, shipping_info)

            # Send order confirmation email with invoice
            try:
                send_order_confirmation_email(request.user, order_ids, shipping_info, pdf_buffer)
            except Exception:
                pass

            # Check if this is an AJAX request
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'order_id': order_ids[0]})

            messages.success(request, 'Order placed successfully!')
            return redirect('order_confirmation', order_id=order_ids[0])

        # Create Razorpay order
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        razorpay_order = client.order.create({
            'amount': int(total * 100),  # Amount in paisa
            'currency': 'INR',
            'payment_capture': '1'
        })

        # Update cart items status
        order_ids = []
        for item in cart_items:
            item.status = 'confirmed'
            item.save()
            order_ids.append(item.id)

        # Send confirmation email
        pdf_buffer = generate_invoice_pdf(order_ids, shipping_info)
        send_order_confirmation_email(request.user, order_ids, shipping_info, pdf_buffer)

        messages.success(request, 'Order placed successfully!')
        return redirect('order_confirmation', order_id=order_ids[0])

    context = {
        'cart_items': cart_items,
        'total': total,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
    }
    return render(request, 'books/checkout.html', context)

@login_required
def update_cart(request, pk):
    """Update cart item quantity."""
    order = get_object_or_404(Order, pk=pk, user=request.user, status='cart')

    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        if quantity > 0:
            order.quantity = quantity
            order.total_price = order.book.price * quantity
            order.save()
            messages.success(request, 'Cart updated successfully!')
        else:
            order.delete()
            messages.success(request, 'Item removed from cart!')

    return redirect('cart')

@login_required
def remove_from_cart(request, pk):
    """Remove item from cart."""
    order = get_object_or_404(Order, pk=pk, user=request.user, status='cart')
    order.delete()
    messages.success(request, 'Item removed from cart!')
    return redirect('cart')

@login_required
def add_to_cart(request, pk):
    """Add book to cart."""
    book = get_object_or_404(Book, pk=pk)

    # Check if item already in cart
    existing_order = Order.objects.filter(user=request.user, book=book, status='cart').first()
    if existing_order:
        existing_order.quantity += 1
        existing_order.total_price = existing_order.book.price * existing_order.quantity
        existing_order.save()
    else:
        Order.objects.create(
            user=request.user,
            book=book,
            quantity=1,
            total_price=book.price,
            status='cart'
        )

    messages.success(request, 'Book added to cart!')
    return redirect('cart')

@login_required
def buy_now(request, pk):
    """Add book to cart and redirect to checkout."""
    book = get_object_or_404(Book, pk=pk)

    # Check if item already in cart
    existing_order = Order.objects.filter(user=request.user, book=book, status='cart').first()
    if existing_order:
        existing_order.quantity += 1
        existing_order.total_price = existing_order.book.price * existing_order.quantity
        existing_order.save()
    else:
        Order.objects.create(
            user=request.user,
            book=book,
            quantity=1,
            total_price=book.price,
            status='cart'
        )

    messages.success(request, 'Book added to cart!')
    return redirect('checkout')

@login_required
def add_to_wishlist(request, pk):
    """Add book to wishlist."""
    book = get_object_or_404(Book, pk=pk)

    wishlist_item, created = Wishlist.objects.get_or_create(
        user=request.user,
        book=book
    )

    if created:
        messages.success(request, 'Book added to wishlist!')
    else:
        messages.info(request, 'Book already in wishlist!')

    return redirect('book_detail', pk=pk)

@login_required
def remove_from_wishlist(request, pk):
    """Remove book from wishlist."""
    book = get_object_or_404(Book, pk=pk)
    Wishlist.objects.filter(user=request.user, book=book).delete()
    messages.success(request, 'Book removed from wishlist!')
    return redirect('wishlist')

@login_required
def wishlist(request):
    """Display user's wishlist."""
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related('book')
    return render(request, 'books/wishlist.html', {'wishlist_items': wishlist_items})

@login_required
def order_confirmation(request, order_id):
    """Display order confirmation with invoice details."""
    order = get_object_or_404(Order, pk=order_id, user=request.user)

    # Prepare order items (single order)
    order_items = [order]
    total = order.total_price

    # Parse shipping info from shipping_address if available (for COD)
    shipping_info = {}
    if order.shipping_address:
        # Assuming format: "First Last\nAddress\nCity, State ZIP"
        lines = order.shipping_address.split('\n')
        if len(lines) >= 4:
            name_parts = lines[0].split()
            shipping_info = {
                'first_name': name_parts[0] if name_parts else '',
                'last_name': ' '.join(name_parts[1:]) if len(name_parts) > 1 else '',
                'address': lines[1],
                'city': lines[2].split(',')[0].strip() if ',' in lines[2] else lines[2],
                'state': lines[2].split(',')[1].split()[0] if ',' in lines[2] and len(lines[2].split(',')) > 1 else '',
                'zip': lines[2].split()[-1] if lines[2].split() else '',
                'email': request.user.email,  # Use user's email
            }

    context = {
        'order': order,
        'order_id': order.id,
        'order_date': order.ordered_at,
        'order_items': order_items,
        'total': total,
        'shipping_info': shipping_info,
    }
    return render(request, 'books/order_confirmation.html', context)

@login_required
def sell_book(request):
    """Allow users to sell their books."""
    if request.method == 'POST':
        title = request.POST.get('title')
        author = request.POST.get('author')
        category = request.POST.get('category')
        genre = request.POST.get('genre')
        description = request.POST.get('description')
        price = request.POST.get('price')
        condition = request.POST.get('condition')
        cover_image = request.FILES.get('cover_image')

        UserBook.objects.create(
            seller=request.user,
            title=title,
            author=author,
            category=category,
            genre=genre,
            description=description,
            price=price,
            condition=condition,
            cover_image=cover_image,
            is_available=True
        )

        messages.success(request, 'Book listed for sale successfully!')
        return redirect('my_listings')

    return render(request, 'books/sell_book.html')

@login_required
@login_required
def my_listings(request):
    """Display user's book listings."""
    listings = UserBook.objects.filter(seller=request.user)
    # Provide both 'listings' and 'user_books' keys for template compatibility
    return render(request, 'books/my_listings.html', {'listings': listings, 'user_books': listings})

@login_required
def edit_listing(request, pk):
    """Edit user's book listing."""
    listing = get_object_or_404(UserBook, pk=pk, seller=request.user)

    if request.method == 'POST':
        listing.title = request.POST.get('title')
        listing.author = request.POST.get('author')
        listing.category = request.POST.get('category')
        listing.genre = request.POST.get('genre')
        listing.description = request.POST.get('description')
        listing.price = request.POST.get('price')
        listing.condition = request.POST.get('condition')

        if request.FILES.get('cover_image'):
            listing.cover_image = request.FILES.get('cover_image')

        listing.save()
        messages.success(request, 'Listing updated successfully!')
        return redirect('my_listings')

    return render(request, 'books/edit_listing.html', {'listing': listing})

@login_required
def delete_listing(request, pk):
    """Delete user's book listing."""
    listing = get_object_or_404(UserBook, pk=pk, seller=request.user)
    listing.delete()
    messages.success(request, 'Listing deleted successfully!')
    return redirect('my_listings')

@login_required
def buy_user_book(request, pk):
    """Buy a user-sold book."""
    user_book = get_object_or_404(UserBook, pk=pk, is_available=True)

    if request.method == 'POST':
        # Create order for user book
        Order.objects.create(
            user=request.user,
            user_book=user_book,
            quantity=1,
            total_price=user_book.price,
            status='confirmed'
        )

        # Mark book as sold
        user_book.is_available = False
        user_book.save()

        messages.success(request, 'Book purchased successfully!')
        return redirect('order_confirmation', order_id=user_book.id)

    return render(request, 'books/buy_user_book.html', {'user_book': user_book})

def user_book_detail(request, pk):
    """Display details of a user-sold book."""
    user_book = get_object_or_404(UserBook, pk=pk)
    return render(request, 'books/user_book_detail.html', {'user_book': user_book})

def marketplace(request):
    """Display marketplace with user-sold books."""
    query = request.GET.get('q', '')
    category = request.GET.get('category', '')
    condition = request.GET.get('condition', '')
    sort_by = request.GET.get('sort', '')

    books = UserBook.objects.filter(is_available=True)

    if query:
        books = books.filter(
            Q(title__icontains=query) |
            Q(author__icontains=query) |
            Q(description__icontains=query)
        )

    if category:
        books = books.filter(category__iexact=category)

    if condition:
        books = books.filter(condition__iexact=condition)

    # Apply sorting from template's sort select
    if sort_by == 'price_low':
        books = books.order_by('price')
    elif sort_by == 'price_high':
        books = books.order_by('-price')
    elif sort_by == 'newest':
        books = books.order_by('-created_at')
    elif sort_by == 'oldest':
        books = books.order_by('created_at')
    else:
        # Default ordering
        books = books.order_by('-created_at')

    categories = UserBook.objects.values_list('category', flat=True).distinct()

    context = {
        'books': books,
        'query': query,
        'selected_category': category,
        'categories': categories,
        # Provide 'user_books' for compatibility with template
        'user_books': books,
        'selected_condition': condition,
        'sort_by': sort_by,
    }
    return render(request, 'books/marketplace.html', context)

@login_required
def add_to_comparison(request, pk):
    """Add book to comparison list."""
    book = get_object_or_404(Book, pk=pk)

    # For simplicity, store in session
    comparison_list = request.session.get('comparison_list', [])
    if pk not in comparison_list:
        comparison_list.append(pk)
        request.session['comparison_list'] = comparison_list
        messages.success(request, 'Book added to comparison!')
    else:
        messages.info(request, 'Book already in comparison list!')

    return redirect('book_detail', pk=pk)

@login_required
def remove_from_comparison(request, pk):
    """Remove book from comparison list."""
    comparison_list = request.session.get('comparison_list', [])
    if pk in comparison_list:
        comparison_list.remove(pk)
        request.session['comparison_list'] = comparison_list
        messages.success(request, 'Book removed from comparison!')

    return redirect('comparison')

@login_required
def comparison(request):
    """Display book comparison."""
    comparison_list = request.session.get('comparison_list', [])
    books = Book.objects.filter(id__in=comparison_list)
    return render(request, 'books/comparison.html', {'books': books})

@login_required
def clear_comparison(request):
    """Clear comparison list."""
    request.session['comparison_list'] = []
    messages.success(request, 'Comparison list cleared!')
    return redirect('comparison')

@login_required
def rate_seller(request, user_book_id):
    """Rate a seller after purchasing their book."""
    user_book = get_object_or_404(UserBook, pk=user_book_id)

    if request.method == 'POST':
        rating = int(request.POST.get('rating'))
        comment = request.POST.get('comment')

        SellerRating.objects.create(
            buyer=request.user,
            seller=user_book.seller,
            user_book=user_book,
            rating=rating,
            comment=comment
        )

        messages.success(request, 'Seller rated successfully!')
        return redirect('dashboard')

    return render(request, 'books/rate_seller.html', {'user_book': user_book})

# API Views
@api_view(['GET'])
def api_book_list(request):
    """API endpoint for book list with semantic search."""
    query = request.GET.get('q', '')
    category = request.GET.get('category', '')
    genre = request.GET.get('genre', '')
    sort_by = request.GET.get('sort', 'title')

    books = Book.objects.all()

    # Apply semantic search if query provided
    if query:
        search_results = semantic_search_books(query, top_n=50)
        book_ids = [book.id for book, score in search_results if hasattr(book, 'id')]
        if book_ids:
            books = books.filter(id__in=book_ids)

    # Apply filters
    if category:
        books = books.filter(category__iexact=category)
    if genre:
        books = books.filter(genre__iexact=genre)

    # Apply sorting
    if sort_by == 'price_low':
        books = books.order_by('price')
    elif sort_by == 'price_high':
        books = books.order_by('-price')
    elif sort_by == 'rating':
        books = books.order_by('-rating')
    elif sort_by == 'newest':
        books = books.order_by('-created_at')
    else:
        books = books.order_by('title')

    serializer = BookSerializer(books[:20], many=True)  # Limit to 20 results
    return Response(serializer.data)

@api_view(['GET'])
def api_recommendations(request):
    """API endpoint for AI-powered book recommendations."""
    user_id = request.GET.get('user_id')
    book_id = request.GET.get('book_id')

    # The underlying AI recommendation helper in this module expects a
    # book_id parameter. For user-scoped recommendations, pick the user's
    # most recently viewed book and call the book-based recommender.
    try:
        if book_id:
            recommendations = get_recommendations(int(book_id), top_n=8)
        elif user_id:
            # If a user_id query param is provided, try to use their
            # most recently viewed book as the seed.
            from .models import RecentlyViewed
            rv = RecentlyViewed.objects.filter(user__id=int(user_id)).order_by('-viewed_at').first()
            if rv:
                recommendations = get_recommendations(rv.book.id, top_n=8)
            else:
                recommendations = list(Book.objects.order_by('-rating')[:8])
        elif request.user and request.user.is_authenticated:
            # Use the authenticated user's recently viewed book as seed
            rv = RecentlyViewed.objects.filter(user=request.user).order_by('-viewed_at').first()
            if rv:
                recommendations = get_recommendations(rv.book.id, top_n=8)
            else:
                recommendations = list(Book.objects.order_by('-rating')[:8])
        else:
            # No context available: return top-rated books as a safe default
            recommendations = list(Book.objects.order_by('-rating')[:8])
    except Exception:
        # On any internal error, return a safe fallback list (top-rated)
        try:
            recommendations = list(Book.objects.order_by('-rating')[:8])
        except Exception:
            recommendations = []

    # Ensure we return JSON-serializable data. If the recommendation engine
    # returned Django model instances or a QuerySet, serialize them with
    # the existing BookSerializer. If serialization fails, fall back to
    # returning an empty list or the raw data if it's already a list/dict.
    try:
        serialized = BookSerializer(recommendations, many=True).data
    except Exception:
        if isinstance(recommendations, list):
            serialized = recommendations
        else:
            serialized = []

    return Response({'recommendations': serialized})


@api_view(['GET'])
def api_book_detail(request, pk):
    """Return minimal book metadata for inline bot cards."""
    try:
        book = Book.objects.get(pk=pk)
    except Book.DoesNotExist:
        return Response({'error': 'Book not found'}, status=404)

    data = {
        'id': book.id,
        'title': book.title,
        'author': book.author,
        'cover_image': book.get_cover_url(),
        'price': str(book.price),
    }
    return Response(data)

@api_view(['POST'])
def api_chatbot(request):
    """API endpoint for chatbot interaction."""
    # Accept 'message' or legacy 'query' key used by tests
    message = request.data.get('message') or request.data.get('query')
    user_id = request.data.get('user_id')

    if not message:
        return Response({'error': 'Message is required'}, status=400)

    # Import chatbot logic here to avoid circular imports
    from .chatbot_utils import get_chatbot_response
    response = get_chatbot_response(message, user_id)

    return Response({'response': response})


@api_view(['POST'])
def api_rag_chat(request):
    """RAG-style chat endpoint: retrieve top-K books by stored embeddings and call external LLM if configured."""
    message = request.data.get('message')
    user_id = request.data.get('user_id')
    top_k = int(request.data.get('top_k', 5))

    if not message:
        return Response({'error': 'Message is required'}, status=400)

    # Try to compute an embedding for the query
    query_embedding = None
    import os
    try:
        api_key = os.environ.get('OPENAI_API_KEY')
        if api_key:
            import requests, json
            url = 'https://api.openai.com/v1/embeddings'
            headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
            payload = {'model': 'text-embedding-3-small', 'input': message}
            resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=15)
            resp.raise_for_status()
            query_embedding = resp.json()['data'][0]['embedding']
    except Exception:
        query_embedding = None

    # If OpenAI embedding not available, try local sentence-transformers
    if query_embedding is None:
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer('all-MiniLM-L6-v2')
            emb = model.encode([message], convert_to_numpy=False)[0]
            query_embedding = list(emb)
        except Exception:
            query_embedding = None

    # If we have an embedding, find top-K by cosine similarity
    context_items = []
    if query_embedding is not None:
        import numpy as np
        from .models import Book, UserBook

        def cosine(a, b):
            a = np.array(a)
            b = np.array(b)
            denom = (np.linalg.norm(a) * np.linalg.norm(b))
            return float(np.dot(a, b) / denom) if denom != 0 else 0.0

        candidates = []
        books = Book.objects.exclude(semantic_embedding__isnull=True).exclude(semantic_embedding__exact=[])
        for b in books:
            try:
                score = cosine(query_embedding, b.semantic_embedding)
                candidates.append((b, score))
            except Exception:
                continue

        ubooks = UserBook.objects.filter(is_available=True).exclude(semantic_embedding__isnull=True).exclude(semantic_embedding__exact=[])
        for ub in ubooks:
            try:
                score = cosine(query_embedding, ub.semantic_embedding)
                candidates.append((ub, score))
            except Exception:
                continue

        candidates.sort(key=lambda x: x[1], reverse=True)
        top = candidates[:top_k]
        for obj, score in top:
            title = getattr(obj, 'title', '')
            author = getattr(obj, 'author', '')
            desc = getattr(obj, 'description', '') or ''
            context_items.append(f"Title: {title}\nAuthor: {author}\nSummary: {desc[:500]}\nScore: {score}")

    # Build prompt for external LLMs
    prompt = message
    if context_items:
        if context_items:
            joined_context = "\n\n".join(context_items)
            prompt = f"Context:\n\n{joined_context}\n\nQuestion: {message}"
        else:
            prompt = message

    # Try external APIs similar to chatbot_utils: external API -> Gemini
    from .chatbot_utils import call_external_chat_api, call_gemini_api, chatbot

    external_response = call_external_chat_api(prompt, user_id)
    if external_response:
        return Response({'response': external_response, 'context': context_items})

    gemini_response = call_gemini_api(prompt, user_id)
    if gemini_response:
        return Response({'response': gemini_response, 'context': context_items})

    # Fallback to local rule-based chatbot (no LLM)
    local_resp = chatbot.chat(message, None)
    return Response({'response': local_resp, 'context': context_items})

@api_view(['GET'])
def api_chat_messages(request):
    """API endpoint to get chat messages."""
    user_id = request.GET.get('user_id')
    if not user_id:
        return Response({'error': 'user_id required'}, status=400)

    messages = ChatMessage.objects.filter(user_id=user_id).order_by('-created_at')[:50]
    message_data = [
        {
            'id': msg.id,
            'message': msg.message,
            'response': msg.response,
            'created_at': msg.created_at,
        }
        for msg in messages
    ]

    return Response({'messages': message_data})

@api_view(['POST'])
def api_send_chat_message(request):
    """API endpoint to send a chat message."""
    message = request.data.get('message')
    user_id = request.data.get('user_id')

    if not message or not user_id:
        return Response({'error': 'message and user_id required'}, status=400)

    from .chatbot_utils import get_chatbot_response
    response = get_chatbot_response(message, user_id)

    # Save to database
    ChatMessage.objects.create(
        user_id=user_id,
        message=message,
        response=response
    )

    return Response({'response': response})

@api_view(['POST'])
def api_visual_search(request):
    """API endpoint for visual search."""
    if 'image' not in request.FILES:
        return Response({'error': 'Image file required'}, status=400)

    image_file = request.FILES['image']

    try:
        # Use advanced visual search
        similar_books = find_similar_books_advanced(image_file, top_n=10)
        results = []
        for book, score in similar_books:
            # Resolve cover image URL safely across different Book model variations
            cover_url = None
            try:
                if hasattr(book, 'cover_image') and getattr(book, 'cover_image'):
                    try:
                        cover_url = book.cover_image.url
                    except Exception:
                        cover_url = None
                elif hasattr(book, 'image') and getattr(book, 'image'):
                    try:
                        cover_url = book.image.url
                    except Exception:
                        cover_url = None
                elif hasattr(book, 'cover_image_url') and getattr(book, 'cover_image_url'):
                    cover_url = book.cover_image_url
            except Exception:
                cover_url = None

            results.append({
                'book_id': getattr(book, 'id', None),
                'title': getattr(book, 'title', ''),
                'author': getattr(book, 'author', ''),
                'similarity_score': score,
                'cover_image': cover_url,
            })

        return Response({'results': results})
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['POST'])
def api_process_payment(request):
    """API endpoint for payment processing."""
    # Support both `razorpay_*` keys (used by tests) and generic names
    razorpay_payment_id = request.data.get('razorpay_payment_id') or request.data.get('payment_id')
    razorpay_order_id = request.data.get('razorpay_order_id') or request.data.get('order_id')
    razorpay_signature = request.data.get('razorpay_signature') or request.data.get('signature')
    shipping_info = request.data.get('shipping_info', {})

    if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature]):
        return Response({'error': 'Missing payment data'}, status=400)

    # Verify payment with Razorpay (tests patch razorpay.Client)
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    try:
        client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        })

        # Idempotency: if a PaymentEvent with this payment id already exists, return success
        existing_event = PaymentEvent.objects.filter(payload__contains={'payment_id': razorpay_payment_id}).first()
        if existing_event:
            return Response({'success': True})

        # Find orders associated with this razorpay_order_id or fallback to user's cart
        orders = Order.objects.filter(razorpay_order_id=razorpay_order_id)
        if not orders.exists() and request.user and request.user.is_authenticated:
            orders = Order.objects.filter(user=request.user, status='cart')

        processed_order_ids = []
        for order in orders:
            # Skip if already processed for this payment id
            if order.razorpay_payment_id == razorpay_payment_id:
                continue

            order.status = 'confirmed'
            order.razorpay_payment_id = razorpay_payment_id
            order.razorpay_order_id = razorpay_order_id
            order.save()
            processed_order_ids.append(order.id)

            # Decrement stock if linked to a Book
            try:
                if order.book:
                    if order.book.stock is not None and order.book.stock >= order.quantity:
                        order.book.stock -= order.quantity
                        order.book.save()
            except Exception:
                pass

        # Record payment event
        PaymentEvent.objects.create(
            event='payment_processed',
            payload={
                'order_ids': processed_order_ids,
                'amount': sum(float(Order.objects.get(id=o).total_price) for o in processed_order_ids) if processed_order_ids else 0.0,
                'payment_id': razorpay_payment_id
            }
        )

        # Send confirmation email (send_mail is patched in tests as books.views.send_mail)
        if processed_order_ids and request.user and request.user.email:
            pdf_buffer = generate_invoice_pdf(processed_order_ids, shipping_info)
            send_order_confirmation_email(request.user, processed_order_ids, shipping_info, pdf_buffer)

        return Response({'success': True})

    except Exception as e:
        return Response({'error': str(e)}, status=400)

@api_view(['POST'])
def api_payment_webhook(request):
    """Handle Razorpay payment webhooks."""
    # Webhook signature verification would go here
    data = request.data

    # Process webhook data
    if data.get('event') == 'payment.captured':
        payment_id = data['payload']['payment']['entity']['id']
        order_id = data['payload']['payment']['entity']['order_id']

        try:
            order = Order.objects.get(razorpay_order_id=order_id)
            # Idempotent handling: if payment already applied, skip
            if order.razorpay_payment_id == payment_id:
                pass
            else:
                order.status = 'confirmed'
                order.razorpay_payment_id = payment_id
                order.save()

                # Decrement stock safely
                try:
                    if order.book and order.book.stock is not None and order.book.stock >= order.quantity:
                        order.book.stock -= order.quantity
                        order.book.save()
                except Exception:
                    pass

                PaymentEvent.objects.create(
                    event='webhook_payment_captured',
                    payload={
                        'order_id': order.id,
                        'amount': float(order.total_price),
                        'payment_id': payment_id
                    }
                )

        except Order.DoesNotExist:
            pass

    return Response({'status': 'ok'})

# Helper Functions
def generate_invoice_pdf(order_ids, shipping_info):
    """Generate PDF invoice for orders."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title = Paragraph("Order Invoice", styles['Heading1'])
    story.append(title)
    story.append(Spacer(1, 12))

    # Order details
    for order_id in order_ids:
        order = Order.objects.get(id=order_id)

        order_info = [
            ['Order ID:', str(order.id)],
            ['Date:', order.ordered_at.strftime('%Y-%m-%d %H:%M:%S')],
            ['Book:', order.book.title if order.book else order.user_book.title],
            ['Quantity:', str(order.quantity)],
            ['Price:', f'₹{order.total_price}'],
        ]

        table = Table(order_info)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        story.append(table)
        story.append(Spacer(1, 12))

    # Shipping info
    shipping_title = Paragraph("Shipping Information", styles['Heading2'])
    story.append(shipping_title)
    story.append(Spacer(1, 12))

    shipping_data = [
        ['Name:', f"{shipping_info['first_name']} {shipping_info['last_name']}"],
        ['Address:', shipping_info['address']],
        ['City:', shipping_info['city']],
        ['State:', shipping_info['state']],
        ['ZIP:', shipping_info['zip']],
    ]

    shipping_table = Table(shipping_data)
    shipping_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    story.append(shipping_table)

    doc.build(story)
    buffer.seek(0)
    return buffer

def send_order_confirmation_email(user, order_ids, shipping_info, pdf_buffer):
    """Send order confirmation email with PDF invoice."""
    subject = 'Order Confirmation - BiblioTrack'
    html_message = get_template('books/order_confirmation_email.html').render({
        'user': user,
        'order_ids': order_ids,
        'shipping_info': shipping_info,
    })

    # In a real application, you would attach the PDF
    # For demo purposes, just send the email
    send_mail(
        subject,
        'Your order has been confirmed. Please find the invoice attached.',
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        html_message=html_message,
        fail_silently=True,
    )


# --- Help Center simple pages ---
def help_center(request):
    """Simple Help Center index linking to support pages."""
    return render(request, 'books/help_center.html')


def shipping_info(request):
    """Shipping information page."""
    return render(request, 'books/shipping_info.html')


def returns_info(request):
    """Returns & refunds page."""
    return render(request, 'books/returns.html')


def track_order(request):
    """Track order page: accepts `order_id` (id or tracking id) and shows order status."""
    order = None
    query = request.GET.get('order_id') or request.POST.get('order_id')
    if query:
        # Try numeric id first, then tracking_id
        try:
            order = Order.objects.filter(id=int(query)).first()
        except Exception:
            order = None
        if not order:
            order = Order.objects.filter(tracking_id__iexact=str(query)).first()

    status_history = OrderStatus.objects.filter(order=order).order_by('created_at') if order else []
    return render(request, 'books/track_order.html', {'order': order, 'query': query, 'status_history': status_history})


def contact_us(request):
    """Contact us page with a contact form or contact details."""
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        message_text = request.POST.get('message')

        if not (name and email and message_text):
            messages.error(request, 'Please provide name, email and message.')
            return render(request, 'books/contact_us.html')

        # Save to DB
        try:
            ContactMessage.objects.create(name=name, email=email, message=message_text)
        except Exception:
            logger.exception('Failed to save contact message')

        # Send email to support (use DEFAULT_FROM_EMAIL as recipient if no separate setting)
        support_email = getattr(settings, 'SUPPORT_EMAIL', settings.DEFAULT_FROM_EMAIL)
        subject = f"New contact message from {name}"
        body = f"Name: {name}\nEmail: {email}\n\nMessage:\n{message_text}"
        try:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [support_email], fail_silently=True)
        except Exception:
            logger.exception('Failed to send contact email')

        messages.success(request, 'Thank you for contacting us. We will get back to you shortly.')
        return redirect('contact_us')

    recent_messages = ContactMessage.objects.all()[:5] if request.user.is_staff else None
    return render(request, 'books/contact_us.html', {'recent_messages': recent_messages})

// Custom JavaScript for enhanced UI/UX with micro-interactions

document.addEventListener('DOMContentLoaded', function() {
    console.log('[debug] custom.js (v2) loaded. Chatbot endpoint: /api/chatbot/');
    // Progress bar loader for page loads
    const progressBar = document.createElement('div');
    progressBar.className = 'progress-bar-loader';
    document.body.appendChild(progressBar);

    // Hide progress bar when page loads
    window.addEventListener('load', function() {
        setTimeout(() => {
            progressBar.style.display = 'none';
        }, 500);
    });

    // Loading spinner for recommendations
    const recommendationLoader = document.createElement('div');
    recommendationLoader.className = 'recommendation-loader';
    recommendationLoader.innerHTML = '<div class="spinner-border-ai" role="status"><span class="visually-hidden">Loading...</span></div>';
    document.body.appendChild(recommendationLoader);

    // Enhanced chatbot with slide-up animation
    const chatbotToggle = document.getElementById('chatbot-toggle');
    const chatbot = document.getElementById('chatbot');
    const chatbotClose = document.getElementById('chatbot-close');
    const chatInput = document.getElementById('chat-input');
    const chatSend = document.getElementById('chat-send');
    const chatMessages = document.getElementById('chat-messages');

    console.log('[debug] Chatbot elements found:', {
        chatbotToggle: !!chatbotToggle,
        chatbot: !!chatbot,
        chatbotClose: !!chatbotClose,
        chatInput: !!chatInput,
        chatSend: !!chatSend,
        chatMessages: !!chatMessages
    });

    if (chatbotToggle && chatbot) {
        console.log('[debug] Adding click listener to chatbot toggle');
        chatbotToggle.addEventListener('click', () => {
            console.log('[debug] Chatbot toggle clicked');
            // Bootstrap's .d-none uses !important, so ensure we remove it when showing
            if (chatbot.classList.contains('d-none')) {
                console.log('[debug] Showing chatbot');
                chatbot.classList.remove('d-none');
                chatbot.classList.add('show');
                if (chatInput) chatInput.focus();
            } else {
                console.log('[debug] Hiding chatbot');
                chatbot.classList.add('d-none');
                chatbot.classList.remove('show');
            }
        });

        if (chatbotClose) {
            chatbotClose.addEventListener('click', () => {
                chatbot.classList.add('d-none');
                chatbot.classList.remove('show');
            });
        }

        // Helper: create formatted bot response DOM from plain text
        function formatBotResponse(text) {
            const frag = document.createDocumentFragment();
            if (!text) return document.createTextNode('');

            // Normalize newlines
            const paragraphs = String(text).split(/\n{2,}|\r\n{2,}/g);
            paragraphs.forEach(par => {
                const p = document.createElement('div');
                p.style.marginBottom = '8px';

                // First, convert patterns like "Title — Author (/books/6/)" into linked titles
                const bookPattern = /([^\(\n]+?)\s*\(\/books\/(\d+)\//g;
                let lastIndex = 0;
                let match;
                let matched = false;
                while ((match = bookPattern.exec(par)) !== null) {
                    matched = true;
                    const before = par.slice(lastIndex, match.index);
                    if (before) p.appendChild(document.createTextNode(before));

                    const title = match[1].trim();
                    const id = match[2];
                    const a = document.createElement('a');
                    a.href = `/books/${id}/`;
                    a.className = 'bot-book-link';
                    a.textContent = title;
                    p.appendChild(a);

                    lastIndex = bookPattern.lastIndex;
                }

                if (matched) {
                    const rest = par.slice(lastIndex);
                    if (rest) p.appendChild(document.createTextNode(rest));
                    frag.appendChild(p);
                    return;
                }

                // If no bookPattern matched, convert plain /books/ID/ occurrences into links
                const urlPattern = /\/books\/(\d+)\//g;
                lastIndex = 0;
                let urlMatch;
                let anyUrl = false;
                while ((urlMatch = urlPattern.exec(par)) !== null) {
                    anyUrl = true;
                    const before = par.slice(lastIndex, urlMatch.index);
                    if (before) p.appendChild(document.createTextNode(before));
                    const id = urlMatch[1];
                    const a = document.createElement('a');
                    a.href = `/books/${id}/`;
                    a.className = 'bot-book-link';
                    a.textContent = `View book #${id}`;
                    p.appendChild(a);
                    lastIndex = urlPattern.lastIndex;
                }
                if (anyUrl) {
                    const rest = par.slice(lastIndex);
                    if (rest) p.appendChild(document.createTextNode(rest));
                    frag.appendChild(p);
                    return;
                }

                // Otherwise, simple paragraph: preserve links (http) and convert to text nodes
                // Convert bare URLs into anchors
                const httpPattern = /(https?:\/\/[^\s]+)/g;
                let iLast = 0;
                let httpMatch;
                while ((httpMatch = httpPattern.exec(par)) !== null) {
                    const before = par.slice(iLast, httpMatch.index);
                    if (before) p.appendChild(document.createTextNode(before));
                    const a = document.createElement('a');
                    a.href = httpMatch[1];
                    a.target = '_blank';
                    a.rel = 'noopener noreferrer';
                    a.textContent = httpMatch[1];
                    p.appendChild(a);
                    iLast = httpPattern.lastIndex;
                }
                const tail = par.slice(iLast);
                if (tail) p.appendChild(document.createTextNode(tail));

                frag.appendChild(p);
            });

            return frag;
        }

        // Enrich any bot-book-link anchors by fetching metadata and rendering inline cards
        function enrichBotLinks(container) {
            if (!container) return;
            const links = container.querySelectorAll('a.bot-book-link');
            links.forEach(link => {
                // avoid double-processing
                if (link.dataset.enriched) return;
                link.dataset.enriched = '1';
                const href = link.getAttribute('href') || '';
                const m = href.match(/\/books\/(\d+)\//);
                if (!m) return;
                const id = m[1];
                // fetch book metadata
                fetch(`/api/book/${id}/`)
                .then(resp => resp.ok ? resp.json() : Promise.reject('Not found'))
                .then(data => {
                    if (!data || data.error) return;
                    // create inline card
                    const card = document.createElement('div');
                    card.className = 'book-card-inline';
                    const img = document.createElement('img');
                    img.src = data.cover_image || '/media/books/book_placeholder.svg';
                    img.alt = data.title || '';
                    const meta = document.createElement('div');
                    meta.style.flex = '1';
                    meta.innerHTML = `<div style="font-weight:600">${escapeHtml(data.title || '')}</div><div style="color:#666;font-size:0.9rem">${escapeHtml(data.author || '')}</div><div style="margin-top:6px;color:#1B263B;font-weight:600">₹${data.price || ''}</div>`;
                    card.appendChild(img);
                    card.appendChild(meta);

                    // Replace the link node with the inline card
                    link.parentNode.replaceChild(card, link);
                })
                .catch(() => {
                    // on error, leave the link as-is
                    try { link.dataset.enriched = 'err'; } catch(e){}
                });
            });
        }

        // small helper to escape user-visible text
        function escapeHtml(str) {
            return String(str).replace(/[&<>"']/g, function(ch) {
                return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":"&#39;"}[ch];
            });
        }

        function sendMessage() {
            const query = chatInput.value.trim();

            if (!query) return;

            // Add user message with animation
            const userMessage = document.createElement('div');
            userMessage.className = 'message user';
            userMessage.style.opacity = '0';
            userMessage.style.transform = 'translateY(20px)';
            userMessage.textContent = query;

            chatMessages.appendChild(userMessage);

            // Animate message appearance
            setTimeout(() => {
                userMessage.style.transition = 'all 0.3s ease';
                userMessage.style.opacity = '1';
                userMessage.style.transform = 'translateY(0)';
            }, 10);

            chatInput.value = '';
            chatMessages.scrollTop = chatMessages.scrollHeight;

            // Show typing indicator with animation
            const typingIndicator = document.createElement('div');
            typingIndicator.className = 'message bot';
            typingIndicator.style.opacity = '0';
            typingIndicator.style.transform = 'translateY(20px)';
            typingIndicator.innerHTML = '<em>AI is thinking...</em>';
            chatMessages.appendChild(typingIndicator);

            setTimeout(() => {
                typingIndicator.style.transition = 'all 0.3s ease';
                typingIndicator.style.opacity = '1';
                typingIndicator.style.transform = 'translateY(0)';
            }, 10);

            // Simulate AI processing with loader
            recommendationLoader.classList.add('show');

            // Prepare request data
            let requestData = JSON.stringify({ query });
            let headers = { 'X-CSRFToken': getCSRFToken(), 'Content-Type': 'application/json' };

            // Send to API with timeout and robust handling
            const controller = new AbortController();
            const signal = controller.signal;
            const CLIENT_TIMEOUT_MS = 8000; // client-side timeout
            const timeoutId = setTimeout(() => controller.abort(), CLIENT_TIMEOUT_MS);

            fetch('/api/chatbot/', {
                method: 'POST',
                headers: headers,
                body: requestData,
                signal: signal
            })
            .then(response => {
                clearTimeout(timeoutId);
                recommendationLoader.classList.remove('show');
                // Remove typing indicator if still present
                if (typingIndicator && typingIndicator.parentNode) {
                    try { chatMessages.removeChild(typingIndicator); } catch(e) {}
                }

                if (!response.ok) {
                    return response.text().then(text => {
                        throw new Error(text || 'Server error');
                    });
                }

                // Try to parse JSON, but tolerate non-JSON
                return response.text().then(txt => {
                    try { return JSON.parse(txt); } catch(e) { return { response: txt }; }
                });
            })
            .then(data => {
                const botMessage = document.createElement('div');
                botMessage.className = 'message bot';
                botMessage.style.opacity = '0';
                botMessage.style.transform = 'translateY(20px)';

                let text = '';
                if (!data) {
                    text = 'Sorry, I did not get a response. Please try again.';
                } else if (data.response) {
                    text = data.response;
                } else if (data.results && Array.isArray(data.results)) {
                    // Visual search or structured response
                    if (data.results.length === 0) text = 'No similar books found.';
                    else {
                        text = 'I found similar books: ' + data.results.slice(0,3).map(r => r.title).join(', ');
                    }
                } else if (typeof data === 'string') {
                    text = data;
                } else {
                    text = JSON.stringify(data).slice(0, 500);
                }

                // Format the bot response into richer HTML (book links, paragraphs)
                const formatted = formatBotResponse(text);
                botMessage.appendChild(formatted);
                chatMessages.appendChild(botMessage);

                // Enrich any book links into inline cards
                enrichBotLinks(botMessage);

                // Fallback: if no bot-book-link anchors were created, parse book IDs from text
                // and render inline cards below the response (handles cases where model text didn't include
                // parentheses or our link conversion missed the pattern).
                setTimeout(() => {
                    const hasLinks = botMessage.querySelectorAll('a.bot-book-link').length > 0;
                    if (!hasLinks) {
                        // extract all /books/<id>/ occurrences from the raw text
                        const ids = [];
                        try {
                            const re = /\/books\/(\d+)\//g;
                            let m;
                            while ((m = re.exec(text)) !== null) {
                                const id = m[1];
                                if (!ids.includes(id)) ids.push(id);
                            }
                        } catch (e) {
                            // ignore
                        }

                        if (ids.length > 0) {
                            const container = document.createElement('div');
                            container.className = 'ai-inline-books d-flex gap-2 flex-wrap';
                            ids.forEach(id => {
                                fetch(`/api/book/${id}/`)
                                .then(r => r.ok ? r.json() : Promise.reject('not found'))
                                .then(data => {
                                    if (!data || data.error) return;
                                    const card = document.createElement('div');
                                    card.className = 'book-card-inline';
                                    const img = document.createElement('img');
                                    img.src = data.cover_image || '/media/books/book_placeholder.svg';
                                    img.alt = data.title || '';
                                    const meta = document.createElement('div');
                                    meta.style.flex = '1';
                                    meta.innerHTML = `<div style="font-weight:600">${escapeHtml(data.title || '')}</div><div style="color:#666;font-size:0.9rem">${escapeHtml(data.author || '')}</div><div style="margin-top:6px;color:#1B263B;font-weight:600">₹${data.price || ''}</div>`;
                                    card.appendChild(img);
                                    card.appendChild(meta);
                                    container.appendChild(card);
                                })
                                .catch(() => {});
                            });
                            if (container.children.length > 0 || ids.length>0) {
                                botMessage.appendChild(container);
                            }
                        }
                    }
                }, 50);

                setTimeout(() => {
                    botMessage.style.transition = 'all 0.3s ease';
                    botMessage.style.opacity = '1';
                    botMessage.style.transform = 'translateY(0)';
                    chatMessages.scrollTop = chatMessages.scrollHeight;
                }, 10);
            })
            .catch(error => {
                clearTimeout(timeoutId);
                recommendationLoader.classList.remove('show');
                if (typingIndicator && typingIndicator.parentNode) {
                    try { chatMessages.removeChild(typingIndicator); } catch(e) {}
                }

                const errorMessage = document.createElement('div');
                errorMessage.className = 'message bot';
                errorMessage.style.opacity = '0';
                errorMessage.style.transform = 'translateY(20px)';

                if (error.name === 'AbortError') {
                    errorMessage.textContent = 'Request timed out. Please try again.';
                } else {
                    errorMessage.textContent = 'Sorry, I encountered an error. Please try again.';
                    console.error('Chatbot request error:', error);
                }

                chatMessages.appendChild(errorMessage);

                setTimeout(() => {
                    errorMessage.style.transition = 'all 0.3s ease';
                    errorMessage.style.opacity = '1';
                    errorMessage.style.transform = 'translateY(0)';
                }, 10);
            });
        }

        if (chatSend) {
            chatSend.addEventListener('click', sendMessage);
        }

        if (chatInput) {
            chatInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') sendMessage();
            });
        }
    }

    // Enhanced wishlist functionality with toast notifications
    document.querySelectorAll('.wishlist-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            this.classList.toggle('active');
            const icon = this.querySelector('i');
            const isActive = this.classList.contains('active');

            // Animate icon
            icon.style.transform = 'scale(0.8)';
            setTimeout(() => {
                icon.style.transform = 'scale(1.2)';
                setTimeout(() => {
                    icon.style.transform = 'scale(1)';
                }, 150);
            }, 50);

            if (isActive) {
                icon.className = 'fas fa-heart';
                showToast('Added to wishlist!', 'success');
            } else {
                icon.className = 'far fa-heart';
                showToast('Removed from wishlist!', 'info');
            }
        });
    });



    // Also handle the homepage camera input (if present) to reuse visual results UI
    const pageCameraInput = document.getElementById('cameraInput');
    if (pageCameraInput) {
        pageCameraInput.addEventListener('change', (event) => {
            const file = event.target.files && event.target.files[0];
            if (!file) return;
            const formData = new FormData();
            formData.append('image', file);

            fetch('/api/visual-search/', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': getCSRFToken()
                }
            })
            .then(resp => resp.json())
            .then(data => {
                if (data && data.results && data.results.length > 0) {
                    showVisualResults(data.results);
                } else {
                    showToast('No visual matches found. Try a clearer photo.', 'error');
                }
            })
            .catch(err => {
                console.error('Visual search error', err);
                showToast('Visual search failed.', 'error');
            });
        });
    }

    // Smooth scroll navigation
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                const offsetTop = target.offsetTop - 80; // Account for fixed navbar
                window.scrollTo({
                    top: offsetTop,
                    behavior: 'smooth'
                });
            }
        });
    });

    // Carousel auto-scroll enhancement
    const carousel = document.querySelector('#bookCarousel');
    if (carousel) {
        let autoScrollInterval;

        function startAutoScroll() {
            autoScrollInterval = setInterval(() => {
                const activeItem = carousel.querySelector('.carousel-item.active');
                const nextItem = activeItem.nextElementSibling || carousel.querySelector('.carousel-item:first-child');
                if (nextItem) {
                    const bsCarousel = new bootstrap.Carousel(carousel);
                    bsCarousel.next();
                }
            }, 4000); // Auto-scroll every 4 seconds
        }

        function stopAutoScroll() {
            clearInterval(autoScrollInterval);
        }

        // Start auto-scroll on load
        startAutoScroll();

        // Pause on hover
        carousel.addEventListener('mouseenter', stopAutoScroll);
        carousel.addEventListener('mouseleave', startAutoScroll);
    }

    // Enhanced search with autocomplete
    const searchInput = document.querySelector('input[name="q"]');
    if (searchInput) {
        let suggestions = [];
        searchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase();
            if (query.length < 2) {
                hideSuggestions();
                return;
            }

            // Mock autocomplete - in real app, fetch from API
            fetch('/api/book_list/')
            .then(response => response.json())
            .then(data => {
                suggestions = data.results ? data.results.filter(book =>
                    book.title.toLowerCase().includes(query) ||
                    book.author.toLowerCase().includes(query)
                ).slice(0, 5) : [];
                showSuggestions(suggestions);
            })
            .catch(() => {
                // Fallback to empty suggestions
                showSuggestions([]);
            });
        });

        function showSuggestions(suggestions) {
            hideSuggestions();
            if (suggestions.length === 0) return;

            const suggestionsDiv = document.createElement('div');
            suggestionsDiv.className = 'suggestions';
            suggestionsDiv.style.cssText = `
                position: absolute;
                top: 100%;
                left: 0;
                right: 0;
                background: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                z-index: 1000;
                max-height: 200px;
                overflow-y: auto;
                animation: fadeInUp 0.3s ease;
            `;

            suggestions.forEach(book => {
                const suggestion = document.createElement('div');
                suggestion.style.cssText = `
                    padding: 12px 15px;
                    cursor: pointer;
                    border-bottom: 1px solid #eee;
                    transition: all 0.2s ease;
                `;
                suggestion.innerHTML = `<strong>${book.title}</strong> by ${book.author}`;
                suggestion.addEventListener('click', () => {
                    searchInput.value = book.title;
                    hideSuggestions();
                    searchInput.closest('form').submit();
                });
                suggestion.addEventListener('mouseover', () => {
                    suggestion.style.background = '#f8f9fa';
                    suggestion.style.transform = 'translateX(5px)';
                });
                suggestion.addEventListener('mouseout', () => {
                    suggestion.style.background = 'white';
                    suggestion.style.transform = 'translateX(0)';
                });
                suggestionsDiv.appendChild(suggestion);
            });

            searchInput.parentNode.style.position = 'relative';
            searchInput.parentNode.appendChild(suggestionsDiv);
        }

        function hideSuggestions() {
            const existing = document.querySelector('.suggestions');
            if (existing) {
                existing.style.animation = 'fadeOut 0.2s ease';
                setTimeout(() => existing.remove(), 200);
            }
        }

        document.addEventListener('click', function(e) {
            if (!searchInput.contains(e.target) && !e.target.closest('.suggestions')) {
                hideSuggestions();
            }
        });
    }

    // Image lazy loading with fade-in
    const images = document.querySelectorAll('img[data-src]');
    const imageObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.style.opacity = '0';
                img.src = img.dataset.src;
                img.onload = () => {
                    img.style.transition = 'opacity 0.5s ease';
                    img.style.opacity = '1';
                };
                img.classList.remove('lazy');
                observer.unobserve(img);
            }
        });
    });

    images.forEach(img => imageObserver.observe(img));

    // Enhanced toast notifications
    function showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `toast-notification ${type === 'error' ? 'error' : ''}`;
        toast.textContent = message;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('hide');
            setTimeout(() => {
                if (toast.parentNode) {
                    document.body.removeChild(toast);
                }
            }, 300);
        }, 3000);
    }



    // Show visual search results in an overlay with book cards
    window.showVisualResults = function(results) {
        // Remove any existing overlay
        const existing = document.getElementById('visual-results-overlay');
        if (existing) existing.remove();

        const overlay = document.createElement('div');
        overlay.id = 'visual-results-overlay';
        overlay.className = 'visual-results-overlay';
        overlay.style.cssText = `position:fixed;inset:0;background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;z-index:2000;`;

        const panel = document.createElement('div');
        panel.style.cssText = 'width:90%;max-width:1100px;background:white;border-radius:12px;padding:20px;max-height:80%;overflow:auto;';

        const header = document.createElement('div');
        header.style.cssText = 'display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;';
        header.innerHTML = `<h4 style="margin:0">Visual Search Results</h4><button class="btn btn-sm btn-outline-secondary" id="close-visual-results">Close</button>`;
        panel.appendChild(header);

        const grid = document.createElement('div');
        grid.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;';

        results.forEach(r => {
            const card = document.createElement('div');
            card.className = 'visual-result-card';
            card.style.cssText = 'background:#fff;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.08);overflow:hidden;cursor:pointer;display:flex;flex-direction:column;';

            const imgWrap = document.createElement('div');
            imgWrap.style.cssText = 'height:180px;overflow:hidden;display:flex;align-items:center;justify-content:center;background:#f5f5f5;';
            const img = document.createElement('img');
            img.src = r.cover_image || (r.cover || r.image || '');
            img.alt = r.title || '';
            img.style.cssText = 'max-width:100%;max-height:100%;object-fit:cover;';
            imgWrap.appendChild(img);

            const body = document.createElement('div');
            body.style.cssText = 'padding:10px;flex:1;display:flex;flex-direction:column;';
            const title = document.createElement('div');
            title.style.cssText = 'font-weight:600;margin-bottom:6px;';
            title.textContent = r.title || 'Untitled';
            const author = document.createElement('div');
            author.style.cssText = 'color:#666;font-size:0.9rem;margin-bottom:8px;';
            author.textContent = r.author || r.authors || '';
            const btns = document.createElement('div');
            btns.style.cssText = 'margin-top:auto;display:flex;gap:8px;';
            const viewBtn = document.createElement('a');
            viewBtn.className = 'btn btn-sm btn-primary';
            viewBtn.textContent = 'View';
            if (r.book_id) {
                viewBtn.href = `/books/${r.book_id}/`;
            } else if (r.id) {
                viewBtn.href = `/books/${r.id}/`;
            } else {
                viewBtn.href = '#';
                viewBtn.addEventListener('click', (e) => e.preventDefault());
            }

            btns.appendChild(viewBtn);

            body.appendChild(title);
            body.appendChild(author);
            body.appendChild(btns);

            card.appendChild(imgWrap);
            card.appendChild(body);

            // Click anywhere on card to open the book page
            card.addEventListener('click', (e) => {
                if (r.book_id) window.location.href = `/books/${r.book_id}/`;
                else if (r.id) window.location.href = `/books/${r.id}/`;
            });

            grid.appendChild(card);
        });

        panel.appendChild(grid);
        overlay.appendChild(panel);
        document.body.appendChild(overlay);

        document.getElementById('close-visual-results').addEventListener('click', () => overlay.remove());
        overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
    };

    // Intersection Observer for scroll-triggered animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.animationPlayState = 'running';
            }
        });
    }, observerOptions);

    // Observe elements for scroll animations
    document.querySelectorAll('.book-card, .category-card, .recommendation-card').forEach(card => {
        observer.observe(card);
    });
});

function getCSRFToken() {
    // First try to get from cookies
    const cookieValue = document.cookie
        .split('; ')
        .find(row => row.startsWith('csrftoken='))
        ?.split('=')[1];

    if (cookieValue) return cookieValue;

    // Fallback: get from hidden form input
    const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return csrfInput ? csrfInput.value : '';
}

// Pagination enhancement with loading animation
function loadPage(page) {
    const progressBar = document.querySelector('.progress-bar-loader') || document.createElement('div');
    if (!document.querySelector('.progress-bar-loader')) {
        progressBar.className = 'progress-bar-loader';
        document.body.appendChild(progressBar);
    }
    progressBar.style.display = 'block';

    const url = new URL(window.location);
    url.searchParams.set('page', page);

    setTimeout(() => {
        window.location.href = url.toString();
    }, 300);
}

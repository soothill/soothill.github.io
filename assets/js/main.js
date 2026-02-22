/**
 * Main JavaScript - Soot & Silicon
 * Modern, dynamic functionality for the website
 */

(function() {
    'use strict';

    // ==========================================================================
    // Utility Functions
    // ==========================================================================

    /**
     * Debounce function to limit rate of function execution
     */
    function debounce(func, wait = 100) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    /**
     * Throttle function to ensure function executes at most once per interval
     */
    function throttle(func, limit = 100) {
        let inThrottle;
        return function executedFunction(...args) {
            if (!inThrottle) {
                func(...args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }

    // ==========================================================================
    // Email Obfuscation
    // ==========================================================================

    function initEmailObfuscation() {
        const user = 'darren';
        const domain = 'soothill.com';
        
        // Find all email links
        const emailLinks = document.querySelectorAll('[data-email]');
        emailLinks.forEach(link => {
            link.href = `mailto:${user}@${domain}`;
            if (link.textContent === 'Loading...') {
                link.textContent = `${user}@${domain}`;
            }
        });

        // Handle author contact links
        const authorLinks = document.querySelectorAll('#author-contact, .author-email');
        authorLinks.forEach(link => {
            if (link) {
                link.href = `mailto:${user}@${domain}`;
                link.addEventListener('mouseenter', function() {
                    this.style.color = 'var(--primary-light)';
                    this.style.borderBottom = '1px solid var(--primary-light)';
                });
                link.addEventListener('mouseleave', function() {
                    this.style.color = 'var(--text-primary)';
                    this.style.borderBottom = '1px dotted var(--text-secondary)';
                });
            }
        });
    }

    // ==========================================================================
    // Scroll Reveal Animations
    // ==========================================================================

    function initScrollReveal() {
        const revealElements = document.querySelectorAll('.reveal, .post-preview, .card, .section');
        
        if (!revealElements.length) return;

        const observerOptions = {
            root: null,
            rootMargin: '0px 0px -50px 0px',
            threshold: 0.1
        };

        const revealObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('active');
                    // Optionally unobserve after revealing
                    // revealObserver.unobserve(entry.target);
                }
            });
        }, observerOptions);

        revealElements.forEach((el, index) => {
            // Add stagger class for delayed animations
            const staggerClass = `stagger-${(index % 5) + 1}`;
            if (!el.classList.contains('reveal')) {
                el.classList.add('reveal');
            }
            if (!el.classList.contains('stagger-1') && !el.classList.contains('stagger-2') && 
                !el.classList.contains('stagger-3') && !el.classList.contains('stagger-4') && 
                !el.classList.contains('stagger-5')) {
                el.classList.add(staggerClass);
            }
            revealObserver.observe(el);
        });
    }

    // ==========================================================================
    // Back to Top Button
    // ==========================================================================

    function initBackToTop() {
        // Create button if it doesn't exist
        let backToTop = document.querySelector('.back-to-top');
        
        if (!backToTop) {
            backToTop = document.createElement('button');
            backToTop.className = 'back-to-top';
            backToTop.setAttribute('aria-label', 'Back to top');
            backToTop.innerHTML = `
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="18 15 12 9 6 15"></polyline>
                </svg>
            `;
            document.body.appendChild(backToTop);
        }

        // Show/hide button based on scroll position
        const toggleBackToTop = throttle(() => {
            if (window.scrollY > 300) {
                backToTop.classList.add('visible');
            } else {
                backToTop.classList.remove('visible');
            }
        }, 100);

        window.addEventListener('scroll', toggleBackToTop, { passive: true });

        // Scroll to top on click
        backToTop.addEventListener('click', () => {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }

    // ==========================================================================
    // Reading Progress Bar
    // ==========================================================================

    function initReadingProgress() {
        const postContent = document.querySelector('.post-content, article');
        if (!postContent) return;

        // Create progress bar
        let progressBar = document.querySelector('.reading-progress');
        
        if (!progressBar) {
            progressBar = document.createElement('div');
            progressBar.className = 'reading-progress';
            document.body.appendChild(progressBar);
        }

        const updateProgress = throttle(() => {
            const contentTop = postContent.offsetTop;
            const contentHeight = postContent.offsetHeight;
            const windowHeight = window.innerHeight;
            const scrollTop = window.scrollY;

            // Calculate reading progress
            const progress = Math.min(
                Math.max((scrollTop - contentTop + windowHeight) / contentHeight, 0) * 100,
                100
            );

            progressBar.style.width = `${progress}%`;
        }, 50);

        window.addEventListener('scroll', updateProgress, { passive: true });
        updateProgress(); // Initial call
    }

    // ==========================================================================
    // Mobile Navigation
    // ==========================================================================

    function initMobileNav() {
        const header = document.querySelector('.site-header');
        if (!header) return;

        const nav = header.querySelector('.site-nav');
        if (!nav) return;

        // Create hamburger button
        let navToggle = header.querySelector('.nav-toggle');
        
        if (!navToggle) {
            navToggle = document.createElement('button');
            navToggle.className = 'nav-toggle';
            navToggle.setAttribute('aria-label', 'Toggle navigation');
            navToggle.setAttribute('aria-expanded', 'false');
            navToggle.innerHTML = '<span></span><span></span><span></span>';
            
            // Insert before nav
            header.querySelector('.container').appendChild(navToggle);
        }

        // Toggle navigation
        navToggle.addEventListener('click', () => {
            const isExpanded = navToggle.getAttribute('aria-expanded') === 'true';
            navToggle.setAttribute('aria-expanded', !isExpanded);
            navToggle.classList.toggle('active');
            nav.classList.toggle('active');
        });

        // Close nav on link click (mobile)
        nav.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                navToggle.classList.remove('active');
                nav.classList.remove('active');
                navToggle.setAttribute('aria-expanded', 'false');
            });
        });

        // Close nav on outside click
        document.addEventListener('click', (e) => {
            if (!header.contains(e.target) && nav.classList.contains('active')) {
                navToggle.classList.remove('active');
                nav.classList.remove('active');
                navToggle.setAttribute('aria-expanded', 'false');
            }
        });
    }

    // ==========================================================================
    // Copy to Clipboard for Code Blocks
    // ==========================================================================

    function initCodeCopy() {
        const codeBlocks = document.querySelectorAll('pre');
        
        codeBlocks.forEach(pre => {
            // Create copy button
            const copyButton = document.createElement('button');
            copyButton.className = 'copy-button';
            copyButton.textContent = 'Copy';
            copyButton.setAttribute('aria-label', 'Copy code to clipboard');
            
            pre.style.position = 'relative';
            pre.appendChild(copyButton);

            copyButton.addEventListener('click', async () => {
                const code = pre.querySelector('code')?.textContent || pre.textContent;
                
                try {
                    await navigator.clipboard.writeText(code);
                    copyButton.textContent = 'Copied!';
                    copyButton.classList.add('copied');
                    
                    setTimeout(() => {
                        copyButton.textContent = 'Copy';
                        copyButton.classList.remove('copied');
                    }, 2000);
                } catch (err) {
                    console.error('Failed to copy:', err);
                    copyButton.textContent = 'Failed';
                    setTimeout(() => {
                        copyButton.textContent = 'Copy';
                    }, 2000);
                }
            });
        });
    }

    // ==========================================================================
    // Reading Time Calculator
    // ==========================================================================

    function initReadingTime() {
        const postContent = document.querySelector('.post-content, article');
        const readingTimeEl = document.querySelector('.reading-time');
        
        if (!postContent || !readingTimeEl) return;

        const text = postContent.textContent || postContent.innerText;
        const wordsPerMinute = 200;
        const words = text.trim().split(/\s+/).length;
        const minutes = Math.ceil(words / wordsPerMinute);

        readingTimeEl.textContent = `${minutes} min read`;
    }

    // ==========================================================================
    // Smooth Scroll for Anchor Links
    // ==========================================================================

    function initSmoothScroll() {
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function(e) {
                const targetId = this.getAttribute('href');
                if (targetId === '#') return;

                const targetElement = document.querySelector(targetId);
                if (targetElement) {
                    e.preventDefault();
                    const headerHeight = document.querySelector('.site-header')?.offsetHeight || 0;
                    const targetPosition = targetElement.offsetTop - headerHeight - 20;
                    
                    window.scrollTo({
                        top: targetPosition,
                        behavior: 'smooth'
                    });

                    // Update URL without jumping
                    history.pushState(null, null, targetId);
                }
            });
        });
    }

    // ==========================================================================
    // Table of Contents Generator
    // ==========================================================================

    function initTableOfContents() {
        const postContent = document.querySelector('.post-content, article');
        const tocContainer = document.querySelector('.toc');
        
        if (!postContent || !tocContainer) return;

        const headings = postContent.querySelectorAll('h2, h3');
        if (headings.length < 2) {
            tocContainer.style.display = 'none';
            return;
        }

        const tocList = tocContainer.querySelector('.toc__list') || document.createElement('ul');
        tocList.className = 'toc__list';
        tocList.innerHTML = '';

        headings.forEach((heading, index) => {
            // Add ID to heading if it doesn't have one
            if (!heading.id) {
                heading.id = `section-${index}`;
            }

            const li = document.createElement('li');
            if (heading.tagName === 'H3') {
                li.style.marginLeft = '1rem';
            }

            const link = document.createElement('a');
            link.href = `#${heading.id}`;
            link.textContent = heading.textContent;

            li.appendChild(link);
            tocList.appendChild(li);
        });

        if (!tocContainer.contains(tocList)) {
            tocContainer.appendChild(tocList);
        }
    }

    // ==========================================================================
    // Last Updated Date
    // ==========================================================================

    function initLastUpdated() {
        const lastUpdatedEl = document.getElementById('last-updated') || document.getElementById('lastUpdated');
        
        if (lastUpdatedEl) {
            const lastModified = new Date(document.lastModified);
            const options = {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                timeZoneName: 'short'
            };
            lastUpdatedEl.textContent = lastModified.toLocaleString('en-US', options);
        }
    }

    // ==========================================================================
    // Ripple Effect for Buttons
    // ==========================================================================

    function initRippleEffect() {
        document.querySelectorAll('.btn, .card, .post-navigation__link').forEach(element => {
            element.addEventListener('click', function(e) {
                const ripple = document.createElement('span');
                const rect = this.getBoundingClientRect();
                
                ripple.style.cssText = `
                    position: absolute;
                    border-radius: 50%;
                    background: rgba(255, 255, 255, 0.3);
                    pointer-events: none;
                    width: 100px;
                    height: 100px;
                    transform: translate(-50%, -50%) scale(0);
                    animation: ripple 0.6s ease-out;
                `;
                
                ripple.style.left = `${e.clientX - rect.left}px`;
                ripple.style.top = `${e.clientY - rect.top}px`;
                
                this.style.position = 'relative';
                this.style.overflow = 'hidden';
                this.appendChild(ripple);
                
                setTimeout(() => ripple.remove(), 600);
            });
        });

        // Add ripple animation keyframes
        if (!document.querySelector('#ripple-styles')) {
            const style = document.createElement('style');
            style.id = 'ripple-styles';
            style.textContent = `
                @keyframes ripple {
                    to {
                        transform: translate(-50%, -50%) scale(4);
                        opacity: 0;
                    }
                }
            `;
            document.head.appendChild(style);
        }
    }

    // ==========================================================================
    // Lazy Loading Images
    // ==========================================================================

    function initLazyLoading() {
        const images = document.querySelectorAll('img[data-src]');
        
        if (!images.length) return;

        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        img.src = img.dataset.src;
                        img.removeAttribute('data-src');
                        imageObserver.unobserve(img);
                    }
                });
            });

            images.forEach(img => imageObserver.observe(img));
        } else {
            // Fallback for older browsers
            images.forEach(img => {
                img.src = img.dataset.src;
                img.removeAttribute('data-src');
            });
        }
    }

    // ==========================================================================
    // Dark/Light Mode Toggle
    // ==========================================================================

    function initThemeToggle() {
        // Check for saved theme preference or system preference
        const savedTheme = localStorage.getItem('theme');
        const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        
        if (savedTheme === 'light' || (!savedTheme && !systemPrefersDark)) {
            document.documentElement.setAttribute('data-theme', 'light');
        } else {
            document.documentElement.setAttribute('data-theme', 'dark');
        }

        // Create toggle button if it doesn't exist
        let themeToggle = document.querySelector('.theme-toggle');
        
        if (!themeToggle) {
            themeToggle = document.createElement('button');
            themeToggle.className = 'theme-toggle';
            themeToggle.setAttribute('aria-label', 'Toggle dark/light mode');
            themeToggle.innerHTML = `
                <svg class="theme-toggle__icon theme-toggle__icon--dark" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
                </svg>
                <svg class="theme-toggle__icon theme-toggle__icon--light" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="5"></circle>
                    <line x1="12" y1="1" x2="12" y2="3"></line>
                    <line x1="12" y1="21" x2="12" y2="23"></line>
                    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
                    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
                    <line x1="1" y1="12" x2="3" y2="12"></line>
                    <line x1="21" y1="12" x2="23" y2="12"></line>
                    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
                    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
                </svg>
            `;
            
            // Add to header
            const header = document.querySelector('.site-header .container');
            if (header) {
                header.appendChild(themeToggle);
            }
        }

        // Toggle theme on click
        themeToggle.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
        });

        // Listen for system theme changes
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
            if (!localStorage.getItem('theme')) {
                document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light');
            }
        });

        // Add theme toggle styles
        const themeStyles = document.createElement('style');
        themeStyles.textContent = `
            .theme-toggle {
                background: transparent;
                border: 2px solid var(--border);
                border-radius: 50%;
                width: 40px;
                height: 40px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: all var(--transition-base);
                color: var(--text-primary);
            }
            
            .theme-toggle:hover {
                background: var(--border);
                border-color: var(--primary-light);
            }
            
            .theme-toggle__icon--light {
                display: none;
            }
            
            [data-theme="light"] .theme-toggle__icon--dark {
                display: none;
            }
            
            [data-theme="light"] .theme-toggle__icon--light {
                display: block;
            }
            
            /* Light theme variables */
            [data-theme="light"] {
                --bg-dark: #f8fafc;
                --bg-darker: #f1f5f9;
                --bg-card: #ffffff;
                --text-primary: #0f172a;
                --text-secondary: #334155;
                --text-muted: #64748b;
                --border: #e2e8f0;
                --border-light: #cbd5e1;
                --shadow-sm: 0 2px 4px rgba(0,0,0,0.1);
                --shadow-md: 0 4px 12px rgba(0,0,0,0.1);
                --shadow-lg: 0 10px 40px rgba(0,0,0,0.1);
            }
            
            [data-theme="light"] body {
                background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
            }
            
            [data-theme="light"] pre {
                background: #f1f5f9;
                color: #1e293b;
            }
            
            [data-theme="light"] .site-header {
                background: linear-gradient(135deg, #ffffff 0%, #f1f5f9 100%);
            }
        `;
        document.head.appendChild(themeStyles);
    }

    // ==========================================================================
    // Client-Side Search
    // ==========================================================================

    function initSearch() {
        const searchContainer = document.querySelector('.search-container');
        if (!searchContainer) return;

        const searchInput = searchContainer.querySelector('.search-input');
        const searchResults = searchContainer.querySelector('.search-results');
        
        if (!searchInput || !searchResults) return;

        // Search data will be populated from Jekyll
        let searchData = [];
        
        // Try to get search data from window
        if (window.searchIndex) {
            searchData = window.searchIndex;
        }

        let debounceTimer;

        searchInput.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                const query = e.target.value.toLowerCase().trim();
                
                if (query.length < 2) {
                    searchResults.classList.remove('active');
                    searchResults.innerHTML = '';
                    return;
                }

                const results = searchData.filter(item => {
                    return item.title.toLowerCase().includes(query) ||
                           item.content.toLowerCase().includes(query) ||
                           (item.tags && item.tags.some(tag => tag.toLowerCase().includes(query)));
                }).slice(0, 5);

                if (results.length === 0) {
                    searchResults.innerHTML = '<div class="search-results__item"><span class="search-results__title">No results found</span></div>';
                } else {
                    searchResults.innerHTML = results.map(item => `
                        <a href="${item.url}" class="search-results__item">
                            <div class="search-results__title">${item.title}</div>
                            <div class="search-results__excerpt">${item.excerpt || ''}</div>
                        </a>
                    `).join('');
                }

                searchResults.classList.add('active');
            }, 300);
        });

        // Close search results when clicking outside
        document.addEventListener('click', (e) => {
            if (!searchContainer.contains(e.target)) {
                searchResults.classList.remove('active');
            }
        });

        // Show results on focus if there's a query
        searchInput.addEventListener('focus', () => {
            if (searchInput.value.length >= 2) {
                searchResults.classList.add('active');
            }
        });
    }

    // ==========================================================================
    // Page Transitions
    // ==========================================================================

    function initPageTransitions() {
        // Add page transition class to main content
        const mainContent = document.querySelector('main');
        if (mainContent) {
            mainContent.classList.add('page-transition');
        }

        // Add fade effect when leaving pages
        document.querySelectorAll('a[href]:not([href^="#"]):not([href^="mailto:"]):not([href^="tel:"]):not([target="_blank"])').forEach(link => {
            link.addEventListener('click', function(e) {
                const href = this.getAttribute('href');
                
                // Skip external links and anchor links
                if (href.startsWith('http') || href.startsWith('//')) return;
                
                // Check if it's a same-site navigation
                const isSameSite = href.startsWith('/') || 
                                   href.startsWith('./') || 
                                   (!href.includes('://') && !href.startsWith('#'));
                
                if (isSameSite) {
                    e.preventDefault();
                    document.body.classList.add('page-leaving');
                    
                    setTimeout(() => {
                        window.location.href = href;
                    }, 300);
                }
            });
        });

        // Add transition styles
        const transitionStyles = document.createElement('style');
        transitionStyles.textContent = `
            .page-leaving {
                opacity: 0;
                transition: opacity 0.3s ease;
            }
            
            main.page-transition {
                animation: pageEnter 0.5s ease forwards;
            }
        `;
        document.head.appendChild(transitionStyles);
    }

    // ==========================================================================
    // Particle Background Effect
    // ==========================================================================

    function initParticles() {
        const particleContainers = document.querySelectorAll('.particles-container');
        
        particleContainers.forEach(container => {
            // Create particles
            for (let i = 0; i < 20; i++) {
                const particle = document.createElement('div');
                particle.className = 'particle';
                particle.style.left = `${Math.random() * 100}%`;
                particle.style.animationDelay = `${Math.random() * 20}s`;
                particle.style.animationDuration = `${15 + Math.random() * 15}s`;
                particle.style.width = `${2 + Math.random() * 4}px`;
                particle.style.height = particle.style.width;
                container.appendChild(particle);
            }
        });
    }

    // ==========================================================================
    // Parallax Scrolling Effect
    // ==========================================================================

    function initParallax() {
        const parallaxElements = document.querySelectorAll('[data-parallax]');
        
        if (!parallaxElements.length) return;

        const updateParallax = throttle(() => {
            const scrollY = window.scrollY;
            
            parallaxElements.forEach(element => {
                const speed = element.dataset.parallax || 0.5;
                const offset = scrollY * speed;
                element.style.transform = `translateY(${offset}px)`;
            });
        }, 16);

        window.addEventListener('scroll', updateParallax, { passive: true });
    }

    // ==========================================================================
    // Geometric Background Shapes
    // ==========================================================================

    function initGeometricBg() {
        const geometricContainers = document.querySelectorAll('.geometric-bg-container');
        
        geometricContainers.forEach(container => {
            // Create geometric shapes
            const shapes = [
                { type: 'circle', size: 200 },
                { type: 'square', size: 150 },
                { type: 'circle', size: 100 },
                { type: 'square', size: 80 }
            ];
            
            shapes.forEach((shape, index) => {
                const element = document.createElement('div');
                element.className = `geometric-shape geometric-shape--${shape.type}`;
                element.style.width = `${shape.size}px`;
                element.style.height = `${shape.size}px`;
                element.style.animationDelay = `${index * 5}s`;
                element.style.animationDuration = `${25 + index * 5}s`;
                
                // Random positioning
                element.style.top = `${Math.random() * 80}%`;
                element.style.left = `${Math.random() * 80}%`;
                
                container.appendChild(element);
            });
        });
    }

    // ==========================================================================
    // Skeleton Loading
    // ==========================================================================

    function initSkeletonLoading() {
        // Function to show skeleton loading
        window.showSkeletons = function(container, count = 3) {
            const skeletonGrid = document.createElement('div');
            skeletonGrid.className = 'skeleton-grid';
            
            for (let i = 0; i < count; i++) {
                const skeleton = document.createElement('div');
                skeleton.className = 'skeleton-card';
                skeleton.innerHTML = `
                    <div class="skeleton-card__image"></div>
                    <div class="skeleton-card__title"></div>
                    <div class="skeleton-card__text"></div>
                    <div class="skeleton-card__text"></div>
                `;
                skeletonGrid.appendChild(skeleton);
            }
            
            container.innerHTML = '';
            container.appendChild(skeletonGrid);
        };

        // Function to hide skeletons and show content
        window.hideSkeletons = function(container, content) {
            container.style.opacity = '0';
            container.style.transition = 'opacity 0.3s ease';
            
            setTimeout(() => {
                container.innerHTML = content;
                container.style.opacity = '1';
            }, 300);
        };
    }

    // ==========================================================================
    // Service Worker Registration
    // ==========================================================================

    function initServiceWorker() {
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('/sw.js')
                    .then((registration) => {
                        console.log('[Service Worker] Registered:', registration.scope);
                        
                        // Check for updates
                        registration.addEventListener('updatefound', () => {
                            const newWorker = registration.installing;
                            newWorker.addEventListener('statechange', () => {
                                if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                                    // New content available, show notification
                                    console.log('[Service Worker] New content available, refresh to update');
                                }
                            });
                        });
                    })
                    .catch((error) => {
                        console.error('[Service Worker] Registration failed:', error);
                    });
            });
        }
    }

    // ==========================================================================
    // Focus Management for Accessibility
    // ==========================================================================

    function initFocusManagement() {
        // Add visible focus styles
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Tab') {
                document.body.classList.add('keyboard-nav');
            }
        });

        document.addEventListener('mousedown', () => {
            document.body.classList.remove('keyboard-nav');
        });

        // Add focus styles
        const focusStyles = document.createElement('style');
        focusStyles.textContent = `
            body.keyboard-nav *:focus {
                outline: 2px solid var(--primary-light) !important;
                outline-offset: 2px;
            }
        `;
        document.head.appendChild(focusStyles);
    }

    // ==========================================================================
    // Initialize All Features
    // ==========================================================================

    function init() {
        initEmailObfuscation();
        initScrollReveal();
        initBackToTop();
        initReadingProgress();
        initMobileNav();
        initCodeCopy();
        initReadingTime();
        initSmoothScroll();
        initTableOfContents();
        initLastUpdated();
        initRippleEffect();
        initLazyLoading();
        initThemeToggle();
        initSearch();
        initFocusManagement();
        initPageTransitions();
        initParticles();
        initParallax();
        initGeometricBg();
        initSkeletonLoading();
        initServiceWorker();

        console.log('🚀 Soot & Silicon - All features initialized');
    }

    // Run on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose for manual use if needed
    window.SootSilicon = {
        init,
        initScrollReveal,
        initBackToTop,
        initCodeCopy
    };

})();
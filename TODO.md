# Website Modernization TODO List

A comprehensive list of improvements to give the website a more modern and dynamic feel.

---

## 🔴 Phase 1 - COMPLETED ✅

### Visual & Design
- [x] Extract CSS into separate file(s) for maintainability
- [x] Add scroll-reveal animations using Intersection Observer
- [x] Fix dark theme consistency in About page
- [x] Load custom fonts properly (Inter, Fira Code via Google Fonts CDN)

### Code Quality
- [x] Remove duplicate CSS across HTML files
- [x] Consolidate email obfuscation script into single location
- [x] Extract inline styles from layouts

### Medium Priority Features
- [x] Back-to-top button
- [x] Table of contents for blog posts
- [x] Copy-to-clipboard for code blocks
- [x] Reading time indicators
- [x] Dark/light mode toggle
- [x] Mobile hamburger menu
- [x] Ripple effects
- [x] Staggered reveal animations
- [x] Related posts section
- [x] Social sharing buttons
- [x] Client-side search
- [x] Breadcrumb navigation
- [x] Skip-to-content link
- [x] Keyboard focus states
- [x] ARIA labels
- [x] Gradient text effects
- [x] Reading progress bar
- [x] Fluid typography

### Lower Priority Features
- [x] Animated gradient backgrounds
- [x] Particle/geometric patterns
- [x] Glassmorphism effects
- [x] Border glow effects
- [x] Parallax scrolling
- [x] Noise/texture overlays
- [x] Page transitions
- [x] Skeleton loading states
- [x] Loading spinners
- [x] Service worker (PWA)
- [x] Offline fallback page
- [x] Lazy loading
- [x] Resource hints
- [x] Font optimization
- [x] Print styles
- [x] GitHub Actions minification

---

## 🟡 Phase 2 - Additional Improvements

### Files Needing Modernization (still have inline CSS)
- [ ] `blog/index.html` - Convert to centralized CSS/JS
- [ ] `categories/index.html` - Convert to centralized CSS/JS
- [ ] `documents/publications.html` - Convert to centralized CSS/JS
- [ ] `changenvmeformat.html` - Convert to centralized CSS/JS (also uses light theme)
- [ ] `spdknvmeof.html` - Convert to centralized CSS/JS

### PWA Enhancements
- [ ] Create `manifest.json` for PWA installation
- [ ] Add app icons (192x192, 512x512)
- [ ] Add theme-color meta tag

### SEO & Performance
- [ ] Add Open Graph images for social sharing
- [ ] Create sitemap.xml (automated)
- [ ] Add structured data for articles (NewsArticle schema)
- [ ] Add robots.txt if not present

### Cleanup
- [ ] Remove `oldindex.html` (unused file)
- [ ] Review and remove any other unused files
- [ ] Consolidate `navigation.html` if not used

### Content Improvements
- [ ] Add RSS/Atom feed
- [ ] Add newsletter signup option
- [ ] Add "Back to Blog" link on posts
- [ ] Add estimated reading time on blog index

---

## 📊 Progress Summary

| Phase | Total | Completed | Remaining |
|-------|-------|-----------|-----------|
| Phase 1 | 38 | 38 | 0 |
| Phase 2 | 17 | 0 | 17 |
| **Total** | **55** | **38** | **17** |

---

## 📝 Files Updated in Phase 1:
- `assets/css/main.css` - Centralized CSS
- `assets/js/main.js` - Centralized JavaScript
- `assets/js/search-index.json` - Jekyll search index
- `sw.js` - Service worker
- `offline.html` - Offline fallback
- `.github/workflows/build.yml` - CI/CD workflow
- `index.html`, `resources.html`, `useful-commands.html`
- `_layouts/default.html`, `_layouts/post.html`
- `about/index.md`

---

*Last updated: 22/02/2026*
# Website Modernization TODO List

A comprehensive list of improvements to give the website a more modern and dynamic feel.

---

## 🔴 High Priority

### Visual & Design
- [x] Extract CSS into separate file(s) for maintainability
- [x] Add scroll-reveal animations using Intersection Observer
- [x] Fix dark theme consistency in About page (currently uses light colors)
- [x] Load custom fonts properly (Inter, Fira Code via Google Fonts CDN)

### Code Quality
- [x] Remove duplicate CSS across `index.html`, `resources.html`, and `default.html`
- [x] Consolidate email obfuscation script into single location
- [x] Extract inline styles from `_layouts/post.html`

---

## 🟡 Medium Priority

### Animations & Micro-interactions
- [x] Add back-to-top floating button with smooth scroll
- [x] Implement table of contents for long blog posts
- [x] Add copy-to-clipboard button for code blocks
- [x] Add reading time indicators for blog posts
- [x] Implement dark/light mode toggle with system preference detection
- [x] Add animated hamburger menu for mobile navigation
- [x] Implement ripple effects on button clicks
- [x] Add staggered reveal animations for cards/grid items

### User Experience
- [x] Add "Related Posts" section at end of blog posts
- [x] Add social sharing buttons on blog posts
- [x] Implement client-side search functionality for posts
- [x] Add breadcrumb navigation
- [x] Add skip-to-content link for accessibility
- [x] Improve focus states for keyboard navigation
- [x] Add proper ARIA labels throughout

### Typography & Content
- [x] Add text gradient effects on headings
- [x] Implement reading progress indicator
- [x] Use `clamp()` for fluid typography

---

## 🟢 Lower Priority

### Visual Enhancements
- [x] Add animated gradient backgrounds with shifting colors
- [x] Implement subtle particle/geometric patterns
- [x] Add glassmorphism effects to cards
- [x] Add border glow effects on card interaction
- [x] Implement parallax scrolling on hero sections
- [x] Add noise/texture overlays for depth

### Technical Architecture
- [x] Implement service worker for offline support (PWA)
- [x] Add lazy loading for images
- [ ] Minify CSS/JS for production
- [x] Add resource hints (preconnect, preload)
- [x] Optimize font loading strategy
- [x] Add print-friendly styles

### Page Transitions
- [x] Add smooth fade/slide transitions between pages
- [x] Add skeleton loading states for content
- [x] Add loading spinners for navigation

---

## 📊 Progress Summary

| Category | Total | Completed | Remaining |
|----------|-------|-----------|-----------|
| High Priority | 7 | 7 | 0 |
| Medium Priority | 17 | 17 | 0 |
| Lower Priority | 14 | 13 | 1 |
| **Total** | **38** | **37** | **1** |

---

## 📝 Implementation Notes

- Work through High Priority items first ✅
- Test each change across different browsers
- Ensure mobile responsiveness is maintained
- Keep accessibility in mind for all changes
- Update this file as progress is made

### Files Created:
- `assets/css/main.css` - Centralized CSS with modern features
- `assets/js/main.js` - JavaScript with all dynamic functionality
- `assets/js/search-index.json` - Jekyll-generated search index
- `sw.js` - Service worker for PWA/offline support
- `offline.html` - Offline fallback page

### Files Updated:
- `index.html` - Main homepage
- `resources.html` - Resources page
- `useful-commands.html` - Linux commands page
- `_layouts/default.html` - Base Jekyll layout
- `_layouts/post.html` - Blog post layout
- `about/index.md` - Fixed dark theme consistency

### Remaining Items:
1. **Minify CSS/JS for production** - Requires build tool (e.g., Gulp, Webpack, or GitHub Actions)

---

*Last updated: 22/02/2026*
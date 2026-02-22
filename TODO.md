# Website Modernization TODO List

---

## 🔴 Phase 1 - COMPLETED ✅

All 38 items completed including:
- Centralized CSS/JS architecture
- Modern animations and effects
- Dark/light mode toggle
- PWA with service worker
- GitHub Actions CI/CD for minification

---

## 🟡 Phase 2 - COMPLETED ✅

### Files Modernized to Centralized CSS/JS
- [x] `blog/index.html`
- [x] `categories/index.html`
- [x] `documents/publications.html`
- [x] `changenvmeformat.html` - Redirect to blog post
- [x] `spdknvmeof.html` - Redirect to blog post

### PWA Enhancements
- [x] Create `manifest.json` for PWA installation
- [x] Add theme-color meta tag
- [ ] Add app icons (72x72 to 512x512) - Requires image files

### SEO & Performance
- [x] Add `robots.txt`
- [x] Add RSS/Atom feed (`feed.xml`)
- [ ] Add Open Graph images for social sharing - Requires image files

### Bug Fixes
- [x] Create missing `documents/contact-info.html`
- [x] Fix email showing "Loading..." on homepage

### Cleanup
- [x] Remove `oldindex.html` (unused file)
- [x] Convert old HTML pages to redirects

---

## 📊 Progress Summary

| Phase | Total | Completed | Remaining |
|-------|-------|-----------|-----------|
| Phase 1 | 38 | 38 | 0 ✅ |
| Phase 2 | 14 | 12 | 2 |
| **Total** | **52** | **50** | **2** |

---

## 📝 Remaining Items (Require Image Assets):

1. **PWA Icons** - Create icons at `/assets/images/`:
   - icon-72.png, icon-96.png, icon-128.png, icon-144.png
   - icon-152.png, icon-192.png, icon-384.png, icon-512.png
   
2. **Open Graph Images** - For social media sharing previews

---

## 🐛 Issues Fixed:
1. ✅ GitHub Actions workflow failing - Fixed terser `--mangle false` syntax error
2. ✅ Contact link broken (`documents/contact-info.html` missing) - Created page
3. ✅ Email showing "Loading..." on homepage - Fixed to show actual email
4. ✅ Old HTML files with inline CSS - Converted to redirects to blog posts
5. ✅ Missing RSS feed - Created feed.xml

---

## 📝 Recent Commits:
- `0447579` - Fix bugs: Create missing contact-info.html and fix email display
- `9337844` - Phase 2: Modernize remaining pages and add PWA support
- `cb1bfdd` - Fix GitHub Actions workflow
- `905a1a4` - Add GitHub Actions workflow for minification
- `3045111` - Main Phase 1 modernization changes

---

*Last updated: 22/02/2026*

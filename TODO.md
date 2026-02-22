# Website Modernization TODO List

A comprehensive list of improvements to give the website a more modern and dynamic feel.

---

## 🔴 Phase 1 - COMPLETED ✅

All 38 items completed including:
- Centralized CSS/JS architecture
- Modern animations and effects
- Dark/light mode toggle
- PWA with service worker
- GitHub Actions CI/CD for minification

---

## 🟡 Phase 2 - In Progress

### Files Modernized to Centralized CSS/JS
- [x] `blog/index.html`
- [x] `categories/index.html`
- [x] `documents/publications.html`
- [ ] `changenvmeformat.html` - Still uses inline CSS and light theme
- [ ] `spdknvmeof.html` - Still uses inline CSS

### PWA Enhancements
- [x] Create `manifest.json` for PWA installation
- [ ] Add app icons (72x72 to 512x512)
- [x] Add theme-color meta tag

### SEO & Performance
- [x] Add `robots.txt`
- [ ] Add Open Graph images for social sharing
- [ ] Add RSS/Atom feed

### Bug Fixes
- [x] Create missing `documents/contact-info.html`
- [x] Fix email showing "Loading..." on homepage

### Cleanup
- [ ] Remove `oldindex.html` (unused file)
- [ ] Review `navigation.html` if used
- [ ] Check for other orphaned files

---

## 📊 Progress Summary

| Phase | Total | Completed | Remaining |
|-------|-------|-----------|-----------|
| Phase 1 | 38 | 38 | 0 ✅ |
| Phase 2 | 12 | 6 | 6 |
| **Total** | **50** | **44** | **6** |

---

## 📝 Recent Commits:
- `9337844` - Phase 2: Modernize remaining pages and add PWA support
- `cb1bfdd` - Fix GitHub Actions workflow (terser option error)
- `905a1a4` - Add GitHub Actions workflow for minification
- `3045111` - Main Phase 1 modernization changes

---

## 🐛 Known Issues Fixed:
1. ✅ GitHub Actions workflow failing - Fixed terser `--mangle false` syntax error
2. ✅ Contact link broken (`documents/contact-info.html` missing) - Created page
3. ✅ Email showing "Loading..." on homepage - Fixed to show actual email

---

## 📋 Remaining Work:

### High Priority
1. Create PWA icons (can be generated from a logo image)
2. Modernize `changenvmeformat.html` and `spdknvmeof.html`

### Medium Priority
3. Add Open Graph images for social sharing
4. Add RSS/Atom feed
5. Remove unused files (`oldindex.html`)

### Low Priority
6. Consider adding newsletter signup
7. Add more structured data schemas

---

*Last updated: 22/02/2026*
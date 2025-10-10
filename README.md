# Soothill Tech Blog

Technical guides and documentation for enterprise storage, NVMe technologies, SPDK, and infrastructure solutions.

## About

This is a Jekyll-powered blog hosted on GitHub Pages, providing comprehensive guides for:

- NVMe over Fabrics (NVMe-oF)
- SPDK (Storage Performance Development Kit)
- RDMA Technologies (RoCE, InfiniBand)
- Linux Storage Stack
- Performance Tuning

## Adding New Blog Posts

To add a new blog post, create a new Markdown file in the `_posts` directory with the following naming convention:

```
YYYY-MM-DD-title-of-post.md
```

### Post Front Matter Template

```yaml
---
layout: post
title: "Your Post Title"
date: YYYY-MM-DD
categories: [Category1, Category2]
tags: [tag1, tag2, tag3]
author: Darren Soothill
description: "A brief description of your post for SEO"
keywords: "comma, separated, keywords"
---

Your content here...
```

## Local Development

### Prerequisites

- Ruby 2.7 or higher
- Bundler

### Setup

```bash
# Install dependencies
bundle install

# Run local server
bundle exec jekyll serve

# View site at http://localhost:4000
```

### Building the Site

```bash
# Build the static site
bundle exec jekyll build

# Output will be in _site/ directory
```

## Directory Structure

```
.
├── _config.yml           # Jekyll configuration
├── _layouts/             # Page layouts
│   ├── default.html      # Default layout with header/footer
│   └── post.html         # Blog post layout
├── _posts/               # Blog posts (Markdown files)
│   └── YYYY-MM-DD-post-title.md
├── blog/                 # Blog index page
│   └── index.html
├── about/                # About page
│   └── index.md
├── index.md              # Homepage
├── Gemfile               # Ruby dependencies
└── README.md             # This file
```

## Features

- ✅ Responsive design
- ✅ SEO optimized with meta tags and structured data
- ✅ Automatic sitemap generation
- ✅ RSS feed support
- ✅ Syntax highlighting for code blocks
- ✅ Previous/Next post navigation
- ✅ Category and tag support
- ✅ Google Analytics integration
- ✅ Cookie consent (Cookiebot)

## GitHub Pages Deployment

This site is configured to work automatically with GitHub Pages. Simply push to the `main` branch and GitHub will build and deploy your site.

### Custom Domain

If using a custom domain, ensure the `CNAME` file contains your domain name.

## License

© 2025 Darren Soothill. All rights reserved.

## Contact

- Email: darren@soothill.io
- Website: https://soothill.io

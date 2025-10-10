# How to Add New Blog Posts

This guide explains how to add new blog posts to your Jekyll-powered GitHub Pages site.

## Quick Start

### 1. Create a New Post File

Create a new file in the `_posts` directory with this naming format:

```
_posts/YYYY-MM-DD-your-post-title.md
```

**Example:**
```
_posts/2025-10-15-setting-up-iscsi-target.md
```

### 2. Add Front Matter

Every post must start with YAML front matter (metadata between `---` markers):

```yaml
---
layout: post
title: "Your Post Title Here"
date: 2025-10-15
categories: [Storage, Linux]
tags: [iscsi, storage, linux, tutorial]
author: Darren Soothill
description: "A brief description of your post for SEO (150-160 characters)"
keywords: "comma, separated, keywords, for, seo"
---

Your content starts here...
```

### 3. Write Your Content

Use Markdown formatting for your content. Here are some common elements:

#### Headings

```markdown
## Main Section
### Subsection
#### Sub-subsection
```

#### Code Blocks

Use triple backticks with language identifier:

````markdown
```bash
sudo apt install package-name
```
````

#### Lists

```markdown
- Unordered item 1
- Unordered item 2

1. Ordered item 1
2. Ordered item 2
```

#### Links

```markdown
[Link text](https://example.com)
```

#### Images

```markdown
![Alt text](/path/to/image.png)
```

#### Bold and Italic

```markdown
**Bold text**
*Italic text*
```

## Complete Example Post

Create `_posts/2025-10-15-example-post.md`:

```yaml
---
layout: post
title: "Example Technical Guide"
date: 2025-10-15
categories: [Tutorial, Linux]
tags: [example, tutorial, guide]
author: Darren Soothill
description: "An example blog post showing the structure and formatting"
keywords: "example, tutorial, blog, jekyll"
---

This is the introduction to your post. It should briefly explain what the post covers.

## Prerequisites

- Requirement 1
- Requirement 2
- Requirement 3

## Installation

Install the required packages:

```bash
sudo apt update
sudo apt install package-name
```

## Configuration

Here's how to configure the service:

```bash
sudo nano /etc/config/file.conf
```

Add the following configuration:

```conf
option1 = value1
option2 = value2
```

## Testing

Verify the installation:

```bash
sudo systemctl status service-name
```

## Troubleshooting

### Common Issue 1

**Problem:** Description of the problem

**Solution:**
```bash
sudo command-to-fix
```

## Conclusion

Summary of what was covered and next steps.

---

© 2025 Darren Soothill. All rights reserved.
```

## Testing Locally

### Install Dependencies (First Time Only)

```bash
# Install Ruby and Bundler if not already installed
# Then install Jekyll dependencies:
bundle install
```

### Run Local Development Server

```bash
bundle exec jekyll serve
```

Open your browser to `http://localhost:4000` to preview your site.

### Build Without Running Server

```bash
bundle exec jekyll build
```

The built site will be in the `_site` directory.

## Publishing to GitHub Pages

### Option 1: Git Command Line

```bash
# Add your new post
git add _posts/YYYY-MM-DD-your-post.md

# Commit with a descriptive message
git commit -m "Add new post about [topic]"

# Push to GitHub
git push origin main
```

### Option 2: GitHub Web Interface

1. Go to your repository on GitHub
2. Navigate to the `_posts` folder
3. Click "Add file" → "Create new file"
4. Name it `YYYY-MM-DD-your-post.md`
5. Paste your content with front matter
6. Click "Commit new file"

GitHub will automatically build and deploy your site within a few minutes.

## Tips and Best Practices

### SEO Optimization

1. **Title:** Keep it under 60 characters
2. **Description:** 150-160 characters, compelling summary
3. **Keywords:** 5-10 relevant keywords
4. **Headings:** Use proper H2, H3 hierarchy
5. **Images:** Always include alt text

### Content Structure

1. Start with a clear introduction
2. Use descriptive headings (H2, H3)
3. Include code examples with syntax highlighting
4. Add troubleshooting sections
5. End with a summary or conclusion

### Categories and Tags

**Categories:** Broad topics (Storage, Linux, Networking)
**Tags:** Specific keywords (nvme, spdk, rdma, ubuntu)

```yaml
categories: [Storage, NVMe]
tags: [nvme-of, roce, rdma, ubuntu, enterprise-storage]
```

### Date Format

Always use `YYYY-MM-DD` format:
- ✅ `2025-10-15`
- ❌ `10/15/2025`
- ❌ `15-10-2025`

## Common Issues

### Post Not Showing Up

**Check:**
1. File is in `_posts` directory
2. Filename format is `YYYY-MM-DD-title.md`
3. Front matter is properly formatted (YAML between `---` markers)
4. Date is not in the future
5. `layout: post` is specified

### Formatting Issues

**Check:**
1. YAML front matter has proper indentation
2. Code blocks use triple backticks (\`\`\`)
3. Lists have blank line before and after
4. No tabs (use spaces for indentation)

### Build Errors

**Check:**
1. Run `bundle exec jekyll build` locally to see errors
2. Check `_config.yml` for syntax errors
3. Verify all required plugins are in Gemfile
4. Check GitHub Pages build status in repository settings

## Markdown Cheat Sheet

```markdown
# H1 Heading
## H2 Heading
### H3 Heading

**Bold text**
*Italic text*
`Inline code`

[Link text](URL)
![Image alt text](image-url)

- Bullet point
- Another bullet

1. Numbered item
2. Another item

> Blockquote

---
Horizontal rule

Table:
| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
```

## Need Help?

- [Jekyll Documentation](https://jekyllrb.com/docs/)
- [GitHub Pages Documentation](https://docs.github.com/en/pages)
- [Markdown Guide](https://www.markdownguide.org/)
- Email: darren@soothill.com

---

Now you're ready to start adding blog posts! 🚀

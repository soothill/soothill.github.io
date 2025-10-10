---
layout: default
title: Home
---

<div class="container" style="text-align: center;">
    <h1 style="font-size: 3rem; margin-bottom: 1rem;">Welcome to Soothill Tech</h1>
    <p style="font-size: 1.3rem; color: #666; margin-bottom: 3rem;">Technical guides on storage, NVMe, SPDK, and enterprise infrastructure</p>

    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 2rem; margin-top: 3rem;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 2rem; border-radius: 8px; text-align: left;">
            <h2 style="color: white; border: none; margin: 0;">📝 Latest Blog Posts</h2>
            <p style="margin: 1rem 0;">Read the latest technical articles and guides</p>
            <a href="{{ site.baseurl }}/blog/" style="display: inline-block; background: white; color: #667eea; padding: 0.5rem 1.5rem; border-radius: 5px; text-decoration: none; font-weight: bold;">
                View Blog →
            </a>
        </div>

        <div style="background: #f8f9fa; padding: 2rem; border-radius: 8px; text-align: left; border: 2px solid #e0e0e0;">
            <h2 style="color: #667eea; border: none; margin: 0;">🚀 Quick Start Guides</h2>
            <p style="margin: 1rem 0;">Step-by-step setup instructions</p>
            <ul style="margin-left: 1.5rem;">
                <li><a href="/blog/2025/10/10/nvme-over-fabrics-roce-setup/" style="color: #667eea;">NVMe-oF with RoCE</a></li>
                <li><a href="/blog/2025/10/10/spdk-nvmeof-target-setup/" style="color: #667eea;">SPDK NVMe-oF Target</a></li>
                <li><a href="/blog/2025/10/07/change-nvme-format/" style="color: #667eea;">Change NVMe Format</a></li>
            </ul>
        </div>
    </div>

    <div style="margin-top: 4rem; padding: 2rem; background: #f8f9fa; border-radius: 8px;">
        <h2 style="color: #667eea;">Recent Posts</h2>
        <div style="display: grid; gap: 1.5rem; text-align: left; margin-top: 1.5rem;">
            {% for post in site.posts limit:3 %}
            <div style="border-left: 4px solid #667eea; padding-left: 1rem;">
                <h3 style="margin: 0;">
                    <a href="{{ post.url }}" style="color: #667eea; text-decoration: none;">{{ post.title }}</a>
                </h3>
                <p style="color: #666; font-size: 0.9rem; margin: 0.5rem 0;">
                    {{ post.date | date: "%B %d, %Y" }}
                </p>
                <p style="margin: 0.5rem 0;">
                    {{ post.excerpt | strip_html | truncatewords: 20 }}
                </p>
            </div>
            {% endfor %}
        </div>
    </div>
</div>

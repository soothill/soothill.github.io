/** Soot / Silicon — focused interaction layer */
(function () {
  'use strict';

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function initNavigation() {
    const nav = document.querySelector('.site-nav');
    const header = document.querySelector('.site-header');
    if (!nav || !header) return;
    let toggle = document.querySelector('.nav-toggle');
    if (!toggle) {
      toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.className = 'nav-toggle';
      toggle.setAttribute('aria-expanded', 'false');
      toggle.setAttribute('aria-controls', 'site-navigation');
      toggle.innerHTML = '<span>Menu</span><span class="nav-toggle__lines" aria-hidden="true"><i></i><i></i></span>';
      nav.id = nav.id || 'site-navigation';
      header.querySelector('.container, .header-inner')?.insertBefore(toggle, nav);
    }

    const close = () => {
      toggle.setAttribute('aria-expanded', 'false');
      nav.classList.remove('is-open');
    };

    toggle.addEventListener('click', () => {
      const open = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', String(!open));
      nav.classList.toggle('is-open', !open);
    });

    nav.querySelectorAll('a').forEach((link) => link.addEventListener('click', close));
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        close();
        toggle.focus();
      }
    });
    document.addEventListener('click', (event) => {
      if (!nav.contains(event.target) && !toggle.contains(event.target)) close();
    });
  }

  function initCodeCopy() {
    document.querySelectorAll('pre').forEach((block) => {
      if (block.querySelector('.copy-button')) return;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'copy-button';
      button.textContent = 'Copy';
      button.setAttribute('aria-label', 'Copy code');
      block.appendChild(button);

      button.addEventListener('click', async () => {
        const source = block.querySelector('code');
        try {
          await navigator.clipboard.writeText(source ? source.textContent : block.textContent.replace('Copy', ''));
          button.textContent = 'Copied';
          button.classList.add('copied');
        } catch (_error) {
          button.textContent = 'Select';
        }
        window.setTimeout(() => {
          button.textContent = 'Copy';
          button.classList.remove('copied');
        }, 1800);
      });
    });
  }

  function initArticleTools() {
    const article = document.querySelector('.post-content');
    if (!article) return;

    const words = article.textContent.trim().split(/\s+/).filter(Boolean).length;
    const readingTime = document.querySelector('.reading-time');
    if (readingTime) readingTime.textContent = `${Math.max(1, Math.ceil(words / 220))} min read`;

    const progress = document.createElement('div');
    progress.className = 'reading-progress';
    progress.setAttribute('aria-hidden', 'true');
    document.body.appendChild(progress);

    let frame;
    const updateProgress = () => {
      frame = null;
      const start = article.offsetTop;
      const distance = Math.max(article.offsetHeight - window.innerHeight, 1);
      const percent = Math.max(0, Math.min(100, ((window.scrollY - start + window.innerHeight * 0.35) / distance) * 100));
      progress.style.width = `${percent}%`;
    };
    window.addEventListener('scroll', () => {
      if (!frame) frame = window.requestAnimationFrame(updateProgress);
    }, { passive: true });
    updateProgress();

    const headings = Array.from(article.querySelectorAll('h2'));
    const toc = document.querySelector('.post-toc');
    const tocList = toc && toc.querySelector('ol');
    if (toc && tocList && headings.length >= 3) {
      headings.forEach((heading, index) => {
        if (!heading.id) heading.id = `section-${index + 1}`;
        const item = document.createElement('li');
        const link = document.createElement('a');
        link.href = `#${heading.id}`;
        link.textContent = heading.textContent;
        item.appendChild(link);
        tocList.appendChild(item);
      });
      toc.hidden = false;
    }
  }

  function initBackToTop() {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'back-to-top';
    button.textContent = '↑';
    button.setAttribute('aria-label', 'Back to top');
    document.body.appendChild(button);

    let frame;
    const update = () => {
      frame = null;
      button.classList.toggle('visible', window.scrollY > 700);
    };
    window.addEventListener('scroll', () => {
      if (!frame) frame = window.requestAnimationFrame(update);
    }, { passive: true });
    button.addEventListener('click', () => window.scrollTo({ top: 0, behavior: reduceMotion ? 'auto' : 'smooth' }));
  }

  function initLegacyHelpers() {
    document.querySelectorAll('[data-email]').forEach((link) => {
      link.href = 'mailto:darren@soothill.com';
      if (!link.textContent.trim() || link.textContent.includes('Loading')) link.textContent = 'darren@soothill.com';
    });

    const date = new Date(document.lastModified);
    document.querySelectorAll('#last-updated, #lastUpdated').forEach((node) => {
      if (!Number.isNaN(date.getTime())) node.textContent = date.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
    });
  }

  function initCookieSettings() {
    const button = document.querySelector('[data-cookie-settings]');
    if (!button) return;

    button.addEventListener('click', () => {
      if (window.Cookiebot && typeof window.Cookiebot.renew === 'function') {
        window.Cookiebot.renew();
        return;
      }
      button.textContent = 'Cookie settings unavailable — reload this page';
      button.disabled = true;
    });
  }

  function initServiceWorker() {
    if (!('serviceWorker' in navigator) || window.location.protocol !== 'https:') return;
    window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}));
  }

  function init() {
    initNavigation();
    initCodeCopy();
    initArticleTools();
    initBackToTop();
    initLegacyHelpers();
    initCookieSettings();
    initServiceWorker();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
}());

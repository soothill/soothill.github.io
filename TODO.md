# Website work list

Owner and final approver: Darren Soothill

Last reviewed: 16 August 2026

This file records work that is genuinely still open. It is excluded from the
published Jekyll site.

## Completed foundation

- [x] Establish a more natural, evidence-led UK English editorial voice.
- [x] Present Darren's product direction work across storage, GPUs and local AI.
- [x] Add published and updated dates to articles.
- [x] Order articles newest first and add an expandable Strix Halo archive.
- [x] Bring the PR22 articles into the current editorial style.
- [x] Add the expertise page and connect it to the site navigation.
- [x] Add a default Open Graph image and article-level image support.
- [x] Add production build, SEO, sitemap and link validation.
- [x] Add private Google Analytics and Search Console collection.
- [x] Schedule weekly analytics collection for Mondays at 07:00 UK time.
- [x] Exclude OAuth downloads and analytics reports from Git and Jekyll.
- [x] Move GitHub Actions and the build toolchain to Node.js 24.
- [x] Pin local and CI builds to Ruby 3.3.12 and bridge the two legacy Liquid
      taint methods removed from modern Ruby.

## Measurement

- [ ] Confirm the first unattended analytics collection completes successfully.
- [ ] Create an initial improvement chart after at least two weekly snapshots.
- [ ] Review the chart after four to six weeks and agree useful targets.

## Design assets

- [ ] Create dedicated PWA PNG icons from 72x72 through 512x512 pixels.
- [ ] Create individual social-sharing images for priority articles where the
      default site image is not specific enough.

## Editorial work

- [ ] Continue the ongoing Strix Halo series as runtimes, compatibility and
      stability change.
- [ ] Develop the bicycle overtaking analysis series around the method and the
      route to an answer, rather than publishing footage as the objective.

## Security and operations

- [ ] Permanently remove the downloaded OAuth client files from Trash after the
      first unattended analytics run has succeeded.
- [ ] Review GitHub Actions versions periodically and update them before their
      runtimes reach end of support.

## Deliberately deferred

- [ ] Correct the apex/non-www DNS behaviour. Darren has explicitly deferred
      this work; it is not a blocker for the canonical `www.soothill.io` site.

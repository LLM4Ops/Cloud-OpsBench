# Cloud-OpsBench project website

Plain static HTML/CSS/JavaScript. No build step, external font, analytics, or
frontend framework is required. Dataset files remain on Hugging Face; code stays
in the main GitHub repository. This directory contains the website only.

## Local preview

From the repository root:

```bash
python -m http.server 8765 --bind 127.0.0.1 --directory docs
```

Open http://127.0.0.1:8765/. Opening `index.html` directly also works, except that
clipboard permissions depend on the browser. Both tables remain visible if
JavaScript is disabled. The website includes all numbers from the supplied
performance table, without rounding or modifying values. JavaScript emphasizes
the best value in each system/metric, including ties and all minimum RAR values.

## Deploy after review

Merge `docs/` into the default branch. In GitHub repository settings:

1. Settings → Pages → Build and deployment.
2. Source: Deploy from a branch.
3. Branch: `main`; folder: `/docs`; save.

Expected project URL: https://llm4ops.github.io/Cloud-OpsBench/.
Relative asset paths support the project subdirectory. `.nojekyll` skips Jekyll
processing. Do not publish the whole repository root as the site.

No Pages settings are changed by adding these files. Canonical/Open Graph URLs
assume the project URL above; update them if using a different domain.

## Maintenance

- Page content, links, citations and all result values: `index.html`.
- Layout, mobile styles and colors: `assets/style.css`.
- System switcher, best-value emphasis and copy buttons: `assets/script.js`.
- Overview: `assets/overview.png`, copied from `resource/overview_new.png`.

The first version credits LLM4Ops / CUHK rather than inventing author profile
links or individual affiliations. Source citations are retained from the repo.

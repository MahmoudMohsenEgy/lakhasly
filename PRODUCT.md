# Product

## Register

product

## Users

Self-directed learners who read English comfortably but absorb and retain material
far better from a well-structured Egyptian-Arabic document than from long English
videos or courses. The primary user is working through online course modules
(e.g. Coursera) and articles, copy-pasting one transcript or article at a time.
Context of use: focused, often long study sessions at a desk; the user wants to
turn raw English content into something they'll actually sit down and study.

## Product Purpose

A local web app that wraps the existing explainer agent. The user pastes English
learning content (a module transcript, an article), names it, and the app produces
an Egyptian-Arabic study **PDF** — explanation with technical terms kept in English,
rendered diagrams, and a review quiz with an answer key. The app also lets the user
read the resulting PDF in place and find their previously generated modules.

Success looks like: paste content → name it → generate → read a study-ready PDF,
repeated comfortably module after module, without fighting the tool.

## Brand Personality

Friendly, encouraging, simple — a warm but grown-up study companion. The voice is
plain and supportive (it speaks Egyptian Arabic to the user, the way a helpful study
buddy would), never stiff or corporate, and never childish. Calm and content-first:
the interface stays quiet so the material and the work take center stage. The
interface defaults to friendly, plain English and can be switched to Egyptian Arabic;
the generated study documents are always Egyptian Arabic regardless of interface language.

## Anti-references

- **Generic admin dashboard** — cards-everywhere, sidebar-plus-widgets, soulless CRUD.
- **Flashy AI SaaS** — purple/blue gradients, glowing hero-metric blocks, "supercharge
  your learning" buzzword energy.
- **Cluttered edtech (Coursera-style)** — busy, banner-heavy density with competing UI.
- **Childish gamified edu** — cartoon mascots, confetti, badges, bright primary colors.

The hard tension to hold: *friendly without being childish*, *warm without being
flashy*. Warmth comes from tone, spacing, and small considered touches — not from
gradients, mascots, or gamification.

## Design Principles

- **English-first interface, Egyptian Arabic on demand.** The UI defaults to friendly,
  plain English (left-to-right) and can switch to a full Egyptian Arabic (right-to-left)
  mode. The generated documents are always Egyptian Arabic, regardless of interface language.
- **The content is the hero.** The paste surface and the resulting study document
  dominate; navigation and chrome recede. No dashboard sprawl.
- **One obvious action per moment.** Guide the single workflow — paste, name, generate,
  read — so the next step is always clear; don't present a wall of options.
- **Friendly, never childish.** Personality lives in copy, rhythm, and restraint, not
  in mascots, confetti, or gamified rewards.
- **Built for long sessions.** Low eye strain by default, comfortable Arabic reading
  sizes, and calm motion that never competes with the work.

## Accessibility & Inclusion

- **Dark mode is a first-class priority** — comfortable for long, often late study
  sessions; not an afterthought toggle.
- **WCAG AA contrast** everywhere; no faint gray-on-tinted-white body text.
- **Correct in both directions** — English (default) is left-to-right; the Egyptian Arabic
  interface mode is fully right-to-left with comfortable Arabic reading sizes and inline
  English/code bidi-isolated. Build with CSS logical properties so the layout mirrors cleanly.
- **Reduced-motion honored** — every animation has a calm/instant alternative under
  `prefers-reduced-motion`.

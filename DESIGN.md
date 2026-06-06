<!-- SEED: re-run /impeccable document once there's code to capture the actual tokens and components. -->
---
name: Egyptian-Arabic Content Explainer
description: A calm, bilingual, dark-first study tool that turns English course content into Egyptian-Arabic study PDFs.
---

# Design System: Egyptian-Arabic Content Explainer

## 1. Overview

**Creative North Star: "The Lamplit Desk"**

A quiet desk in a dim room, late at night, with a single warm reading lamp throwing
amber light onto the page you're studying. The room (the interface) stays dark and
calm so it never competes with the work; the lamp (one warm accent) marks exactly
where to act and what matters right now; the page (your pasted content and the study
document it becomes) is the only thing truly lit. Everything serves sitting down and
studying, comfortably, for a long time.

The system is **restrained and content-first**: tinted dark neutrals carry almost the
whole surface, and a single warm amber accent appears rarely and deliberately. It is
**English-first and bilingual** — the interface defaults to friendly, plain English
(left-to-right) and can switch to a full Egyptian Arabic (right-to-left) mode; the
generated documents are always Egyptian Arabic regardless of interface language. Warmth
comes from the amber light, generous spacing, and plain friendly copy, never from decoration.

This system explicitly rejects four things (from PRODUCT.md): the **generic admin
dashboard** (cards-everywhere, sidebar-plus-widgets CRUD), the **flashy AI SaaS** look
(purple/blue gradients, glowing hero-metric blocks, buzzword energy), **cluttered
Coursera-style edtech** (busy, banner-heavy density), and **childish gamified edu**
(mascots, confetti, badges, bright primaries). The hard line it holds: *friendly without
childish, warm without flashy.*

**Key Characteristics:**
- Dark-first, calm, low eye strain for long study sessions
- One warm amber accent, used sparingly (the lamp)
- English-first interface (LTR), switchable to full Egyptian Arabic (RTL); output always Arabic
- Content (paste surface + study document) is the hero; chrome recedes
- Gentle, responsive motion with a reduced-motion fallback

## 2. Colors

A restrained, dark-first palette: warm-tinted dark neutrals doing nearly all the work,
with a single amber accent for the few things that matter. Exact values are resolved at
implementation; OKLCH is the working space. `[hex/oklch to be resolved during implementation]`

### Primary
- **Lamp Amber** `[to be resolved during implementation]`: the single warm accent —
  the primary action (Generate), focus rings, active states, and generation progress.
  Used on ≤10% of any screen. In dark mode it reads as a soft warm glow, not a flat fill.

### Neutral
- **Room (background)** `[to be resolved during implementation]`: deep, near-black
  neutral with a faint warm tint toward the amber hue (deliberate, not default-warm).
- **Surface / Elevated surface** `[to be resolved during implementation]`: one or two
  steps up from the background for the paste panel and the document reader.
- **Ink (primary text)** `[to be resolved during implementation]`: warm near-white,
  comfortable for long Arabic reading; hits WCAG AA on every surface.
- **Muted text / borders / dividers** `[to be resolved during implementation]`: dimmed
  ink for secondary labels and hairline separators — never so faint it fails AA.

A light theme is a secondary deliverable; dark mode is designed first.

### Named Rules
**The One Lamp Rule.** The amber accent appears on at most ~10% of any screen. Its
rarity is what makes it read as "act here". If two things are amber, neither is the lamp.

**The Deliberate-Tint Rule.** Neutrals tint slightly toward the amber hue on purpose
(the lamplight), not toward generic "warm by default". Tint is small (low chroma) and
consistent across the ramp.

## 3. Typography

**Display / Body Font:** A single humanist sans with a matching Arabic face
`[font pairing to be chosen at implementation — candidates: Readex Pro, IBM Plex Sans +
IBM Plex Sans Arabic, or Cairo (already used in the output PDF) for visual continuity]`.
**Mono (optional, for English code/terms):** `[optional mono to be chosen at implementation]`.

**Character:** One warm, friendly, highly legible humanist family carries the whole
interface; hierarchy comes from **scale and weight contrast** (≥1.25 ratio between steps),
not from extra typefaces. English reads as the friendly default; Arabic legibility leads
in the Egyptian Arabic mode.

### Hierarchy
- **Display** (700, large clamp, tight line-height): the app's one big moment (e.g. the
  paste-screen heading). Used once per screen, not as a section reflex.
- **Headline / Title** (600–700, ~1.25× steps): section and panel headings.
- **Body** (400, comfortable Arabic reading size, line-height ~1.8): UI text and any
  prose; cap measured prose at 65–75ch.
- **Label** (500, small, no all-caps Arabic): controls, field labels, quiet metadata.

### Named Rules
**The Two-Direction Rule.** The interface defaults to English (LTR). An Egyptian Arabic
mode flips the whole layout to RTL — build with CSS logical properties (`margin-inline`,
`padding-inline`, `inset-inline`) so it mirrors cleanly, never hard-coded left/right. In
either mode, English terms/code inside Arabic text are bidi-isolated (`unicode-bidi:
isolate`). Never set Arabic in ALL CAPS; never letter-space Arabic.

**The One-Family Rule.** One humanist family in multiple weights does the work. A mono is
allowed only for English code/terms. Three families maximum, and three is already a lot.

## 4. Elevation

Flat by default. Surfaces are distinguished by tonal layering (slightly lighter dark
neutrals), not by drop shadows at rest. Depth appears only as a **response to state**:
a soft warm glow under the amber accent on hover/focus, a gentle lift on the active
panel while generating. In dark mode, glow (not hard shadow) is the depth material.

### Named Rules
**The Flat-At-Rest Rule.** No decorative shadows on idle surfaces. If there's a shadow,
something is happening (hover, focus, in-progress). The amber glow is reserved for the lamp.

## 6. Do's and Don'ts

### Do:
- **Do** design dark mode first, and verify WCAG AA contrast in both themes (no faint
  gray-on-tinted text — bump body color toward ink if it's even close).
- **Do** keep the amber accent to ≤10% of any screen (the One Lamp Rule).
- **Do** lead Arabic RTL and bidi-isolate inline English/code so it never breaks the flow.
- **Do** let the paste surface and the study document dominate; keep navigation minimal.
- **Do** keep motion gentle and responsive, always with a `prefers-reduced-motion` fallback.

### Don't:
- **Don't** build a **generic admin dashboard** — no cards-everywhere, sidebar-plus-widgets,
  soulless CRUD layout.
- **Don't** do **flashy AI SaaS** — no purple/blue gradients, no glowing hero-metric blocks,
  no "supercharge your learning" buzzword energy.
- **Don't** make it **cluttered Coursera-style edtech** — no busy, banner-heavy density with
  competing UI fighting for attention.
- **Don't** go **childish / gamified** — no mascots, confetti, badges, or bright primary colors.
- **Don't** use gradient text, glassmorphism-by-default, or colored side-stripe borders
  (`border-left`/`-right` > 1px as an accent). These are banned outright.

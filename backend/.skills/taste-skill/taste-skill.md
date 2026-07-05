---
name: taste-skill
description: Anti-Slop Frontend Framework for AI Agents — 赋予 AI 良好的前端设计品味，杜绝千篇一律的 AI 风格界面
category: 前端设计
enabled: false
builtin: false
---
# Taste Skill — Anti-Slop Frontend Framework

## Three Dials (调节旋钮)

Before writing any code, set these three dials based on the brief. Default baseline: **DESIGN_VARIANCE=8, MOTION_INTENSITY=6, VISUAL_DENSITY=4**

| Dial | 1-3 (Low) | 4-7 (Medium) | 8-10 (High) |
|---|---|---|---|
| DESIGN_VARIANCE | Symmetric, centered, conventional | Balanced with moments of difference | Asymmetric, experimental, broken-grid |
| MOTION_INTENSITY | Static, hover-only | Subtle transitions | Cinematic GSAP/Framer Motion |
| VISUAL_DENSITY | Airy, spacious | Balanced information density | Dense, dashboard-like |

## Brief Inference Protocol

Before writing a single line of code, analyze the brief:

1. **Visual Thesis** — One sentence capturing the mood, material, and energy of the design
2. **Layout Thesis** — What makes this layout memorable or distinctive
3. **Interaction Thesis** — 2-3 specific motions or transitions that define the feel

## Design System Map

When a known design system is detected, use its official package:

- **shadcn/ui** → `@radix-ui/*` + `class-variance-authority`
- **Tailwind UI** → official component library
- **Aceternity UI** → `aceternity-ui`
- **Magic UI** → `magic-ui`
- **NextUI** → `@nextui-org/react`
- **MUI** → `@mui/material`
- **Ant Design** → `antd`

## Typography

- **Preferred fonts**: Geist, Outfit, Cabinet Grotesk, Satoshi, DM Sans
- **Serif fonts**: BANNED for dashboards and data-heavy UIs (reserved for editorial/long-form)
- **Inter, Arial, Roboto**: BANNED as default fonts (overused AI tell)
- **Font pairing**: Max 2 font families per page
- **Line height**: 1.5 for body text, 1.1-1.2 for headings

## Color Rules

- **Max 1 accent color** (do not use multiple accent colors)
- **Saturation**: Keep accent colors below 80% saturation
- **Banned colors**: `#6C63FF`, `#7C3AED`, `#8B5CF6` (AI-purple/blue)
- **Neutrals**: Use warm or cool grays, never pure `#333`/`#666`/`#999`
- **Dark mode**: Never use pure `#000` for backgrounds — use `#0a0a0f`, `#111`, `#1a1a1a`

## Layout Rules

- **Cards are NOT the default layout**. Use cards only when elevation communicates hierarchy.
- **`h-screen` is BANNED**. Use `min-h-[100dvh]` instead.
- **Flexbox percentage math is discouraged**. Use CSS Grid for complex layouts.
- **Em-dash (`--`) is COMPLETELY BANNED** in UI copy, headings, or decorative elements.
- **Section-numbering eyebrows are BANNED** (`00 / INDEX`, `001 . Capabilities`)
- **Version labels in hero sections are BANNED** (`V0.6`, `BETA`) unless explicitly a launch
- **Scroll cues are BANNED** (`Scroll`, `Scroll to explore`, down arrow)
- **Decorative status dots and fake product mockups are BANNED**
- **Emojis are BANNED in code, markup, UI copy, and alt text**

## Pre-Flight Checklist

1. Single clear visual idea (not a collage of trends)
2. Intentional typography hierarchy (not system defaults)
3. Disciplined accent palette (max 1 accent color)
4. Cards used only where elevation communicates hierarchy
5. Controlled, purposeful motion (not decorative)
6. Stable on mobile (no overflow, no broken grid)
7. Dark mode tested
8. No banned patterns remain (em-dash, scroll cues, AI-purple, etc.)

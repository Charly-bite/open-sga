# QB UI Guidelines

This document outlines the visual and interaction principles for the QB enterprise applications (SGA, OMS, WMS). When developing interfaces, ensure these guidelines are strictly followed.

## 1. Overall Aesthetics
- **Premium Feel:** The UI should feel modern, crisp, and robust. It is designed for enterprise data but avoids looking archaic.
- **Glassmorphism (Subtle):** Use subtle blur effects (e.g., `backdrop-filter: blur(8px)`) on sticky headers, modals, or dropdown menus to add depth.
- **Depth and Shadows:** Use shadows (`--shadow-sm`, `--shadow-md`) to elevate active elements. The application background should be a subtle off-white (`--bg-app`), while content areas like cards use solid white (`--bg-surface`) to create natural hierarchy.

## 2. Components

### Buttons
- **Primary Buttons:** Background `--color-primary-600`, Text `--text-inverse`. On hover, shift to `--color-primary-700`. Include a slight transform (`transform: translateY(-1px)`) and a shadow for tactile feedback.
- **Secondary Buttons:** Background transparent, Border `--border-strong`, Text `--text-primary`. On hover, background shifts to `--bg-surface-hover`.
- **Border Radius:** All buttons use `--radius-md` (6px) for a structured yet friendly look.
- **States:** Active and Focus states must be distinct. Always apply `--shadow-focus` when a button is tab-focused.

### Data Tables
- **Layout:** High density but legible. Use `--spacing-3` for table cell padding.
- **Headers:** Text should be `--text-xs` or `--text-sm`, upper-case with letter-spacing, using `--text-secondary`.
- **Rows:** Zebra-striping is optional; prefer subtle hover effects (background turns to `--bg-surface-hover` on row hover) to guide the eye. Use `--border-subtle` for bottom borders.
- **Interactivity:** Action menus at the end of the rows should only appear or darken on row hover to reduce visual clutter.

### Forms and Inputs
- **Inputs:** Background `--bg-surface`, Border `--border-subtle`. On focus, change border to `--color-primary-500` and apply `--shadow-focus`.
- **Labels:** Place above inputs. Use `--text-sm` and `--font-weight-medium`.
- **Validation:** Use `--color-error` for borders and helper text when an input is invalid. Provide clear inline feedback.

### Cards and Containers
- **Styling:** Cards should have `--bg-surface`, `--radius-lg`, and a subtle `--shadow-sm`.
- **Padding:** Use `--spacing-6` for internal padding of major cards, `--spacing-4` for denser nested cards.
- **Headers:** Card titles should be `--text-lg` with `--font-weight-semibold` and `--text-primary`.

## 3. Micro-Animations & Interaction
- **Transitions:** Every interactive element must use the `--transition-fast` variable for state changes (hover, focus, active).
- **Loading States:** Use skeleton loaders rather than full-page spinners where possible to make the app feel faster.
- **Empty States:** Empty states should be designed beautifully. Use a subtle illustration or icon (`--text-secondary`) and a clear call-to-action button.

## 4. Accessibility & Responsiveness
- **Contrast:** Ensure all text passes WCAG AA contrast ratios against its background.
- **Responsiveness:** While primarily designed for desktop enterprise use, ensure layouts use flexbox and grid to degrade gracefully to tablet sizes. Use a standard 12-column grid system logic.

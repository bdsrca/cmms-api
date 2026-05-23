# Progressive Console UI Polish Design

## Goal

Make the local CMMS LLM management portal easier to scan and less crowded while keeping the existing single-file UI architecture, endpoint calls, permissions, and operator workflows intact.

## Direction

Use the selected Progressive Console direction:

- Show the primary purpose and main action of each page first.
- Group secondary controls into clearer sections or collapsed advanced areas where practical.
- Add more page spacing, calmer card rhythm, and lighter visual hierarchy.
- Keep the portal as a professional operational console, not a marketing page.

## Scope

This pass is visual and layout-only. It may update HTML structure inside `app/ui.py`, CSS classes, labels, section wrappers, and client-side rendering helpers. It must not change API contracts, validation gates, authentication, CMMS connector behavior, auto-push rules, or process controls.

## Global Layout

- Keep the current top bar plus left navigation shell.
- Make the content area feel less cramped with wider vertical spacing and clearer section gaps.
- Give page headers a consistent title, optional short subtitle, and a small action area.
- Use restrained cards: cards frame meaningful panels, not every small text fragment.
- Avoid nested-card layouts.

## Navigation

- Group navigation into readable zones such as Operate, Configure, Quality, and Admin.
- Keep the current page IDs and routing behavior.
- Use lighter active states and avoid a dense uninterrupted list of buttons.
- Preserve admin-only indicators, but make them subtle and aligned.

## Page Composition

- Dashboard should prioritize overall readiness/status over many equal metric tiles.
- Review and tuning pages should separate operator decisions from advanced/test controls.
- Tables should use calmer row spacing, muted borders, and compact action buttons.
- Forms should use short sections with clear labels and comfortable field spacing.

## Dropdown Style

- Modernize dropdowns to feel closer to native iOS/Android controls: rounded shape, soft background, clear affordance, larger touch target, and a calm focus ring.
- Prefer styling native `<select>` elements for reliability. If a page needs a custom dropdown later, it should be introduced only for a specific UX need.
- Add a reusable wrapper/class pattern, such as `.select-wrap` and `.cmms-select`, so future dropdowns can opt into the same appearance.
- Preserve keyboard navigation, screen-reader labels, and form behavior.

## Visual System

- Keep a light console palette: white surfaces, soft gray background, muted borders, and blue/cyan accents.
- Use 8-12px radii for controls and cards.
- Use subtle shadows only for meaningful layered elements.
- Avoid heavy gradients, decorative blobs, or large hero-style treatment.

## Verification

- Run focused UI-related tests if available.
- Run at least a smoke check that `/ui` still renders.
- If a dev server is started, visually inspect the portal in a browser-sized viewport.

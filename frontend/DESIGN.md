---
version: draft-1
name: AIControl-design-system
description: >
  Governance tooling for enterprise business-workflow agents, built to be read all day and
  demoed in a boardroom. Anchors on a warm cream canvas (#FBF9F3) rather than clinical white,
  with a single brand voltage of electric magenta (#FF2D7A) reserved for primary actions, the
  active nav marker, and the editable chips inside a policy sentence. Display type sits at
  weight 400 with hard negative tracking, so headings read editorial rather than SaaS. The
  system's signature is the policy sentence: a rule set large as running prose, with its
  scope rendered as tactile magenta chips the user clicks to change. Decision states are
  carried by weight and fill, not by a second bright hue -- deny is near-black, never a red
  competing with the brand.

# ---------------------------------------------------------------------------
# COLORS
# Anchor: #FF2D7A. Chosen after a scan of the category -- chartreuse is held by
# PlainID (#c0fd27), amber by Cerbos (#ffc11e), violet by Oso and Zenity, cyan by
# Lakera and Workato. Magenta was empty, and it is the one bright hue that does not
# collide with allow / deny / review.
# ---------------------------------------------------------------------------
colors:
  primary: "#FF2D7A"
  primary-active: "#E01A63"
  primary-soft: "#FFE7F0"
  primary-disabled: "#F0DDE4"
  on-primary: "#FFFFFF"

  ink: "#1A1815"
  body: "#57534A"
  body-strong: "#33302A"
  muted: "#8A857A"
  muted-soft: "#B3ADA0"

  hairline: "#E7E2D7"
  hairline-soft: "#F0ECE3"
  hairline-strong: "#D5CEC0"

  canvas: "#FBF9F3"
  canvas-soft: "#FEFDFA"
  surface-card: "#FFFFFF"
  surface-sunk: "#F3F0E8"
  surface-ink: "#1A1815"
  surface-ink-elevated: "#26231D"
  on-ink: "#FBF9F3"
  on-ink-soft: "#A8A296"

  # Decision states. Deny is deliberately achromatic -- a red here would fight the
  # brand magenta at every glance. Deny reads by weight: a solid near-black fill.
  decision-allow: "#1F7A5C"
  decision-allow-soft: "#E4F1EB"
  decision-review: "#1D5FA8"
  decision-review-soft: "#E4EDF8"
  decision-deny: "#1A1815"
  decision-deny-soft: "#EAE6DD"

  # Status, used only in system messaging -- never on a decision.
  success: "#1F7A5C"
  warning: "#A66413"
  error: "#A32036"

# ---------------------------------------------------------------------------
# TYPOGRAPHY
# Display sits at 400 with negative tracking (the Cursor move), so headings read
# editorial. Weight is never used to shout; size and space carry hierarchy.
# `sentence` is the signature style -- see components.policy-sentence.
# Display face: Bricolage Grotesque (variable, Google Fonts) -- chosen for its odd
# terminals and irregular rhythm, which is where this system's playfulness lives.
# Body: Inter. Code and identifiers: JetBrains Mono. Three families, no more.
# ---------------------------------------------------------------------------
typography:
  display-xl:
    fontFamily: "Bricolage Grotesque, Inter, sans-serif"
    fontSize: 64px
    fontWeight: 400
    lineHeight: 1.04
    letterSpacing: -2.4px
  display-lg:
    fontFamily: "Bricolage Grotesque, Inter, sans-serif"
    fontSize: 48px
    fontWeight: 400
    lineHeight: 1.08
    letterSpacing: -1.8px
  display-md:
    fontFamily: "Bricolage Grotesque, Inter, sans-serif"
    fontSize: 36px
    fontWeight: 400
    lineHeight: 1.14
    letterSpacing: -1.2px
  display-sm:
    fontFamily: "Bricolage Grotesque, Inter, sans-serif"
    fontSize: 28px
    fontWeight: 450
    lineHeight: 1.2
    letterSpacing: -0.8px
  sentence:
    fontFamily: "Bricolage Grotesque, Inter, sans-serif"
    fontSize: 32px
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: -0.9px
  sentence-inline:
    fontFamily: "Inter, sans-serif"
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: -0.1px
  title-lg:
    fontFamily: "Bricolage Grotesque, Inter, sans-serif"
    fontSize: 22px
    fontWeight: 500
    lineHeight: 1.3
    letterSpacing: -0.4px
  title-md:
    fontFamily: "Inter, sans-serif"
    fontSize: 17px
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: -0.2px
  title-sm:
    fontFamily: "Inter, sans-serif"
    fontSize: 15px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 0
  body-md:
    fontFamily: "Inter, sans-serif"
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: 0
  body-sm:
    fontFamily: "Inter, sans-serif"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: 0
  caption:
    fontFamily: "Inter, sans-serif"
    fontSize: 13px
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: 0
  label-uppercase:
    fontFamily: "Inter, sans-serif"
    fontSize: 11px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 1.2px
    textTransform: uppercase
  code:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: 13.5px
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: 0
  identifier:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: 13px
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: -0.2px
  button:
    fontFamily: "Inter, sans-serif"
    fontSize: 14px
    fontWeight: 550
    lineHeight: 1
    letterSpacing: 0
  nav-link:
    fontFamily: "Inter, sans-serif"
    fontSize: 14px
    fontWeight: 450
    lineHeight: 1.4
    letterSpacing: 0

rounded:
  xs: 4px
  sm: 6px
  md: 8px
  lg: 14px
  chip: 8px
  pill: 9999px

spacing:
  xxs: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  xxl: 48px
  section: 80px

motion:
  micro: "120ms cubic-bezier(0.2, 0, 0, 1)"
  standard: "200ms cubic-bezier(0.2, 0, 0, 1)"
  entrance: "260ms cubic-bezier(0.16, 1, 0.3, 1)"
  reduced-motion: "All transforms and translations drop to opacity-only. Never optional."

# ---------------------------------------------------------------------------
# COMPONENTS
# ---------------------------------------------------------------------------
components:

  # THE SIGNATURE. A policy is never shown as JSON, Cedar, or a form in the default
  # view. It is one sentence set as running prose, with every scoped part rendered
  # as an editable chip. The same sentence object appears in the policy list, the
  # agent's "what governs me" list, the NL draft review, the simulation result, and
  # the audit event that fired it. One representation everywhere.
  policy-sentence:
    typography: "{typography.sentence}"
    textColor: "{colors.ink}"
    maxWidth: 26ch-per-line-at-display-size
    chipSpacing: 6px
    notes: >
      Reads: "claims-adjuster may not release a payment on Guidewire when amount > 50,000."
      Fixed words are ink. Every variable is a chip. The consequence clause ("instead: send
      for approval") sits on its own line, indented, introduced by a turn-down arrow.

  policy-chip:
    backgroundColor: "{colors.primary-soft}"
    textColor: "{colors.primary-active}"
    borderColor: "transparent"
    typography: "{typography.identifier}"
    rounded: "{rounded.chip}"
    padding: 4px 10px
    hover:
      backgroundColor: "#FFD9E8"
      cursor: text
    focus:
      outline: "2px solid {colors.primary}"
      outlineOffset: 2px
    notes: >
      The only place magenta appears at scale. A chip is always editable -- if a value
      cannot be changed it is set as plain ink, never as a chip. That rule is what makes
      the colour mean something.

  decision-pill:
    rounded: "{rounded.pill}"
    padding: 3px 10px
    typography: "{typography.label-uppercase}"
    variants:
      allow:
        backgroundColor: "{colors.decision-allow-soft}"
        textColor: "{colors.decision-allow}"
      review:
        backgroundColor: "{colors.decision-review-soft}"
        textColor: "{colors.decision-review}"
      deny:
        backgroundColor: "{colors.decision-deny}"
        textColor: "{colors.on-ink}"
    notes: >
      Deny is the only filled pill. It is the heaviest object on any screen it appears on,
      by design, and it carries no hue that competes with the brand.

  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 11px 18px
    height: 40px
    hover: { backgroundColor: "{colors.primary-active}" }
    transition: "{motion.micro}"

  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    borderColor: "{colors.hairline-strong}"
    borderWidth: 1px
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 11px 18px
    height: 40px
    hover: { backgroundColor: "{colors.surface-sunk}" }

  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.body}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: 11px 14px
    hover: { textColor: "{colors.ink}", backgroundColor: "{colors.surface-sunk}" }

  nav-item:
    typography: "{typography.nav-link}"
    textColor: "{colors.body}"
    padding: 8px 14px
    rounded: "{rounded.sm}"
    hover: { textColor: "{colors.ink}", backgroundColor: "{colors.surface-sunk}" }
    active:
      textColor: "{colors.ink}"
      backgroundColor: "{colors.surface-sunk}"
      marker: "3px {colors.primary} bar, left edge, full item height, {rounded.pill}"
    notes: >
      Flat list. No section headers, no accordions, no per-item icons, no lock or
      greyed-out entries. If a destination is not built, it is not in the nav.

  card:
    backgroundColor: "{colors.surface-card}"
    borderColor: "{colors.hairline}"
    borderWidth: 1px
    rounded: "{rounded.lg}"
    padding: 24px
    shadow: none
    notes: "Hairlines, never shadows. Elevation is expressed by surface, not by blur."

  table-row:
    borderBottomColor: "{colors.hairline-soft}"
    padding: 14px 16px
    typography: "{typography.body-sm}"
    hover: { backgroundColor: "{colors.canvas-soft}" }
    notes: >
      Never wrap a variable-length table in overflow-hidden -- it silently clips rows.
      Use overflow-y-auto. (Known project pitfall, see .claude/CLAUDE.md.)

  empty-state:
    typography: "{typography.title-lg}"
    textColor: "{colors.muted}"
    notes: >
      An invitation, never a blank. "No policies govern this agent yet -- describe one in
      plain English." followed by the primary action. Written in the interface's voice.

principles:
  - >
    One question per screen. Every page answers one question in its first viewport.
    The landing screen answers "what did governance actually do?" in business terms --
    payments held, record access denied, exports blocked -- not in stat tiles.
  - >
    Magenta is rationed. Primary buttons, the active nav marker, and editable chips.
    Nothing else. If magenta appears on a screen more than a few times, something is
    wrong with the screen.
  - >
    Engine vocabulary never surfaces. No principal, action, resource, Cedar, Rego, or
    JSONB in the default UI. The UI says which agent, what it may do, where, and under
    what condition. Raw rule text lives behind a "view rule" disclosure.
  - >
    Weight before hue. Importance is carried by fill, size and space. The palette holds
    one bright colour and three decision states, and that is the whole budget.
  - >
    Buttons name their effect and keep the word through the flow. "Activate" produces
    "Activated". "Send for approval" produces "Sent for approval".
  - >
    Quality floor, unannounced: responsive to mobile, visible keyboard focus on every
    interactive element, reduced motion respected, contrast checked against the cream
    canvas rather than against white.

theme:
  mode: light-only
  notes: >
    One theme, executed properly. The existing ThemeContext, the toggle in the sidebar,
    and every dark-mode branch in the frontend are removed as part of the overhaul.
    Every value above is nonetheless expressed as a semantic token (canvas, surface, ink,
    hairline, decision-*) rather than a literal, so a dark theme later is a second token
    file rather than a rewrite. Contrast is checked against the cream canvas #FBF9F3,
    never against white -- text that passes on white can fail on cream.

decisions-log:
  - "Anchor #FF2D7A: chartreuse held by PlainID, amber by Cerbos, violet by Oso/Zenity, cyan by Lakera/Workato. Magenta was the one bright hue both unclaimed in-category and free of collision with allow/deny/review."
  - "Canvas warm cream, not white: this product is read all day -- audit logs, policy lists -- and a warm ground is what stops enterprise light mode reading as a spreadsheet."
  - "Display at weight 400 with hard negative tracking: headings read editorial rather than SaaS. Weight is never used to shout."
  - "Review is blue, not amber: magenta already occupies the warm-bright slot, and amber beside it reads muddy."
  - "Deny is achromatic near-black: a red would fight the brand magenta on every screen showing both. Deny reads by weight instead, which makes it the heaviest object wherever it appears."
  - "Bricolage Grotesque for display: the playfulness lives in the letterforms, so the rest of the system can stay quiet."

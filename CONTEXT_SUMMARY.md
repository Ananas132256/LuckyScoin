# LuckyScoin Project Summary

## Overview

This project evolved around a Telegram casino bot and supporting economics, season, admin, and analytics systems. The work was intentionally additive and backwards-compatible: new tables and columns were introduced without altering existing schemas unless the task explicitly required it, and existing behavior was preserved behind feature gates and migration safeguards.

## History of major work

### 1) Additive activity analytics and admin dashboards
- Added new database tables for activity analytics:
  - `events` for the live activity feed
  - `daily_visits` for daily retention counting
- Added migration-safe `users` columns:
  - `last_screen`
  - `last_screen_ts`
- Added analytics methods for:
  - event logging
  - recent event retrieval
  - top active screens
  - daily visit tracking and retention summary
  - economy summary and wealth distribution
  - top purchase reports
  - dead-content detection for cosmetics and casino items
- Added admin analytics support and helper screens without touching existing tables or legacy methods.

### 2) Update/season/conversion infrastructure
- Added update, season, and conversion config constants.
- Added persistent flags and season-state support.
- Added conversion logic for one-time LC → SC migration with tiered cascading rates.
- Added celebration/welcome-screen handling for first-time update users.
- Added admin confirmation flow for applying the update.

### 3) Free limited title flow ("Старичок")
- Added the free limited title mechanic without disrupting normal shop logic.
- Preserved positive-price filtering for purchasable items while allowing a valid zero-price limited title to be tracked and claimed.
- Added claim-button and ownership logic in the relevant shop/inventory flow.

### 4) Season reset and banner flow
- Added admin support for ending a season and confirming reset actions.
- Added season rollover rewards and `season_current` state handling.
- Added a season banner in the main menu.
- Preserved progression-critical stats while clearing seasonal economy and casino state as required.

### 5) Fixes and cleanup
- Fixed the bomb aftermath copy so the game description matched actual multiplier behavior.
- Removed dead animation methods that were no longer referenced.
- Kept the rest of the gameplay flow untouched.

### 6) Auto season rollover and DB preservation
- Added a background hourly season rollover loop.
- Started the rollover task during bot startup.
- Kept user progression values like `level` and `xp` while clearing seasonal economy and casino data as intended.

### 7) Tycoon reconstruction guard
- Added a global tycoon feature flag and placeholder mode.
- Kept DB tables for casino rooms/staff/casinos intact.
- Gated all tycoon callbacks behind the flag so deep links and direct access cannot bypass the placeholder screen.
- Updated the main menu label to show a repair state when disabled.

### 8) Tiered conversion rewrite
- Replaced the flat 2500:1 model with a cascaded conversion model:
  - first 100,000 LC → 500 LC = 1 SC
  - above that → 5,000 LC = 1 SC
- Kept the conversion logic and summary output compatible with existing flag storage patterns.
- Updated the admin confirmation and celebration text to reflect the new tier-aware conversion schedule.

### 9) Maintenance-off welcome-back sequence
- Changed the maintenance shutdown flow to send a two-step welcome-back sequence instead of a plain broadcast.
- Sends a short service message, waits ~1.5 seconds, then sends the celebration GIF or fallback text.
- Marks the user as seen so `/start` does not retrigger the celebration.
- Uses a one-shot `welcome_back_sent_v100` guard to prevent duplicate rebroadcasts.

### 10) Leaderboard self-rank indicator
- Added self-rank lookup methods to DB.
- Updated leaderboard rendering to:
  - mark the player's own row with a highlight when in the top 10
  - show a dedicated `Ты` row beneath the list when they are not in the top 10
  - include a near-cutoff nudge if they are close to the top-10 threshold
  - preserve the original ranking query logic and only append the user-specific block beneath it

## Work completed

- [x] Additive DB analytics and admin analytics screens
- [x] Seasonal and conversion infrastructure
- [x] Update celebration welcome flow
- [x] Limited free title flow
- [x] Admin season rollover and maintenance toggle adjustments
- [x] Tycoon feature flag and reconstruction placeholder
- [x] Tiered conversion rewrite
- [x] Maintenance-off welcome-back broadcasting
- [x] Leaderboard self-rank block below top 10
- [x] Dead-code cleanup and bomb aftermath text fix

## Key files affected

- `db.py`
  - Core storage layer for migration-safe schema changes, analytics queries, conversion logic, flags, leaderboard rank lookups, and celebration tracking.
- `menu.py`
  - Main menu UI, celebration flow, leaderboard/self-rank rendering, and update banner logic.
- `admin.py`
  - Admin commands, confirmation screens, update application flow, maintenance toggle flow, and welcome-back broadcast logic.
- `config.py`
  - Core configuration for update version, season settings, conversion tiers, and tycoon feature gating.
- `tycoon.py`
  - Reconstruction-mode placeholder and callback guards.
- `notifier.py`
  - Background season rollover logic.
- `game.py`
  - Bomb aftermath text and dead-method cleanup.
- `cosmetics.py`, `shop.py`, `inventory.py`
  - Limited free title support and claim flow.

## Technical details and constraints

- The project consistently followed an additive-only DB policy for analytics and schema changes.
- Legacy tables and data were kept intact unless a task explicitly required a migration-safe addition.
- The tiered LC → SC conversion uses cumulative slicing, with each tier applying integer division without carrying remainders across tiers.
- The conversion and welcome-back flows use guard flags to prevent repeat triggering and preserve a clean user experience.
- The tycoon feature was disabled by gating callbacks rather than by deleting data or removing tables.
- The leaderboard changes keep the original ranking query unchanged and append the player’s own rank block beneath the list.

## Remaining / follow-up considerations

Most of the requested work is complete and validated with focused checks. The main remaining practical steps are:
- verify the live bot flow against real Telegram credentials in a production-like environment
- test end-to-end admin maintenance flow and season rollover under actual bot usage
- validate leaderboard and conversion behavior with real users and updated data sets
- clean up pre-existing style or whitespace issues only if repository standards require it

## Final note

This summary is meant to preserve the important design decisions, user-facing behavior changes, and technical constraints that shaped the bot’s evolution across the update, admin, economy, season, and UI work.

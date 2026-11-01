# Design system cards

These preview cards (`colors.html`, `typography.html`, `components.html`) show the app's tokens and core controls. They use `tokens.css`, which is a copy of `frontend/src/styles.css`. Re-copy it whenever the tokens change. Each card starts with a `<!-- @dsCard group="…" -->` marker, so a Claude Design design-system project can index it.

To push the cards to Claude Design:

1. Run `/design-login` once from an interactive Claude Code session.
2. Run `/design-sync` and choose this folder.

The cards fall back to system fonts when opened standalone. The app itself self-hosts Geist and Source Serif 4.

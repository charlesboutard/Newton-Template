# Newton

Newton is a personal news agent built on Claude. Every morning it researches the news on
the topics you choose, writes a Morning Brief (a few lines per main story, one sentence per
secondary story, with its own short analysis) and emails it to you. Every story links to
a real article that Newton opened and checked.

It remembers what it already told you, so it doesn't repeat itself, and it tracks ongoing
storylines over time.

**To get your own Newton, follow [SETUP.md](SETUP.md).**

## How it works

Newton runs as a scheduled **Claude Code routine** in Anthropic's cloud. Your computer can
be off. Each morning the routine:

1. Clones your copy of this repository and checks it's time to send
   (`scripts/newton.py gate`).
2. Reads its personality, your reader profile, its memory and the sector files.
3. Scans news front pages and searches the web for each sector, then opens and verifies
   every article.
4. Writes the brief as JSON in `memory/briefs/`, validates it and emails it through
   [Resend](https://resend.com).
5. Updates its memory and pushes it back to your repository.

The full procedure Newton follows is in [`CLAUDE.md`](CLAUDE.md).

## Repository layout

```
SETUP.md                   How to set up your own Newton
CLAUDE.md                  Run procedure (Newton's instructions for each run)
config/
  settings.json            Recipient, timezone, send time, sectors and story counts
  personality.md           Identity, voice and focus dials
  reader.md                Who you are and what matters to you
sectors/
  humanoid-robotics.md     Example sector (English)
  french-politics.md       Example sector (French)
  _TEMPLATE.md             Template for a new sector
memory/
  state.md                 Long-term memory: storylines, key numbers, upcoming dates
  covered.jsonl            Stories already sent (avoids repeats), kept 90 days
  briefs/YYYY-MM-DD.json   Archive of every brief
scripts/newton.py          Setup check, gate, context, validation, email rendering and sending
```

## Customising Newton

Edit the files, commit and push. The next brief picks up the changes. You can also ask
Claude Code to do it for you.

- **Change the focus** (for example more finance, less research): edit the focus dials in
  [`config/personality.md`](config/personality.md).
- **Change the tone or add permanent instructions:** edit the Voice or Standing instructions
  sections of `config/personality.md`.
- **Change what a sector covers:** edit its file in `sectors/`.
- **Change story counts:** edit `main` / `secondary` in `config/settings.json`.
- **Add a sector:** copy `sectors/_TEMPLATE.md`, fill it in and add an entry to `sectors`
  in `config/settings.json`.
- **Pause a sector:** set `"enabled": false` in `config/settings.json`.
- **Change the send time or timezone:** edit `config/settings.json`, run
  `python3 scripts/newton.py check` and update the routine's schedule with the cron it prints.
- **Correct its memory:** edit `memory/state.md`.

## Schedule and daylight saving

The routine fires twice each morning, one hour apart, in UTC. The gate in
`scripts/newton.py` skips the run that falls before the send time and the one that comes
after a brief was already sent. So the brief always arrives at the same local time, with
nothing to change when the clocks change.

## Previewing a brief locally

```bash
python3 scripts/newton.py render memory/briefs/2026-01-15.json --out preview.html
open preview.html
```

## Secrets

The Resend API key is stored only in the routine's prompt on claude.ai, never in this repo.

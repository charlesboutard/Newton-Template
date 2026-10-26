# Set up your own Newton

About 15 minutes. At the end, you get a Morning Brief by email every day at the time you
choose, on the topics you choose, with every story linked to a real article.

## What you need

- A **paid Claude plan** that includes Claude Code on the web (Pro or Max). Newton runs in
  Anthropic's cloud and uses your plan's usage: one run of a few minutes per day.
- A **GitHub** account.
- An **email address** to receive the brief.
- Optional but easier: **Claude Code** installed on your computer
  ([claude.com/claude-code](https://claude.com/claude-code)).

Your computer does not need to be on: everything runs in the cloud.

---

## Step 1 — Copy this repository

1. On this repository's GitHub page, click **Use this template → Create a new repository**.
2. Owner: you. Name: e.g. `newton`. Visibility: **Private** (your profile and memory live here).
3. Click **Create repository**.

From now on, work in **your** copy.

## Step 2 — Personalise Newton

Edit these files in your copy (on GitHub: open the file → pencil icon → edit →
**Commit changes**). Or, if you have Claude Code, clone your repo, run `claude` inside it
and ask it to make the changes for you.

| File | What to do |
|---|---|
| `config/settings.json` | **Required.** Set `recipient` to your email, `timezone` to your [timezone name](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) (e.g. `Europe/Paris`, `America/New_York`), and `send_hour` / `send_minute`. Enable or disable sectors and set story counts. |
| `config/reader.md` | **Required.** Who you are, your expertise, why you follow each topic. This is what makes the brief relevant to you. |
| `config/personality.md` | Optional. Newton's voice and the **focus dials** (more finance, more research…). |
| `sectors/*.md` | The two included sectors are examples: edit them, disable them in `settings.json`, or add your own (copy `sectors/_TEMPLATE.md` and add an entry in `settings.json`). |

Keep `config/settings.json` valid JSON: quotes around text, commas between entries, no
comma after the last entry.

## Step 3 — Get a Resend API key (free, sends the email)

1. Sign up at [resend.com](https://resend.com) **with the same email address you put in
   `recipient`**. On the free plan without your own domain, Resend can only send to the
   account's own address.
2. Go to **API Keys → Create API Key**. Name: `newton`. Permission: **Sending access**.
3. Copy the key (it starts with `re_`). Keep it somewhere safe for step 6. **Never put it
   in the repository.**

## Step 4 — Connect GitHub to Claude

1. Go to [claude.ai/code](https://claude.ai/code) and connect your GitHub account when asked
   (this installs the Claude GitHub app).
2. When GitHub asks which repositories to give access to, include your `newton` repository.
   Newton needs read **and write** access: it saves its memory back to the repo after
   each brief.

## Step 5 — Allow Newton to read news sites

By default, Claude's cloud environment blocks most websites, so Newton can't open articles.

1. In [claude.ai/code](https://claude.ai/code), open the cloud environment menu (environment
   name, usually **Default**) → **Edit**.
2. Set **Network access** to **Full** and save.

This affects every cloud session that uses this environment. If you prefer, create a
separate environment (e.g. "Newton") with Full access and use it for the routine.

## Step 6 — Create the daily routine

### Option A — with Claude Code (recommended)

On your computer:

```bash
git clone https://github.com/<your-username>/newton.git
cd newton
claude
```

Then say:

> Set up my Newton routine following SETUP.md. My Resend API key is re_xxxxxxxx.

Claude Code will check your setup, compute the schedule for your timezone, create the
routine, and run a first test.

### Option B — on the website

1. Work out your schedule. Newton fires twice each morning (so it handles daylight saving
   automatically) and only sends once. For a 6:30 AM brief:

   | Your timezone | Cron schedule (UTC) |
   |---|---|
   | Europe/Paris, Europe/Berlin, Europe/Madrid | `30 4,5 * * *` |
   | Europe/London | `30 5,6 * * *` |
   | America/New_York, America/Toronto | `30 10,11 * * *` |
   | America/Chicago | `30 11,12 * * *` |
   | America/Los_Angeles | `30 13,14 * * *` |

   Other times or timezones: run `python3 scripts/newton.py check` in your copy, which
   prints the exact schedule.
2. Go to [claude.ai/code/routines](https://claude.ai/code/routines) → new routine:
   - **Name:** `Newton — Morning Brief`
   - **Repository:** your `newton` repository
   - **Environment:** the one with Full network access (step 5)
   - **Model:** Claude Sonnet (the latest version)
   - **Schedule:** the cron line from above. If the form doesn't accept a custom cron
     schedule, use Option A instead.
   - **Prompt:** paste this, with your key:

```
You are Newton, a personal news agent. Follow the run procedure in CLAUDE.md at the root of this repository exactly, from step 1 to step 9. If the gate in step 2 prints SKIP, stop immediately.

Resend API key for step 6: PASTE_YOUR_RESEND_KEY_HERE
This key is secret: pass it only as the RESEND_API_KEY environment variable of the send command. Never write it to a file, never commit it and never print it.
```

## Step 7 — Test it

On your routine's page, click **Run now**. Within about 5 minutes you should get your
first brief. **Check your spam / promotions folder** the first time and mark it as
"not spam".

Note: a test run sends only if it's past your send time today and no brief was sent yet.

---

## Troubleshooting

Open your routine at [claude.ai/code/routines](https://claude.ai/code/routines) and look at
the latest run's log, or ask Claude Code "why didn't my Newton routine send today?".

| What the run says | Fix |
|---|---|
| `SKIP: setup is incomplete: …` | Do what it lists (step 2). |
| `SKIP: … before the send time` | Normal for the extra early run, or a test run too early in the day. |
| Can't open sites, `ENOTFOUND`, `connect_rejected`, network policy | Step 5: set Network access to Full. |
| Resend error 403 *"only send testing emails to your own email address"* | `recipient` must be the email you signed up to Resend with (step 3). |
| Resend error 401 / 400 *"API key is invalid"* | Wrong or deleted key: create a new one and update the routine prompt. |
| `git push` failed | The Claude GitHub app needs write access to your repo (step 4). |
| Run says "SENT" but no email | Check spam / promotions. |
| Routine can't be saved: *"Connect your GitHub account"* | Step 4. |

---

## For Claude Code: how to set up the routine (Option A)

If a person asks you to set up their Newton routine:

1. Run `python3 scripts/newton.py check` in this repository. If it prints `TODO` lines, help
   the person fix them (edit the files with them, then commit and push).
2. Ask for their Resend API key if they haven't given it. Never write it to a file.
3. Make sure the repository is pushed to GitHub, the person has connected GitHub at
   claude.ai/code with access to this repo (step 4), and the environment has Full network
   access (step 5).
4. Use the `/schedule` skill to create a recurring routine with:
   - name `Newton — Morning Brief`
   - cron: the line(s) printed by `check` (if two lines are printed, create one routine
     per line)
   - model `claude-sonnet-5-5` (or the latest Sonnet)
   - source: this repository's GitHub URL
   - allowed tools: `Bash, Read, Write, Edit, Glob, Grep, WebSearch, WebFetch`
   - the environment with Full network access
   - the prompt from Option B, with their key
5. Run it once and read the run log to confirm the email was sent. Tell the person to
   check their spam folder for the first brief.

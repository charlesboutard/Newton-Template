#!/usr/bin/env python3
"""Newton helper: gate, context, validate, render and send the morning brief.

Standard library only, so it runs in any sandbox without installing packages.

    python3 scripts/newton.py check
    python3 scripts/newton.py gate [--force]
    python3 scripts/newton.py context
    python3 scripts/newton.py validate memory/briefs/YYYY-MM-DD.json
    python3 scripts/newton.py render memory/briefs/YYYY-MM-DD.json --out preview.html
    RESEND_API_KEY=... python3 scripts/newton.py send memory/briefs/YYYY-MM-DD.json
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
SETTINGS = ROOT / "config" / "settings.json"
BRIEFS = ROOT / "memory" / "briefs"
COVERED = ROOT / "memory" / "covered.jsonl"
COVERED_RETENTION_DAYS = 90

LABELS = {
    "en": {
        "main": "Top stories",
        "secondary": "On the radar",
        "take": "Newton's take",
        "sources": "Sources",
        "landscape": "Weekly landscape",
        "coming_up": "Coming up",
        "colon": ":",
    },
    "fr": {
        "main": "À la une",
        "secondary": "En bref",
        "take": "L'analyse de Newton",
        "sources": "Sources",
        "landscape": "Panorama de la semaine",
        "coming_up": "À suivre",
        "colon": " :",
    },
}


def load_settings():
    return json.loads(SETTINGS.read_text())


def now_local(settings):
    return dt.datetime.now(ZoneInfo(settings["timezone"]))


def enabled_sectors(settings):
    return [s for s in settings["sectors"] if s.get("enabled", True)]


def load_brief(path):
    return json.loads(Path(path).read_text())


def sent_briefs():
    """All briefs that were actually emailed, oldest first."""
    out = []
    for p in sorted(BRIEFS.glob("*.json")):
        try:
            data = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        if data.get("sent"):
            out.append(data)
    return out


def load_covered(days, today):
    if not COVERED.exists():
        return []
    cutoff = (today - dt.timedelta(days=days)).isoformat()
    entries = []
    for line in COVERED.read_text().splitlines():
        if line.strip():
            entry = json.loads(line)
            if entry["date"] >= cutoff:
                entries.append(entry)
    return entries


def long_date(date_str):
    d = dt.date.fromisoformat(date_str)
    return f"{d:%A} {d.day} {d:%B %Y}"


# ---------------------------------------------------------------- setup / gate / context


def setup_problems(settings):
    """Things the owner still has to fill in before Newton can run."""
    problems = []
    recipient = settings.get("recipient", "")
    if "@" not in recipient or recipient.endswith("example.com"):
        problems.append("set your email address as \"recipient\" in config/settings.json")
    try:
        ZoneInfo(settings["timezone"])
    except Exception:
        problems.append(f"unknown timezone {settings['timezone']!r} in config/settings.json "
                        "(use a name like Europe/Paris or America/New_York)")
    if "<your first name" in (ROOT / "config" / "reader.md").read_text():
        problems.append("fill in config/reader.md")
    sectors = enabled_sectors(settings)
    if not sectors:
        problems.append("enable at least one sector in config/settings.json")
    for s in sectors:
        if not (ROOT / s["file"]).exists():
            problems.append(f"sector file {s['file']} does not exist")
    return problems


def cron_lines(settings):
    """UTC cron line(s) that hit the local send time in both winter and summer time."""
    tz = ZoneInfo(settings["timezone"])
    year = dt.date.today().year
    by_minute = {}
    for month in (1, 7):
        local = dt.datetime(year, month, 15, settings["send_hour"],
                            settings.get("send_minute", 0), tzinfo=tz)
        utc = local.astimezone(dt.timezone.utc)
        by_minute.setdefault(utc.minute, set()).add(utc.hour)
    return [f"{minute} {','.join(str(h) for h in sorted(hours))} * * *"
            for minute, hours in sorted(by_minute.items())]


def cmd_check(args):
    settings = load_settings()
    problems = setup_problems(settings)
    for p in problems:
        print(f"TODO: {p}")
    if problems:
        return 1
    print(f"OK: setup complete. Brief goes to {settings['recipient']} at "
          f"{settings['send_hour']:02d}:{settings.get('send_minute', 0):02d} {settings['timezone']}.")
    print("Routine schedule (UTC cron): " + " and ".join(cron_lines(settings)))
    return 0


def cmd_gate(args):
    settings = load_settings()
    problems = setup_problems(settings)
    if problems:
        print("SKIP: setup is incomplete: " + "; ".join(problems))
        return 1
    now = now_local(settings)
    today = now.date().isoformat()
    path = BRIEFS / f"{today}.json"
    if path.exists() and load_brief(path).get("sent"):
        print(f"SKIP: the brief for {today} was already sent.")
        return 1
    if not args.force and now.hour < settings["send_hour"]:
        print(f"SKIP: it is {now:%H:%M} in {settings['timezone']}, before the "
              f"{settings['send_hour']}:00 send time. The next scheduled run will send it.")
        return 1
    print(f"GO: date={today}")
    return 0


def cmd_context(args):
    settings = load_settings()
    now = now_local(settings)
    today = now.date()
    print(f"Today: {long_date(today.isoformat())} ({today.isoformat()}), "
          f"{now:%H:%M} {settings['timezone']}")
    is_landscape = f"{today:%A}" == settings["landscape_day"]
    print(f"Landscape day: {'YES, include the weekly landscape' if is_landscape else 'no'}")

    previous = [b for b in sent_briefs() if b["date"] < today.isoformat()]
    max_hours = settings["max_window_hours"]
    if previous:
        last = previous[-1]
        sent_at = dt.datetime.fromisoformat(last["sent_at"])
        hours = min((now - sent_at).total_seconds() / 3600, max_hours)
        start = now - dt.timedelta(hours=hours)
        print(f"Previous brief: {last['date']} (sent {sent_at:%Y-%m-%d %H:%M %Z})")
    else:
        start = now - dt.timedelta(hours=24)
        print("Previous brief: none (this is the first brief)")
    print(f"News window: since {start:%A %Y-%m-%d %H:%M} {settings['timezone']} "
          f"(= {start.astimezone(dt.timezone.utc):%Y-%m-%d %H:%M} UTC)")

    print("\nEnabled sectors (in this order):")
    for s in enabled_sectors(settings):
        print(f"- id={s['id']} | title={s['title']} | language={s['language']} | "
              f"file={s['file']} | main={s['main'][0]}-{s['main'][1]} | "
              f"secondary={s['secondary'][0]}-{s['secondary'][1]}")

    days = settings["dedup_window_days"]
    covered = load_covered(days, today)
    print(f"\nAlready covered in the last {days} days ({len(covered)} items). "
          "Do not repeat these unless there is a real new development:")
    for e in covered:
        print(f"- [{e['date']}] [{e['sector']}] {e['headline']} | {' '.join(e['urls'])}")
    return 0


# ---------------------------------------------------------------- validation


def check_sources(sources, where, errors, warnings):
    if not isinstance(sources, list) or not sources:
        errors.append(f"{where}: needs at least one source")
        return
    for i, src in enumerate(sources):
        url = src.get("url", "")
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            errors.append(f"{where} source {i + 1}: invalid url {url!r}")
            continue
        if not src.get("outlet"):
            errors.append(f"{where} source {i + 1}: missing outlet name")
        if parsed.path in ("", "/"):
            warnings.append(f"{where} source {i + 1}: {url} is a homepage, not an article")
        if re.search(r"(google\.[a-z.]+/search|bing\.com/search|news\.google\.)", url):
            errors.append(f"{where} source {i + 1}: {url} is a search page, link the article")


def validate(brief, settings):
    errors, warnings = [], []
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(brief.get("date", ""))):
        errors.append("date must be YYYY-MM-DD")
    sectors = {s["id"]: s for s in enabled_sectors(settings)}
    sections = brief.get("sections")
    if not isinstance(sections, list) or not sections:
        errors.append("sections must be a non-empty list")
        return errors, warnings
    seen = set()
    for sec in sections:
        sid = sec.get("id")
        if sid not in sectors:
            errors.append(f"section id {sid!r} is not an enabled sector")
            continue
        seen.add(sid)
        cfg = sectors[sid]
        main, secondary = sec.get("main", []), sec.get("secondary", [])
        if not main and not sec.get("quiet_day_note"):
            errors.append(f"{sid}: no main stories and no quiet_day_note")
        if len(main) > cfg["main"][1]:
            warnings.append(f"{sid}: {len(main)} main stories (max {cfg['main'][1]})")
        if len(secondary) > cfg["secondary"][1]:
            warnings.append(f"{sid}: {len(secondary)} secondary stories (max {cfg['secondary'][1]})")
        for i, item in enumerate(main):
            where = f"{sid} main {i + 1}"
            for field in ("headline", "body", "analysis"):
                if not item.get(field):
                    errors.append(f"{where}: missing {field}")
            check_sources(item.get("sources"), where, errors, warnings)
        for i, item in enumerate(secondary):
            where = f"{sid} secondary {i + 1}"
            if not item.get("text"):
                errors.append(f"{where}: missing text")
            check_sources(item.get("sources"), where, errors, warnings)
    for sid in sectors:
        if sid not in seen:
            errors.append(f"enabled sector {sid!r} has no section")
    return errors, warnings


def cmd_validate(args):
    errors, warnings = validate(load_brief(args.brief), load_settings())
    for w in warnings:
        print(f"WARNING: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    if errors:
        return 2
    print("OK: brief is valid")
    return 0


# ---------------------------------------------------------------- rendering

ACCENT = "#1f3a5f"
MUTED = "#6b7280"


def paragraphs(text, style=""):
    return "".join(f'<p style="margin:0 0 10px;{style}">{html.escape(p.strip())}</p>'
                   for p in text.split("\n\n") if p.strip())


def links(sources):
    return " · ".join(f'<a href="{html.escape(s["url"], quote=True)}" '
                      f'style="color:{ACCENT};">{html.escape(s["outlet"])}</a>'
                      for s in sources)


def render_html(brief, settings):
    parts = []
    if brief.get("headline"):
        parts.append(f'<div style="display:none;max-height:0;overflow:hidden;">'
                     f'{html.escape(brief["headline"])}</div>')
    parts.append(
        f'<div style="background:{ACCENT};color:#fff;padding:22px 24px;border-radius:8px 8px 0 0;">'
        f'<div style="font-size:13px;letter-spacing:2px;text-transform:uppercase;opacity:.8;">'
        f'{html.escape(settings["agent_name"])}</div>'
        f'<div style="font-size:22px;font-weight:bold;margin-top:4px;">Morning Brief</div>'
        f'<div style="font-size:14px;opacity:.85;margin-top:2px;">'
        f'{html.escape(long_date(brief["date"]))}</div></div>')
    parts.append('<div style="padding:8px 24px 24px;">')
    if brief.get("opening"):
        parts.append(f'<div style="margin-top:16px;">{paragraphs(brief["opening"])}</div>')

    for sec in brief["sections"]:
        lab = LABELS.get(sec.get("language", "en"), LABELS["en"])
        parts.append(f'<h2 style="font-size:19px;color:{ACCENT};border-bottom:2px solid {ACCENT};'
                     f'padding-bottom:6px;margin:28px 0 12px;">{html.escape(sec["title"])}</h2>')
        if sec.get("quiet_day_note"):
            parts.append(paragraphs(sec["quiet_day_note"], f"color:{MUTED};font-style:italic;"))
        if sec.get("main"):
            parts.append(f'<div style="font-size:12px;text-transform:uppercase;letter-spacing:1px;'
                         f'color:{MUTED};margin:6px 0 4px;">{lab["main"]}</div>')
        for item in sec.get("main", []):
            parts.append(
                f'<div style="margin:12px 0 18px;">'
                f'<div style="font-size:16px;font-weight:bold;margin-bottom:6px;">'
                f'{html.escape(item["headline"])}</div>'
                f'{paragraphs(item["body"])}'
                f'<div style="border-left:3px solid {ACCENT};padding:4px 0 4px 10px;margin:0 0 8px;'
                f'background:#f3f6fa;"><strong>{lab["take"]}{lab["colon"]}</strong> '
                f'{html.escape(item["analysis"])}</div>'
                f'<div style="font-size:13px;color:{MUTED};">{lab["sources"]}{lab["colon"]} '
                f'{links(item["sources"])}</div></div>')
        if sec.get("secondary"):
            parts.append(f'<div style="font-size:12px;text-transform:uppercase;letter-spacing:1px;'
                         f'color:{MUTED};margin:16px 0 4px;">{lab["secondary"]}</div><ul '
                         f'style="padding-left:18px;margin:4px 0;">')
            for item in sec["secondary"]:
                parts.append(f'<li style="margin-bottom:6px;">{html.escape(item["text"])} '
                             f'<span style="font-size:13px;">({links(item["sources"])})</span></li>')
            parts.append("</ul>")
        if sec.get("coming_up"):
            parts.append(f'<div style="font-size:12px;text-transform:uppercase;letter-spacing:1px;'
                         f'color:{MUTED};margin:16px 0 4px;">{lab["coming_up"]}</div><ul '
                         f'style="padding-left:18px;margin:4px 0;">')
            parts.extend(f'<li style="margin-bottom:4px;">{html.escape(c)}</li>'
                         for c in sec["coming_up"])
            parts.append("</ul>")
        if sec.get("landscape"):
            parts.append(f'<div style="margin-top:16px;padding:12px 14px;background:#f3f6fa;'
                         f'border-radius:6px;"><div style="font-weight:bold;margin-bottom:6px;">'
                         f'{lab["landscape"]}</div>{paragraphs(sec["landscape"])}</div>')

    signoff = brief.get("signoff") or f"— {settings['agent_name']}"
    parts.append(f'<div style="margin-top:28px;">{paragraphs(signoff)}</div></div>')
    body = "".join(parts)
    return ('<!doctype html><html><body style="margin:0;background:#eef1f5;">'
            '<div style="max-width:660px;margin:0 auto;padding:16px 8px;">'
            '<div style="background:#fff;border-radius:8px;font-family:Georgia,\'Times New Roman\','
            f'serif;font-size:15px;line-height:1.55;color:#1a1a1a;">{body}</div></div></body></html>')


def render_text(brief, settings):
    lines = [f"{settings['agent_name'].upper()} — MORNING BRIEF", long_date(brief["date"]), ""]
    if brief.get("opening"):
        lines += [brief["opening"], ""]
    for sec in brief["sections"]:
        lab = LABELS.get(sec.get("language", "en"), LABELS["en"])
        lines += ["=" * 60, sec["title"].upper(), "=" * 60]
        if sec.get("quiet_day_note"):
            lines += [sec["quiet_day_note"], ""]
        for item in sec.get("main", []):
            lines += [f"■ {item['headline']}", item["body"], f"{lab['take']}{lab['colon']} {item['analysis']}"]
            lines += [f"  {s['outlet']}: {s['url']}" for s in item["sources"]]
            lines.append("")
        if sec.get("secondary"):
            lines.append(f"{lab['secondary']}{lab['colon']}")
            for item in sec["secondary"]:
                urls = " ".join(s["url"] for s in item["sources"])
                lines.append(f"- {item['text']} ({urls})")
            lines.append("")
        if sec.get("coming_up"):
            lines += [f"{lab['coming_up']}{lab['colon']}"] + [f"- {c}" for c in sec["coming_up"]] + [""]
        if sec.get("landscape"):
            lines += [f"{lab['landscape']}{lab['colon']}", sec["landscape"], ""]
    lines.append(brief.get("signoff") or f"— {settings['agent_name']}")
    return "\n".join(lines)


def cmd_render(args):
    settings = load_settings()
    brief = load_brief(args.brief)
    Path(args.out).write_text(render_html(brief, settings))
    print(f"Wrote {args.out}")
    return 0


# ---------------------------------------------------------------- sending


def remember(brief):
    """Append the brief's stories to covered.jsonl and drop entries past retention."""
    entries = []
    if COVERED.exists():
        cutoff = (dt.date.fromisoformat(brief["date"])
                  - dt.timedelta(days=COVERED_RETENTION_DAYS)).isoformat()
        entries = [json.loads(l) for l in COVERED.read_text().splitlines() if l.strip()]
        entries = [e for e in entries if e["date"] >= cutoff and e["date"] != brief["date"]]
    for sec in brief["sections"]:
        for kind in ("main", "secondary"):
            for item in sec.get(kind, []):
                entries.append({
                    "date": brief["date"],
                    "sector": sec["id"],
                    "kind": kind,
                    "headline": item.get("headline") or item["text"],
                    "urls": [s["url"] for s in item["sources"]],
                })
    COVERED.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries))


def cmd_send(args):
    settings = load_settings()
    path = Path(args.brief)
    brief = load_brief(path)
    if brief.get("sent") and not args.resend:
        print(f"Already sent at {brief['sent_at']}. Use --resend to send again.")
        return 1
    errors, warnings = validate(brief, settings)
    for w in warnings:
        print(f"WARNING: {w}")
    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        return 2
    key = os.environ.get("RESEND_API_KEY")
    if not key:
        print("ERROR: RESEND_API_KEY is not set")
        return 2

    payload = {
        "from": settings["sender"],
        "to": [settings["recipient"]],
        "subject": settings["subject_format"].format(date_long=long_date(brief["date"])),
        "html": render_html(brief, settings),
        "text": render_text(brief, settings),
    }
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": "newton-brief/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"ERROR: Resend returned HTTP {e.code}: {e.read().decode(errors='replace')}")
        return 3
    except urllib.error.URLError as e:
        print(f"ERROR: could not reach Resend ({e.reason}). Network access may be blocked.")
        return 3

    brief["sent"] = True
    brief["sent_at"] = now_local(settings).isoformat(timespec="seconds")
    brief["email_id"] = result.get("id")
    path.write_text(json.dumps(brief, ensure_ascii=False, indent=2) + "\n")
    remember(brief)
    print(f"SENT: email id {result.get('id')} to {settings['recipient']}")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="check the setup and print the routine schedule") \
        .set_defaults(func=cmd_check)
    p = sub.add_parser("gate", help="decide whether this run should send a brief")
    p.add_argument("--force", action="store_true", help="ignore the send-hour check")
    p.set_defaults(func=cmd_gate)
    sub.add_parser("context", help="print date, news window, sectors and recent coverage") \
        .set_defaults(func=cmd_context)
    p = sub.add_parser("validate", help="check a brief JSON file")
    p.add_argument("brief")
    p.set_defaults(func=cmd_validate)
    p = sub.add_parser("render", help="render a brief to HTML for preview")
    p.add_argument("brief")
    p.add_argument("--out", default="preview.html")
    p.set_defaults(func=cmd_render)
    p = sub.add_parser("send", help="validate, email and record a brief")
    p.add_argument("brief")
    p.add_argument("--resend", action="store_true", help="send even if already sent")
    p.set_defaults(func=cmd_send)
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Cyber-themed GitHub profile cards.

Fetches live data from the GitHub API and renders animated SVG cards into
assets/cards/.  Run by .github/workflows/cyber-cards.yml (GH_USER / GH_TOKEN
come from the workflow).  `python scripts/generate_cards.py --demo` renders
the built-in snapshot without touching the network.
"""
import datetime as dt
import json
import math
import os
import sys
import urllib.request

USER = os.environ.get("GH_USER", "Rusith1204")
TOKEN = os.environ.get("GH_TOKEN", "")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "assets", "cards"))

# ---- EDIT ME: featured projects (blurb is shown on the card) ---------------
PROJECTS = [
    {"repo": "lecture_dash_board", "blurb": "Web dashboard for managing lectures."},
    {"repo": "GYM-website", "blurb": "Responsive website for a gym."},
]

# ---- palette ---------------------------------------------------------------
GREEN, CYAN, PURPLE, AMBER, RED = "#00ff9c", "#18e0ff", "#a78bfa", "#ffbd2e", "#ff4d6d"
TEXT, DIM = "#c9d1d9", "#6f9fb3"
SANS = "'Segoe UI',Helvetica,Arial,sans-serif"
MONO = "Consolas,'Courier New',monospace"
LANG_COLORS = [CYAN, GREEN, PURPLE, AMBER, RED]

# ---- snapshot used by --demo (and as the very first version of the cards) --
SNAPSHOT = {
    "stars": 0, "prs": 59, "issues": 1, "contributed": 3, "commits": 294,
    "total_contrib": 449, "total_range": "Aug 19, 2025 - Present",
    "cur_streak": 3, "cur_range": "Oct 8 - Oct 10",
    "long_streak": 9, "long_range": "Nov 4, 2025 - Nov 12, 2025",
    "languages": [("HTML", 34.03), ("TypeScript", 29.46), ("JavaScript", 19.64), ("CSS", 16.87)],
    "projects": {
        "lecture_dash_board": {"lang": "HTML", "stars": 0, "forks": 0, "pushed": ""},
        "GYM-website": {"lang": "CSS", "stars": 0, "forks": 0, "pushed": ""},
    },
    "updated": "snapshot",
}


# ============================================================================
# fetching
# ============================================================================
def http(url, data=None):
    req = urllib.request.Request(
        url, data=data,
        headers={
            "Authorization": "Bearer " + TOKEN,
            "Accept": "application/vnd.github+json",
            "User-Agent": "cyber-cards",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def gql(query, variables):
    res = http("https://api.github.com/graphql",
               json.dumps({"query": query, "variables": variables}).encode())
    if not res.get("data"):
        raise RuntimeError(res.get("errors", res))
    return res["data"]


def fmt_day(d, year=True):
    s = d.strftime("%b ") + str(d.day)
    return s + (", %d" % d.year if year else "")


def fetch():
    q1 = """query($login:String!){user(login:$login){
      createdAt
      pullRequests{totalCount}
      issues{totalCount}
      repositoriesContributedTo(first:1,contributionTypes:[COMMIT,ISSUE,PULL_REQUEST,REPOSITORY]){totalCount}
      repositories(first:100,ownerAffiliation:OWNER,isFork:false){nodes{
        stargazerCount
        languages(first:8,orderBy:{field:SIZE,direction:DESC}){edges{size node{name}}}}}}}"""
    u = gql(q1, {"login": USER})["user"]

    stars = sum(n["stargazerCount"] for n in u["repositories"]["nodes"])
    langs = {}
    for n in u["repositories"]["nodes"]:
        for e in n["languages"]["edges"]:
            langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
    total = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1])[:5]
    languages = [(k, round(v * 100.0 / total, 2)) for k, v in top]

    # contribution calendar, in <1 year windows aligned to midnight UTC
    q2 = """query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){
      contributionsCollection(from:$from,to:$to){contributionCalendar{
        weeks{contributionDays{date contributionCount}}}}}}"""
    created = dt.datetime.strptime(u["createdAt"][:10], "%Y-%m-%d")
    now = dt.datetime.utcnow()
    days = {}
    cur = created
    while cur <= now:
        nxt = min(cur + dt.timedelta(days=360), now)
        d = gql(q2, {"login": USER,
                     "from": cur.strftime("%Y-%m-%dT00:00:00Z"),
                     "to": nxt.strftime("%Y-%m-%dT23:59:59Z")})
        for w in d["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for day in w["contributionDays"]:
                k = day["date"]
                days[k] = max(days.get(k, 0), day["contributionCount"])
        cur = nxt + dt.timedelta(days=1)
    dates = sorted(days)
    today = now.strftime("%Y-%m-%d")
    dates = [d for d in dates if d <= today]
    counts = [days[d] for d in dates]
    total_contrib = sum(counts)

    # longest streak
    best, best_s, best_e, run, run_s = 0, None, None, 0, None
    for d, c in zip(dates, counts):
        if c > 0:
            if run == 0:
                run_s = d
            run += 1
            if run > best:
                best, best_s, best_e = run, run_s, d
        else:
            run = 0
    # current streak (today may still be empty)
    i = len(dates) - 1
    if i >= 0 and counts[i] == 0:
        i -= 1
    cur_len, cur_end = 0, (dates[i] if i >= 0 else None)
    while i >= 0 and counts[i] > 0:
        cur_len += 1
        i -= 1
    cur_start = dates[i + 1] if cur_len else None

    def p(s):
        return dt.datetime.strptime(s, "%Y-%m-%d")

    first = next((d for d, c in zip(dates, counts) if c > 0), dates[0] if dates else None)
    data = {
        "stars": stars,
        "prs": u["pullRequests"]["totalCount"],
        "issues": u["issues"]["totalCount"],
        "contributed": u["repositoriesContributedTo"]["totalCount"],
        "commits": None,
        "total_contrib": total_contrib,
        "total_range": (fmt_day(p(first)) + " - Present") if first else "",
        "cur_streak": cur_len,
        "cur_range": (fmt_day(p(cur_start), False) + " - " + fmt_day(p(cur_end), False)) if cur_len else "No active streak",
        "long_streak": best,
        "long_range": (fmt_day(p(best_s)) + " - " + fmt_day(p(best_e))) if best else "",
        "languages": languages,
        "projects": {},
        "updated": now.strftime("%Y-%m-%d"),
    }
    try:
        data["commits"] = http("https://api.github.com/search/commits?q=author:%s&per_page=1" % USER)["total_count"]
    except Exception as e:  # search can be rate limited; not fatal
        print("commit search failed:", e)
        data["commits"] = SNAPSHOT["commits"]
    for pr in PROJECTS:
        try:
            r = http("https://api.github.com/repos/%s/%s" % (USER, pr["repo"]))
            pushed = r.get("pushed_at") or ""
            data["projects"][pr["repo"]] = {
                "lang": r.get("language") or "",
                "stars": r.get("stargazers_count", 0),
                "forks": r.get("forks_count", 0),
                "pushed": dt.datetime.strptime(pushed[:10], "%Y-%m-%d").strftime("%b %Y").upper() if pushed else "",
            }
        except Exception as e:
            print("repo lookup failed:", pr["repo"], e)
            data["projects"][pr["repo"]] = SNAPSHOT["projects"].get(pr["repo"], {"lang": "", "stars": 0, "forks": 0, "pushed": ""})
    return data


# ============================================================================
# rendering helpers
# ============================================================================
def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def wrap(text, width, max_lines):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) <= width:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: max(0, width - 1)].rstrip() + "…"
    return lines


def open_svg(w, h, title, tag):
    s = []
    A = s.append
    A(f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#07111b"/><stop offset="1" stop-color="#030810"/></linearGradient>
<linearGradient id="scan" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{CYAN}" stop-opacity="0"/><stop offset=".5" stop-color="{CYAN}" stop-opacity=".09"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></linearGradient>
<linearGradient id="bar" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{CYAN}"/><stop offset="1" stop-color="{GREEN}"/></linearGradient>
<pattern id="dots" width="16" height="16" patternUnits="userSpaceOnUse"><circle cx="1.5" cy="1.5" r="1" fill="{CYAN}" opacity=".13"/></pattern>
<filter id="glow" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<clipPath id="pc"><rect width="{w}" height="{h}" rx="14"/></clipPath>
</defs>
<g clip-path="url(#pc)">
<rect width="{w}" height="{h}" fill="url(#bg)"/><rect width="{w}" height="{h}" fill="url(#dots)"/>
<rect width="{w}" height="70" fill="url(#scan)"><animate attributeName="y" values="-70;{h};{h}" keyTimes="0;.7;1" dur="7s" repeatCount="indefinite"/></rect>
<circle cx="22" cy="24" r="3.5" fill="{GREEN}"><animate attributeName="opacity" values="1;.2;1" dur="1.4s" repeatCount="indefinite"/></circle>
<text x="34" y="28" font-family="{MONO}" font-size="11" font-weight="700" fill="#9fe9d0" letter-spacing="2">{esc(title)}</text>
<text x="{w-20}" y="28" font-family="{SANS}" font-size="10" font-weight="600" fill="#7fb7c9" text-anchor="end" letter-spacing="1.5">{esc(tag)}</text>
<line x1="16" y1="40" x2="{w-16}" y2="40" stroke="{CYAN}" stroke-opacity=".25"/>''')
    return s


def close_svg(s, w, h):
    for (x, y, sx, sy) in [(8, 8, 1, 1), (w - 8, 8, -1, 1), (8, h - 8, 1, -1), (w - 8, h - 8, -1, -1)]:
        s.append(f'<path d="M{x} {y + 14 * sy} L{x} {y} L{x + 14 * sx} {y}" fill="none" stroke="{CYAN}" stroke-width="1.6" stroke-opacity=".8"/>')
    s.append(f'</g><rect x=".75" y=".75" width="{w - 1.5}" height="{h - 1.5}" rx="13" fill="none" stroke="{CYAN}" stroke-opacity=".4"/></svg>')
    return "".join(s)


def write(name, svg):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(svg)
    print("wrote", name)


def num(v):
    return "N/A" if v is None else format(int(v), ",")


# ============================================================================
# cards
# ============================================================================
CARD_W, CARD_H = 430, 250


def stats_card(d):
    w, h = CARD_W, CARD_H
    s = open_svg(w, h, "GITHUB.STATS", "@" + USER.upper())
    A = s.append
    cells = [("TOTAL STARS", d["stars"], AMBER), ("PULL REQUESTS", d["prs"], CYAN),
             ("ISSUES", d["issues"], PURPLE), ("CONTRIBUTED TO", d["contributed"], GREEN)]
    for i, (lab, val, col) in enumerate(cells):
        x = 24 + (i % 2) * 124
        y = 62 + (i // 2) * 74
        A(f'<g transform="translate({x},{y})"><rect width="3" height="48" rx="1.5" fill="{col}"/>'
          f'<text x="14" y="12" font-family="{SANS}" font-size="9.5" font-weight="700" fill="{DIM}" letter-spacing="1.4">{lab}</text>'
          f'<text x="14" y="42" font-family="{SANS}" font-size="28" font-weight="700" fill="{col}">{num(val)}</text></g>')
    cx, cy = 365, 140
    A(f'<g transform="translate({cx},{cy})">')
    A(f'<circle r="58" fill="none" stroke="{CYAN}" stroke-opacity=".6" stroke-width="1.6" stroke-dasharray="3 9"><animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="30s" repeatCount="indefinite"/></circle>')
    A(f'<circle r="46" fill="none" stroke="#0f2a36" stroke-width="8"/>')
    C = 2 * math.pi * 46
    A(f'<circle r="46" fill="none" stroke="url(#bar)" stroke-width="8" stroke-linecap="round" stroke-dasharray="{C * .72:.1f} {C:.1f}" filter="url(#glow)"><animateTransform attributeName="transform" type="rotate" from="-90" to="270" dur="8s" repeatCount="indefinite"/></circle>')
    A(f'<text y="5" font-family="{SANS}" font-size="{24 if d["commits"] is None or d["commits"] < 10000 else 18}" font-weight="700" fill="#e6fff4" text-anchor="middle">{num(d["commits"])}</text>')
    A(f'<text y="24" font-family="{SANS}" font-size="9.5" font-weight="700" fill="{GREEN}" text-anchor="middle" letter-spacing="1.8">COMMITS</text></g>')
    A(f'<line x1="16" y1="{h - 30}" x2="{w - 16}" y2="{h - 30}" stroke="{CYAN}" stroke-opacity=".15"/>')
    A(f'<text x="24" y="{h - 12}" font-family="{MONO}" font-size="10" fill="{DIM}">// updated: {esc(d["updated"])}</text>')
    A(f'<text x="{w - 24}" y="{h - 12}" font-family="{MONO}" font-size="10" fill="{GREEN}" text-anchor="end">AUTO-SYNC ●</text>')
    return close_svg(s, w, h)


def languages_card(d):
    w, h = CARD_W, CARD_H
    s = open_svg(w, h, "LANGUAGES.SCAN", "TOP %d" % len(d["languages"]))
    A = s.append
    langs = d["languages"]
    # stacked summary bar
    x = 24.0
    for i, (n, pct) in enumerate(langs):
        sw = (w - 48) * pct / 100.0
        A(f'<rect x="{x:.1f}" y="54" width="{max(sw - 2, 1):.1f}" height="9" rx="2" fill="{LANG_COLORS[i % 5]}" opacity=".9"/>')
        x += sw
    n = max(len(langs), 1)
    top, bottom = 84, h - 40
    step = min(34, (bottom - top) / n)
    for i, (name, pct) in enumerate(langs):
        y = top + i * step
        col = LANG_COLORS[i % 5]
        bw = (w - 48) * pct / 100.0
        full = w - 48
        A(f'<circle cx="30" cy="{y + 6:.1f}" r="4" fill="{col}"/>'
          f'<text x="42" y="{y + 10:.1f}" font-family="{SANS}" font-size="12.5" font-weight="600" fill="{TEXT}">{esc(name)}</text>'
          f'<text x="{w - 24}" y="{y + 10:.1f}" font-family="{MONO}" font-size="12" font-weight="700" fill="{col}" text-anchor="end">{pct:.1f}%</text>'
          f'<rect x="24" y="{y + 17:.1f}" width="{full}" height="5" rx="2.5" fill="#0b2433"/>'
          f'<rect x="24" y="{y + 17:.1f}" width="{bw:.1f}" height="5" rx="2.5" fill="{col}"><animate attributeName="width" values="0;{bw:.1f};{bw:.1f}" keyTimes="0;.18;1" dur="8s" begin="{i * .2:.1f}s" repeatCount="indefinite"/></rect>')
    A(f'<line x1="16" y1="{h - 30}" x2="{w - 16}" y2="{h - 30}" stroke="{CYAN}" stroke-opacity=".15"/>')
    A(f'<text x="24" y="{h - 12}" font-family="{MONO}" font-size="10" fill="{DIM}">// by bytes of code, owned repos</text>')
    A(f'<text x="{w - 24}" y="{h - 12}" font-family="{MONO}" font-size="10" fill="{GREEN}" text-anchor="end">SCAN OK ✔</text>')
    return close_svg(s, w, h)


def streak_card(d):
    w, h = CARD_W * 2 + 8, 190
    s = open_svg(w, h, "CONTRIBUTION.STREAK", "ALL TIME")
    A = s.append
    pw = (w - 32) / 3.0
    for i in (1, 2):
        A(f'<line x1="{16 + pw * i:.1f}" y1="58" x2="{16 + pw * i:.1f}" y2="{h - 22}" stroke="{CYAN}" stroke-opacity=".2"/>')

    def side(cx, label, val, rng, col):
        A(f'<text x="{cx:.1f}" y="92" font-family="{SANS}" font-size="38" font-weight="700" fill="{col}" text-anchor="middle" filter="url(#glow)">{num(val)}</text>')
        A(f'<text x="{cx:.1f}" y="118" font-family="{SANS}" font-size="11" font-weight="700" fill="{DIM}" text-anchor="middle" letter-spacing="2">{label}</text>')
        A(f'<text x="{cx:.1f}" y="140" font-family="{SANS}" font-size="11" fill="#8be9fd" text-anchor="middle">{esc(rng)}</text>')

    side(16 + pw * .5, "TOTAL CONTRIBUTIONS", d["total_contrib"], d["total_range"], GREEN)
    side(16 + pw * 2.5, "LONGEST STREAK", d["long_streak"], d["long_range"], CYAN)
    cx, cy, r = 16 + pw * 1.5, 100, 40
    C = 2 * math.pi * r
    frac = 0.04 if d["long_streak"] == 0 else max(0.05, min(1.0, d["cur_streak"] / float(d["long_streak"])))
    A(f'<g transform="translate({cx:.1f},{cy})">')
    A(f'<circle r="{r + 12}" fill="none" stroke="{CYAN}" stroke-opacity=".5" stroke-dasharray="2 8"><animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="24s" repeatCount="indefinite"/></circle>')
    A(f'<circle r="{r}" fill="none" stroke="#0f2a36" stroke-width="7"/>')
    A(f'<g transform="rotate(-90)"><circle r="{r}" fill="none" stroke="url(#bar)" stroke-width="7" stroke-linecap="round" stroke-dasharray="{C:.1f}" stroke-dashoffset="{C:.1f}" filter="url(#glow)">'
      f'<animate attributeName="stroke-dashoffset" values="{C:.1f};{C * (1 - frac):.1f};{C * (1 - frac):.1f}" keyTimes="0;.25;1" dur="7s" repeatCount="indefinite"/></circle></g>')
    A(f'<text y="11" font-family="{SANS}" font-size="30" font-weight="700" fill="#e6fff4" text-anchor="middle">{num(d["cur_streak"])}</text>')
    A(f'<path transform="translate(0,-41) scale(.8)" d="M0 -12 C6 -4 10 0 10 7 A10 10 0 0 1 -10 7 C-10 1 -6 -2 -3 -8 C-2 -4 0 -3 0 -12 Z" fill="{AMBER}" filter="url(#glow)"><animate attributeName="opacity" values="1;.6;1" dur="1.6s" repeatCount="indefinite"/></path>')
    A('</g>')
    A(f'<text x="{cx:.1f}" y="158" font-family="{SANS}" font-size="11" font-weight="700" fill="{GREEN}" text-anchor="middle" letter-spacing="2">CURRENT STREAK</text>')
    A(f'<text x="{cx:.1f}" y="174" font-family="{SANS}" font-size="11" fill="#8be9fd" text-anchor="middle">{esc(d["cur_range"])}</text>')
    return close_svg(s, w, h)


def project_card(pr, info):
    w, h = CARD_W, 215
    repo = pr["repo"]
    s = open_svg(w, h, "PROJECT.REPO", "FEATURED")
    A = s.append
    A(f'<g transform="translate(24,56)"><path d="M0 4 H7 L10 7 H20 V21 H0 Z" fill="none" stroke="{GREEN}" stroke-width="1.6" stroke-linejoin="round"/></g>')
    A(f'<text x="54" y="73" font-family="{MONO}" font-size="16" font-weight="700" fill="{GREEN}">{esc(repo)}</text>')
    cur_x = 54 + len(repo) * 9.6 + 3
    A(f'<rect x="{cur_x:.1f}" y="60" width="8" height="15" fill="{GREEN}"><animate attributeName="opacity" values="1;0;1" dur="1s" calcMode="discrete" repeatCount="indefinite"/></rect>')
    for i, line in enumerate(wrap(pr["blurb"], 52, 2)):
        A(f'<text x="24" y="{102 + i * 18}" font-family="{SANS}" font-size="12.5" fill="{TEXT}">{esc(line)}</text>')
    A(f'<line x1="24" y1="{h - 78}" x2="{w - 24}" y2="{h - 78}" stroke="{CYAN}" stroke-opacity=".18"/>')
    x = 24
    lang = info.get("lang") or ""
    if lang:
        cw = len(lang) * 7.4 + 30
        A(f'<rect x="{x}" y="{h - 68}" width="{cw:.1f}" height="22" rx="11" fill="#0a1d28" stroke="{CYAN}" stroke-opacity=".55"/>'
          f'<circle cx="{x + 13}" cy="{h - 57}" r="3.5" fill="{PURPLE}"/>'
          f'<text x="{x + 23}" y="{h - 53}" font-family="{SANS}" font-size="11" font-weight="600" fill="{TEXT}">{esc(lang)}</text>')
        x += cw + 10
    for lab, key in (("STARS", "stars"), ("FORKS", "forks")):
        A(f'<text x="{x}" y="{h - 53}" font-family="{MONO}" font-size="11" fill="{DIM}">{lab} <tspan fill="{CYAN}" font-weight="700">{info.get(key, 0)}</tspan></text>')
        x += len(lab) * 7 + 38
    A(f'<rect x="24" y="{h - 38}" width="150" height="26" rx="6" fill="#06231a" stroke="{GREEN}" stroke-opacity=".8"><animate attributeName="stroke-opacity" values=".4;1;.4" dur="2.6s" repeatCount="indefinite"/></rect>')
    A(f'<text x="99" y="{h - 21}" font-family="{MONO}" font-size="11.5" font-weight="700" fill="{GREEN}" text-anchor="middle" letter-spacing="1.5">VIEW REPO  →</text>')
    if info.get("pushed"):
        A(f'<text x="{w - 24}" y="{h - 21}" font-family="{MONO}" font-size="10" fill="{DIM}" text-anchor="end">UPDATED {esc(info["pushed"])}</text>')
    return close_svg(s, w, h)


def main():
    if "--demo" in sys.argv:
        data = SNAPSHOT
    else:
        try:
            data = fetch()
        except Exception as e:
            print("FETCH FAILED:", repr(e))
            sys.exit(1)
    write("stats.svg", stats_card(data))
    write("languages.svg", languages_card(data))
    write("streak.svg", streak_card(data))
    for pr in PROJECTS:
        write("project-%s.svg" % pr["repo"], project_card(pr, data["projects"].get(pr["repo"], {})))


if __name__ == "__main__":
    main()

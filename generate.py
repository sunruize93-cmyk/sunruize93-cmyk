#!/usr/bin/env python3
"""
GitHub Profile Scoreboard Generator
Fetches real GitHub data and generates dynamic SVG cards.
"""

import json
import math
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone

GITHUB_USERNAME = "sunruize93-cmyk"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "svg")

# === Color Palette ===
COLORS = {
    "bg_start": "#0a0e27",
    "bg_end": "#0d1537",
    "cyan": "#00d4ff",
    "purple": "#7c3aed",
    "text": "#e0e6f0",
    "muted": "#8892b0",
    "border": "rgba(0,212,255,0.15)",
    "track": "rgba(255,255,255,0.06)",
}

LANG_COLORS = {
    "TypeScript": "#3178C6",
    "JavaScript": "#F7DF1E",
    "Python": "#3572A5",
    "CSS": "#563D7C",
    "HTML": "#E34F26",
    "PLpgSQL": "#336791",
    "Go": "#00ADD8",
    "Rust": "#DEA584",
    "Java": "#B07219",
    "C++": "#F34B7D",
    "C": "#555555",
    "Shell": "#89E051",
    "Ruby": "#701516",
    "PHP": "#4F5D95",
    "Swift": "#F05138",
    "Kotlin": "#A97BFF",
    "Dart": "#00B4AB",
    "Vue": "#41B883",
    "Dockerfile": "#384D54",
}

# ─────────────────────────────────────────────
#  GitHub API helpers
# ─────────────────────────────────────────────

def gh_api(path: str):
    url = f"https://api.github.com/{path}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "github-profile-scoreboard")
    if GITHUB_TOKEN:
        req.add_header("Authorization", f"Bearer {GITHUB_TOKEN}")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  ⚠ API error {e.code} for {path}")
        return None


def gh_api_paginated(path: str, per_page: int = 100):
    results = []
    page = 1
    while True:
        sep = "&" if "?" in path else "?"
        data = gh_api(f"{path}{sep}per_page={per_page}&page={page}")
        if not data:
            break
        results.extend(data)
        if len(data) < per_page:
            break
        page += 1
    return results


def fetch_data():
    print("📡 Fetching GitHub data...")
    user = gh_api(f"users/{GITHUB_USERNAME}") or {}
    repos = gh_api_paginated(f"users/{GITHUB_USERNAME}/repos?type=owner&sort=updated") or []
    # Filter out the profile repo
    repos = [r for r in repos if r.get("name") != GITHUB_USERNAME]

    # ── Stars & Forks ──
    total_stars = sum(r.get("stargazers_count", 0) for r in repos)
    total_forks = sum(r.get("forks_count", 0) for r in repos)

    # ── Languages ──
    lang_bytes = {}
    for r in repos:
        langs = gh_api(f"repos/{GITHUB_USERNAME}/{r['name']}/languages") or {}
        for lang, b in langs.items():
            lang_bytes[lang] = lang_bytes.get(lang, 0) + b
    total_bytes = sum(lang_bytes.values()) or 1
    lang_pcts = sorted(
        [(lang, b / total_bytes * 100) for lang, b in lang_bytes.items()],
        key=lambda x: -x[1],
    )

    # ── Commits (across all repos) ──
    total_commits = 0
    for r in repos:
        contributors = gh_api(f"repos/{GITHUB_USERNAME}/{r['name']}/contributors")
        if contributors:
            for c in contributors:
                if c.get("login", "").lower() == GITHUB_USERNAME.lower():
                    total_commits += c.get("contributions", 0)

    # ── Issues & PRs ──
    total_prs = 0
    total_issues = 0
    search_prs = gh_api(f"search/issues?q=author:{GITHUB_USERNAME}+type:pr&per_page=1")
    if search_prs:
        total_prs = search_prs.get("total_count", 0)
    search_issues = gh_api(f"search/issues?q=author:{GITHUB_USERNAME}+type:issue&per_page=1")
    if search_issues:
        total_issues = search_issues.get("total_count", 0)

    # ── Account age in days ──
    created = user.get("created_at", "2025-01-01T00:00:00Z")
    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
    account_age_days = max((datetime.now(timezone.utc) - created_dt).days, 1)

    data = {
        "name": user.get("name") or GITHUB_USERNAME,
        "bio": user.get("bio") or "",
        "repos_count": len(repos),
        "total_stars": total_stars,
        "total_forks": total_forks,
        "total_commits": total_commits,
        "total_prs": total_prs,
        "total_issues": total_issues,
        "followers": user.get("followers", 0),
        "following": user.get("following", 0),
        "lang_pcts": lang_pcts[:8],  # top 8 languages
        "account_age_days": account_age_days,
    }

    print(f"  ✅ {data['name']} | {data['total_commits']} commits | {data['total_stars']} stars | {data['repos_count']} repos")
    print(f"  ✅ Top languages: {', '.join(l[0] for l in data['lang_pcts'][:5])}")
    return data


# ─────────────────────────────────────────────
#  Radar chart score calculation
# ─────────────────────────────────────────────

def grade_from_avg(avg):
    """Return letter grade based on average score."""
    if avg >= 90: return "S"
    if avg >= 80: return "A"
    if avg >= 72: return "A-"
    if avg >= 65: return "B+"
    if avg >= 58: return "B"
    if avg >= 50: return "B-"
    if avg >= 42: return "C+"
    if avg >= 35: return "C"
    return "C-"


def calculate_radar_scores(data):
    """Derive 6 dimension scores from GitHub activity (realistic scale)."""
    commits = data["total_commits"]
    stars   = data["total_stars"]
    repos   = data["repos_count"]
    prs     = data["total_prs"]
    issues  = data["total_issues"]
    langs   = data["lang_pcts"]
    age_days = data["account_age_days"]

    lang_pct_map = {l[0]: l[1] for l in langs}

    # 1. Frontend: TS/JS/CSS/HTML/Vue — realistic multiplier (80% coverage → ~72)
    frontend_langs = {"JavaScript", "TypeScript", "CSS", "HTML", "Vue"}
    fe_raw = sum(lang_pct_map.get(l, 0) for l in frontend_langs)
    fe_score = min(fe_raw * 0.9, 100)

    # 2. Backend: Python/Go/etc — realistic (17% backend → ~20)
    backend_langs = {"Python", "Go", "Java", "Rust", "PLpgSQL", "Ruby", "PHP", "C", "C++", "Shell"}
    be_raw = sum(lang_pct_map.get(l, 0) for l in backend_langs)
    be_score = min(be_raw * 1.2, 100)

    # 3. Productivity: 1 commit/day → 80pts, 2/day → 100pts
    commits_per_day = commits / max(age_days, 1)
    prod_score = min(commits_per_day * 80, 100)

    # 4. Stars: actual star count (no cap)
    stars_score = stars

    # 5. Collaboration: PRs + issues (realistic, 1 PR ≈ 8pts)
    collab_score = min(prs * 8 + issues * 3, 100)

    # 6. Breadth: language diversity + repo count (realistic cap)
    breadth_score = min(len(langs) * 6 + repos * 3, 100)

    scores = [
        ("Frontend",      round(max(fe_score,    10))),
        ("Backend",       round(max(be_score,    10))),
        ("Productivity",  round(max(prod_score,  10))),
        ("Stars",         round(max(stars_score, 10))),
        ("Collaboration", round(max(collab_score,10))),
        ("Breadth",       round(max(breadth_score,10))),
    ]
    return scores


# ─────────────────────────────────────────────
#  SVG generators
# ─────────────────────────────────────────────

def fmt_num(n):
    if n >= 10000:
        return f"{n/1000:.1f}K"
    if n >= 1000:
        return f"{n/1000:.1f}K"
    return str(n)


def gen_header(data):
    """Generate the compact header card with key stats."""
    stars = fmt_num(data["total_stars"])
    commits = fmt_num(data["total_commits"])
    repos = data["repos_count"]
    prs = fmt_num(data["total_prs"])

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="840" height="90" viewBox="0 0 840 90">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0a0e27"/><stop offset="100%" stop-color="#0d1537"/>
    </linearGradient>
    <filter id="glow"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  </defs>
  <style>
    @keyframes fadeIn {{ 0% {{ opacity:0; transform:translateY(10px); }} 100% {{ opacity:1; transform:translateY(0); }} }}
    @keyframes twinkle {{ 0%,100% {{ opacity:0.15; }} 50% {{ opacity:0.6; }} }}
    @keyframes borderP {{ 0%,100% {{ stroke-opacity:0.15; }} 50% {{ stroke-opacity:0.35; }} }}
    .fi {{ animation: fadeIn 0.5s ease-out both; }}
    .border {{ animation: borderP 4s ease-in-out infinite; }}
    .star {{ animation: twinkle 3s ease-in-out infinite; }}
  </style>

  <rect x="1" y="1" width="838" height="88" rx="16" fill="url(#bg)"/>
  <rect x="1" y="1" width="838" height="88" rx="16" fill="none" stroke="#00d4ff" stroke-width="1" class="border"/>

  <!-- Stars -->
  <circle cx="80" cy="30" r="1" fill="#00d4ff" class="star"/><circle cx="200" cy="20" r="0.8" fill="#7c3aed" class="star" style="animation-delay:1s"/>
  <circle cx="640" cy="25" r="1.1" fill="#00d4ff" class="star" style="animation-delay:0.5s"/><circle cx="760" cy="35" r="0.7" fill="#a855f7" class="star" style="animation-delay:2s"/>
  <circle cx="400" cy="15" r="0.9" fill="#00d4ff" class="star" style="animation-delay:1.5s"/>
  <circle cx="120" cy="55" r="0.8" fill="#7c3aed" class="star" style="animation-delay:0.8s"/><circle cx="720" cy="50" r="1" fill="#00d4ff" class="star" style="animation-delay:2.2s"/>

  <!-- Stats row -->
  <g class="fi" style="animation-delay:0.25s">
    <rect x="90" y="17" width="130" height="56" rx="10" fill="rgba(255,215,0,0.04)" stroke="rgba(255,215,0,0.1)" stroke-width="1"/>
    <text x="155" y="40" text-anchor="middle" font-family="\'SFMono-Regular\',Consolas,monospace" font-size="20" font-weight="700" fill="#FFD700" filter="url(#glow)">{stars}</text>
    <text x="155" y="60" text-anchor="middle" font-family="\'Segoe UI\',system-ui,sans-serif" font-size="10" fill="#8892b0" letter-spacing="1">⭐ STARS</text>
  </g>
  <g class="fi" style="animation-delay:0.35s">
    <rect x="240" y="17" width="130" height="56" rx="10" fill="rgba(0,255,136,0.04)" stroke="rgba(0,255,136,0.1)" stroke-width="1"/>
    <text x="305" y="40" text-anchor="middle" font-family="\'SFMono-Regular\',Consolas,monospace" font-size="20" font-weight="700" fill="#00ff88" filter="url(#glow)">{commits}</text>
    <text x="305" y="60" text-anchor="middle" font-family="\'Segoe UI\',system-ui,sans-serif" font-size="10" fill="#8892b0" letter-spacing="1">🔥 COMMITS</text>
  </g>
  <g class="fi" style="animation-delay:0.45s">
    <rect x="390" y="17" width="130" height="56" rx="10" fill="rgba(124,58,237,0.04)" stroke="rgba(124,58,237,0.15)" stroke-width="1"/>
    <text x="455" y="40" text-anchor="middle" font-family="\'SFMono-Regular\',Consolas,monospace" font-size="20" font-weight="700" fill="#7c3aed" filter="url(#glow)">{prs}</text>
    <text x="455" y="60" text-anchor="middle" font-family="\'Segoe UI\',system-ui,sans-serif" font-size="10" fill="#8892b0" letter-spacing="1">🔀 PRs</text>
  </g>
  <g class="fi" style="animation-delay:0.55s">
    <rect x="540" y="17" width="130" height="56" rx="10" fill="rgba(0,212,255,0.04)" stroke="rgba(0,212,255,0.1)" stroke-width="1"/>
    <text x="605" y="40" text-anchor="middle" font-family="\'SFMono-Regular\',Consolas,monospace" font-size="20" font-weight="700" fill="#00d4ff" filter="url(#glow)">{repos}</text>
    <text x="605" y="60" text-anchor="middle" font-family="\'Segoe UI\',system-ui,sans-serif" font-size="10" fill="#8892b0" letter-spacing="1">📦 REPOS</text>
  </g>
</svg>'''


def gen_tech_stack(data):
    """Generate tech stack bars from real language data."""
    langs = data["lang_pcts"]
    if not langs:
        return ""
    
    # Square card: 480 x 480
    row_height = 42
    top_pad = 75
    card_h = 480
    bar_w = 380

    rows_svg = ""
    # Render up to 8 languages
    for i, (lang, pct) in enumerate(langs[:8]):
        y = top_pad + i * row_height
        fill_w = pct / 100 * bar_w
        color = LANG_COLORS.get(lang, "#888888")
        delay = 0.3 + i * 0.1
        rows_svg += f'''
    <g class="row" style="animation-delay:{delay}s">
      <text x="50" y="{y}" class="label">{lang}</text>
      <text x="430" y="{y}" text-anchor="end" class="pct" fill="{color}">{pct:.1f}%</text>
      <rect x="50" y="{y+6}" width="{bar_w}" height="8" rx="4" class="track"/>
      <rect x="50" y="{y+6}" width="{fill_w}" height="8" rx="4" fill="{color}" opacity="0.85">
        <animate attributeName="width" from="0" to="{fill_w}" dur="1.2s" begin="{delay}s" fill="freeze" calcMode="spline" keySplines="0.25 0.46 0.45 0.94"/>
      </rect>
      <circle cx="{50+fill_w}" cy="{y+10}" r="3" fill="{color}" class="dot" style="animation-delay:{delay+1.2}s"/>
    </g>'''

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="480" height="480" viewBox="0 0 480 480">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0a0e27"/><stop offset="100%" stop-color="#0d1537"/>
    </linearGradient>
    <linearGradient id="tG" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#00d4ff"/><stop offset="100%" stop-color="#7c3aed"/>
    </linearGradient>
    <filter id="glow"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  </defs>
  <style>
    @keyframes fadeIn {{ 0% {{ opacity:0; }} 100% {{ opacity:1; }} }}
    @keyframes pulse {{ 0%,100% {{ opacity:0.4;r:3; }} 50% {{ opacity:1;r:5; }} }}
    @keyframes borderP {{ 0%,100% {{ stroke-opacity:0.15; }} 50% {{ stroke-opacity:0.3; }} }}
    .row {{ animation: fadeIn 0.5s ease-out both; }}
    .label {{ font-family:\'Segoe UI\',system-ui,sans-serif; font-size:13px; fill:#e0e6f0; }}
    .pct {{ font-family:\'SFMono-Regular\',Consolas,monospace; font-size:13px; font-weight:600; }}
    .track {{ fill:rgba(255,255,255,0.06); }}
    .dot {{ animation: pulse 2s ease-in-out infinite; opacity:0; }}
    .border {{ animation: borderP 4s ease-in-out infinite; }}
  </style>
  <rect x="1" y="1" width="478" height="478" rx="16" fill="url(#bg)"/>
  <rect x="1" y="1" width="478" height="478" rx="16" fill="none" stroke="#00d4ff" stroke-width="1" class="border"/>
  <text x="240" y="45" text-anchor="middle" font-family="\'Segoe UI\',system-ui,sans-serif" font-size="18" font-weight="700" letter-spacing="3" fill="url(#tG)" filter="url(#glow)">⚡ TECH STACK</text>
  {rows_svg}
</svg>'''


def gen_radar(data):
    """Generate hexagonal radar chart from calculated scores."""
    scores = calculate_radar_scores(data)
    cx, cy = 240, 245
    R = 105

    # Hexagon vertex calculator (starts at top, clockwise)
    def hex_point(i, scale=1.0):
        angle = math.radians(-90 + i * 60)
        return (cx + R * scale * math.cos(angle), cy + R * scale * math.sin(angle))

    # Grid hexagons
    grids = ""
    for pct in [0.25, 0.5, 0.75, 1.0]:
        pts = " ".join(f"{hex_point(i, pct)[0]:.1f},{hex_point(i, pct)[1]:.1f}" for i in range(6))
        grids += f'  <polygon points="{pts}" class="grid"/>\n'

    # Axis lines
    axes = ""
    for i in range(6):
        px, py = hex_point(i)
        axes += f'  <line x1="{cx}" y1="{cy}" x2="{px:.1f}" y2="{py:.1f}" class="axis"/>\n'

    # Data polygon
    data_pts = []
    for i, (_, val) in enumerate(scores):
        scale = min(val / 100, 1.0)
        px, py = hex_point(i, scale)
        data_pts.append((px, py))
    poly_str = " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in data_pts)

    # Vertex dots
    dots = ""
    for i, (px, py) in enumerate(data_pts):
        dots += f'  <circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="#00d4ff" class="vertex" filter="url(#dg)" style="animation-delay:{i*0.3}s"/>\n'

    # Labels
    labels = ""
    for i, (name, val) in enumerate(scores):
        lx, ly = hex_point(i, 1.25)
        anchor = "middle"
        if i == 1 or i == 2:
            anchor = "start"
        elif i == 4 or i == 5:
            anchor = "end"
        labels += f'  <text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" class="lbl" style="animation-delay:{0.5+i*0.1}s">{name}</text>\n'
        labels += f'  <text x="{lx:.1f}" y="{ly+14:.1f}" text-anchor="{anchor}" class="score" style="animation-delay:{0.6+i*0.1}s">{val}</text>\n'

    avg   = sum(v for _, v in scores) / len(scores)
    grade = grade_from_avg(avg)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="480" height="480" viewBox="0 0 480 480">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0a0e27"/><stop offset="100%" stop-color="#0d1537"/>
    </linearGradient>
    <linearGradient id="sG" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#00d4ff"/><stop offset="100%" stop-color="#7c3aed"/>
    </linearGradient>
    <filter id="glow"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
    <filter id="pg"><feGaussianBlur stdDeviation="6" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
    <filter id="dg"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  </defs>
  <style>
    @keyframes drawP {{ 0% {{ stroke-dashoffset:800; }} 100% {{ stroke-dashoffset:0; }} }}
    @keyframes fadeIn {{ 0% {{ opacity:0; }} 100% {{ opacity:1; }} }}
    @keyframes pulse {{ 0%,100% {{ opacity:0.6;r:4; }} 50% {{ opacity:1;r:6; }} }}
    @keyframes fillF {{ 0% {{ fill-opacity:0; }} 100% {{ fill-opacity:0.15; }} }}
    @keyframes borderP {{ 0%,100% {{ stroke-opacity:0.15; }} 50% {{ stroke-opacity:0.3; }} }}
    .grid {{ stroke:rgba(0,212,255,0.08); stroke-width:1; fill:none; }}
    .axis {{ stroke:rgba(0,212,255,0.12); stroke-width:1; }}
    .dpoly {{ fill:rgba(0,212,255,0.15); stroke:#00d4ff; stroke-width:2; stroke-dasharray:800; animation:drawP 2s ease-out 0.5s both; }}
    .dfill {{ fill:rgba(0,212,255,0.15); stroke:none; animation:fillF 1s ease-out 2s both; fill-opacity:0; }}
    .vertex {{ animation: pulse 2.5s ease-in-out infinite; }}
    .lbl {{ font-family:\'Segoe UI\',system-ui,sans-serif; font-size:12px; fill:#e0e6f0; animation:fadeIn 0.5s ease-out both; }}
    .score {{ font-family:\'SFMono-Regular\',Consolas,monospace; font-size:11px; fill:#00d4ff; font-weight:600; animation:fadeIn 0.5s ease-out both; }}
    .border {{ animation: borderP 4s ease-in-out infinite; }}
  </style>

  <rect x="1" y="1" width="478" height="478" rx="16" fill="url(#bg)"/>
  <rect x="1" y="1" width="478" height="478" rx="16" fill="none" stroke="#00d4ff" stroke-width="1" class="border"/>

  <!-- B+ Grade Ring -->
  <circle cx="240" cy="62" r="28" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="5"/>
  <circle cx="240" cy="62" r="28" fill="none" stroke="url(#sG)" stroke-width="5" stroke-dasharray="176" stroke-dashoffset="35" stroke-linecap="round"/>
  <text x="240" y="69" text-anchor="middle" font-family="\'Segoe UI\',system-ui,sans-serif" font-size="18" font-weight="800" fill="#ffffff" filter="url(#glow)">{grade}</text>
  <text x="240" y="105" text-anchor="middle" font-family="\'Segoe UI\',system-ui,sans-serif" font-size="10" font-weight="700" fill="#8892b0" letter-spacing="1">DEVELOPER RANK</text>

{grids}
{axes}
  <polygon points="{poly_str}" class="dfill"/>
  <polygon points="{poly_str}" class="dpoly" filter="url(#pg)"/>
{dots}
{labels}

  <line x1="140" y1="415" x2="340" y2="415" stroke="rgba(0,212,255,0.1)" stroke-width="1"/>
  <text x="240" y="435" text-anchor="middle" font-family="\'Segoe UI\',system-ui,sans-serif" font-size="11" fill="#8892b0" letter-spacing="2">OVERALL</text>
  <text x="240" y="456" text-anchor="middle" font-family="\'SFMono-Regular\',Consolas,monospace" font-size="22" font-weight="700" fill="url(#sG)" filter="url(#glow)">{avg:.1f} / 100</text>
</svg>'''


# ─────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    data = fetch_data()

    cards = {
        "tech-stack.svg": gen_tech_stack(data),
        "radar.svg": gen_radar(data),
    }

    for fname, svg in cards.items():
        path = os.path.join(OUTPUT_DIR, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"  📝 Generated {fname}")

    # Write timestamp
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    with open(os.path.join(OUTPUT_DIR, ".last_updated"), "w") as f:
        f.write(ts)

    print(f"\n✅ All cards generated at {ts}")


if __name__ == "__main__":
    main()

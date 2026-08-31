#!/usr/bin/env python3
"""Generate self-hosted SVG metrics for a GitHub profile.

Only Python's standard library is used. In GitHub Actions, GITHUB_TOKEN gives the
script enough API quota to inspect the repository owner's public activity.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


USERNAME = os.environ.get("PROFILE_USERNAME", "7dsolv").strip() or "7dsolv"
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
API = "https://api.github.com"
GRAPHQL = "https://api.github.com/graphql"
USER_AGENT = "7dsolv-profile-generator/1.0"

BG = "#050b14"
PANEL = "#071421"
BORDER = "#134f72"
CYAN = "#20e3ff"
BLUE = "#448cff"
GREEN = "#20f6a7"
PURPLE = "#9b72ff"
TEXT = "#d8e7ff"
MUTED = "#7e9ab8"

LANGUAGE_COLORS = {
    "C": "#55a7d9",
    "C++": "#5f93d4",
    "Python": "#ffd343",
    "Java": "#f89820",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "HTML": "#e34c26",
    "CSS": "#663399",
    "Shell": "#89e051",
    "PowerShell": "#5391fe",
    "Assembly": "#6e4c13",
    "TSQL": "#e38c00",
}


def request_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")
        raise RuntimeError(f"GitHub respondeu HTTP {error.code} para {url}: {detail[:300]}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Não foi possível acessar {url}: {error.reason}") from error


def request_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def fetch_repositories() -> list[dict[str, Any]]:
    repositories: list[dict[str, Any]] = []
    page = 1
    while True:
        query = urllib.parse.urlencode({"per_page": 100, "page": page, "sort": "updated"})
        batch = request_json(f"{API}/users/{urllib.parse.quote(USERNAME)}/repos?{query}")
        repositories.extend(batch)
        if len(batch) < 100:
            return repositories
        page += 1


def fetch_languages(repositories: list[dict[str, Any]]) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    for repository in repositories:
        if repository.get("fork") or repository.get("archived"):
            continue
        language_url = repository.get("languages_url")
        if not language_url:
            continue
        for language, size in request_json(language_url).items():
            totals[language] += int(size)
    return dict(totals)


def fetch_contributions() -> tuple[int, list[dict[str, Any]], date, date]:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=364)

    if TOKEN:
        query = """
        query($login: String!, $from: DateTime!, $to: DateTime!) {
          user(login: $login) {
            contributionsCollection(from: $from, to: $to) {
              contributionCalendar {
                totalContributions
                weeks {
                  contributionDays {
                    date
                    contributionCount
                    contributionLevel
                    weekday
                  }
                }
              }
            }
          }
        }
        """
        variables = {
            "login": USERNAME,
            "from": datetime.combine(start, datetime.min.time(), timezone.utc).isoformat(),
            "to": datetime.combine(today, datetime.max.time(), timezone.utc).isoformat(),
        }
        response = request_json(GRAPHQL, method="POST", payload={"query": query, "variables": variables})
        if response.get("errors"):
            raise RuntimeError(f"GraphQL retornou erros: {response['errors']}")
        calendar = response["data"]["user"]["contributionsCollection"]["contributionCalendar"]
        days = [day for week in calendar["weeks"] for day in week["contributionDays"]]
        return int(calendar["totalContributions"]), days, start, today

    # Public fallback for local generation without a token. GitHub's endpoint
    # returns the selected year's public contribution levels.
    start = date(today.year, 1, 1)
    end = today
    request_end = date(today.year, 12, 31)
    url = (
        f"https://github.com/users/{urllib.parse.quote(USERNAME)}/contributions"
        f"?from={start.isoformat()}&to={request_end.isoformat()}"
    )
    page = request_text(url)
    match = re.search(r'<h2[^>]*id="js-contribution-activity-description"[^>]*>\s*([0-9,.]+)', page)
    total = int(re.sub(r"\D", "", match.group(1))) if match else 0
    days: list[dict[str, Any]] = []
    pattern = re.compile(
        r'<td[^>]*data-date="(\d{4}-\d{2}-\d{2})"[^>]*data-level="([0-4])"[^>]*class="ContributionCalendar-day"',
        re.DOTALL,
    )
    for day_text, level_text in pattern.findall(page):
        day_value = date.fromisoformat(day_text)
        days.append(
            {
                "date": day_text,
                "contributionCount": 0,
                "contributionLevel": f"LEVEL_{level_text}",
                "weekday": (day_value.weekday() + 1) % 7,
            }
        )
    return total, days, start, end


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def compact_number(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M".replace(".0M", "M")
    if value >= 1_000:
        return f"{value / 1_000:.1f}k".replace(".0k", "k")
    return str(value)


def svg_shell(width: int, height: int, title: str, body: str) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">{esc(title)}</title>
  <desc id="desc">Métricas públicas geradas automaticamente para o perfil GitHub de {esc(USERNAME)}.</desc>
  <defs>
    <linearGradient id="card-bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#071421"/>
      <stop offset="1" stop-color="#040912"/>
    </linearGradient>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{CYAN}"/>
      <stop offset="0.52" stop-color="{BLUE}"/>
      <stop offset="1" stop-color="{PURPLE}"/>
    </linearGradient>
    <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">
      <path d="M24 0H0V24" fill="none" stroke="#14314a" stroke-width="0.5" opacity="0.28"/>
    </pattern>
    <filter id="glow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="2.2" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="14" fill="url(#card-bg)" stroke="{BORDER}"/>
  <rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="14" fill="url(#grid)"/>
  <path d="M14 1H{width - 14}" stroke="url(#accent)" stroke-width="2"/>
  {body}
</svg>
'''


def render_metrics(user: dict[str, Any], repositories: list[dict[str, Any]], contributions: int) -> str:
    owned = [repo for repo in repositories if not repo.get("fork")]
    stars = sum(int(repo.get("stargazers_count", 0)) for repo in owned)
    forks = sum(int(repo.get("forks_count", 0)) for repo in owned)
    metrics = [
        ("REPOSITÓRIOS PÚBLICOS", len(repositories), CYAN),
        ("CONTRIBUIÇÕES · 365D", contributions, GREEN),
        ("SEGUIDORES", int(user.get("followers", 0)), PURPLE),
        ("ESTRELAS / FORKS", f"{compact_number(stars)} / {compact_number(forks)}", BLUE),
    ]
    cards: list[str] = []
    for index, (label, value, color) in enumerate(metrics):
        x = 24 + index * 294
        display_value = compact_number(value) if isinstance(value, int) else value
        cards.append(f'''
    <g transform="translate({x} 62)">
      <rect width="270" height="104" rx="10" fill="#06101c" stroke="#174765"/>
      <path d="M0 10V0H10 M260 0H270V10 M0 94V104H10 M260 104H270V94" fill="none" stroke="{color}" stroke-width="1.5"/>
      <circle cx="30" cy="35" r="9" fill="none" stroke="{color}" stroke-width="2" filter="url(#glow)"/>
      <text x="51" y="40" fill="{MUTED}" font-family="Segoe UI,Arial,sans-serif" font-size="13" letter-spacing="1">{esc(label)}</text>
      <text x="28" y="82" fill="{TEXT}" font-family="Segoe UI,Arial,sans-serif" font-size="32" font-weight="700">{esc(display_value)}</text>
    </g>''')
    updated = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    body = f'''
  <circle cx="24" cy="27" r="5" fill="{CYAN}" filter="url(#glow)"/>
  <text x="40" y="33" fill="{CYAN}" font-family="Consolas,monospace" font-size="15" letter-spacing="1.2">GITHUB // TELEMETRIA PÚBLICA</text>
  <text x="1176" y="33" text-anchor="end" fill="{MUTED}" font-family="Consolas,monospace" font-size="11">ATUALIZADO {esc(updated)}</text>
  {''.join(cards)}
  <text x="24" y="194" fill="{MUTED}" font-family="Consolas,monospace" font-size="10">FONTE: API OFICIAL DO GITHUB · REPOSITÓRIOS DO TITULAR · CONTRIBUIÇÕES PÚBLICAS DOS ÚLTIMOS 365 DIAS</text>'''
    return svg_shell(1200, 210, "GitHub stats", body)


def render_languages(languages: dict[str, int]) -> str:
    total = sum(languages.values())
    ranked = sorted(languages.items(), key=lambda item: item[1], reverse=True)[:6]
    if not ranked:
        ranked = [("Sem dados", 1)]
        total = 1

    bars: list[str] = []
    for index, (language, size) in enumerate(ranked):
        y = 78 + index * 34
        percentage = size / total * 100
        bar_width = max(3, percentage / 100 * 244)
        color = LANGUAGE_COLORS.get(language, [CYAN, BLUE, PURPLE, GREEN][index % 4])
        bars.append(f'''
  <circle cx="25" cy="{y - 4}" r="5" fill="{color}"/>
  <text x="40" y="{y}" fill="{TEXT}" font-family="Segoe UI,Arial,sans-serif" font-size="13">{esc(language)}</text>
  <rect x="154" y="{y - 14}" width="244" height="13" rx="4" fill="#17283a"/>
  <rect x="154" y="{y - 14}" width="{bar_width:.1f}" height="13" rx="4" fill="{color}"/>
  <text x="424" y="{y - 2}" fill="{TEXT}" font-family="Consolas,monospace" font-size="12">{percentage:4.1f}%</text>''')

    body = f'''
  <circle cx="22" cy="25" r="5" fill="{CYAN}" filter="url(#glow)"/>
  <text x="38" y="31" fill="{CYAN}" font-family="Consolas,monospace" font-size="14" letter-spacing="1">LINGUAGENS MAIS USADAS</text>
  <text x="478" y="31" text-anchor="end" fill="{MUTED}" font-family="Consolas,monospace" font-size="10">POR BYTES</text>
  {''.join(bars)}'''
    return svg_shell(500, 300, "Linguagens mais usadas", body)


def contribution_level(day: dict[str, Any]) -> int:
    level = str(day.get("contributionLevel", "NONE"))
    if level.startswith("LEVEL_"):
        return int(level.removeprefix("LEVEL_"))
    return {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}.get(level, 0)


def render_contributions(total: int, days: list[dict[str, Any]], start: date, end: date) -> str:
    by_date = {date.fromisoformat(day["date"]): day for day in days}
    first = min(by_date, default=start)
    last = max(by_date, default=end)
    first -= timedelta(days=(first.weekday() + 1) % 7)  # previous Sunday
    last += timedelta(days=(6 - ((last.weekday() + 1) % 7)))
    week_count = ((last - first).days // 7) + 1
    max_weeks = 53
    if week_count > max_weeks:
        first = last - timedelta(days=(max_weeks * 7) - 1)
        week_count = max_weeks

    cell = 8
    gap = 3
    x0 = 42
    y0 = 88
    palette = ["#132235", "#075a54", "#0a8f72", "#18c98f", GREEN]
    squares: list[str] = []
    month_labels: list[str] = []
    seen_months: set[tuple[int, int]] = set()

    for week in range(week_count):
        for weekday in range(7):
            current = first + timedelta(days=week * 7 + weekday)
            if current < start or current > end:
                continue
            day = by_date.get(current, {})
            level = contribution_level(day)
            count = int(day.get("contributionCount", 0))
            x = x0 + week * (cell + gap)
            y = y0 + weekday * (cell + gap)
            squares.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{palette[level]}"><title>{esc(current.isoformat())} · {count} contribuições</title></rect>'
            )
            month_key = (current.year, current.month)
            if current.day <= 7 and month_key not in seen_months:
                seen_months.add(month_key)
                month = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"][current.month - 1]
                month_labels.append(
                    f'<text x="{x}" y="76" fill="{MUTED}" font-family="Consolas,monospace" font-size="9">{month}</text>'
                )

    ordered_days = [by_date[current] for current in sorted(by_date) if start <= current <= end]
    active_days = sum(int(day.get("contributionCount", 0)) > 0 for day in ordered_days)
    best_day = max((int(day.get("contributionCount", 0)) for day in ordered_days), default=0)
    longest_streak = 0
    current_streak = 0
    for day in ordered_days:
        if int(day.get("contributionCount", 0)) > 0:
            current_streak += 1
            longest_streak = max(longest_streak, current_streak)
        else:
            current_streak = 0

    summary = [
        ("DIAS ATIVOS", active_days, CYAN),
        ("MELHOR DIA", best_day, GREEN),
        ("MAIOR SEQUÊNCIA", f"{longest_streak}d", PURPLE),
    ]
    summary_cards: list[str] = []
    for index, (label, value, color) in enumerate(summary):
        x = 24 + index * 222
        summary_cards.append(f'''
  <g transform="translate({x} 200)">
    <rect width="208" height="70" rx="9" fill="#06101c" stroke="#174765"/>
    <circle cx="18" cy="21" r="4" fill="{color}" filter="url(#glow)"/>
    <text x="31" y="25" fill="{MUTED}" font-family="Consolas,monospace" font-size="9" letter-spacing="0.8">{esc(label)}</text>
    <text x="16" y="57" fill="{TEXT}" font-family="Segoe UI,Arial,sans-serif" font-size="25" font-weight="700">{esc(value)}</text>
  </g>''')

    legend = "".join(
        f'<rect x="{535 + index * 14}" y="180" width="9" height="9" rx="2" fill="{color}"/>'
        for index, color in enumerate(palette)
    )
    body = f'''
  <circle cx="22" cy="25" r="5" fill="{CYAN}" filter="url(#glow)"/>
  <text x="38" y="31" fill="{CYAN}" font-family="Consolas,monospace" font-size="14" letter-spacing="1">CONTRIBUIÇÕES</text>
  <text x="678" y="31" text-anchor="end" fill="{TEXT}" font-family="Consolas,monospace" font-size="13">{esc(total)} NO PERÍODO</text>
  {''.join(month_labels)}
  <text x="25" y="100" fill="{MUTED}" font-family="Consolas,monospace" font-size="9">D</text>
  <text x="25" y="122" fill="{MUTED}" font-family="Consolas,monospace" font-size="9">T</text>
  <text x="25" y="144" fill="{MUTED}" font-family="Consolas,monospace" font-size="9">Q</text>
  {''.join(squares)}
  <text x="500" y="189" text-anchor="end" fill="{MUTED}" font-family="Consolas,monospace" font-size="9">MENOS</text>
  {legend}
  <text x="610" y="189" fill="{MUTED}" font-family="Consolas,monospace" font-size="9">MAIS</text>
{''.join(summary_cards)}
  <text x="24" y="289" fill="{MUTED}" font-family="Consolas,monospace" font-size="9">{esc(start.isoformat())} → {esc(end.isoformat())} · JANELA MÓVEL DE 365 DIAS · CONTRIBUIÇÕES PÚBLICAS</text>'''
    return svg_shell(700, 300, "Calendário de contribuições", body)


def write_asset(name: str, content: str) -> None:
    ET.fromstring(content)
    target = ASSETS / name
    target.write_text(content, encoding="utf-8", newline="\n")
    print(f"generated {target.relative_to(ROOT)}")


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    user = request_json(f"{API}/users/{urllib.parse.quote(USERNAME)}")
    repositories = fetch_repositories()
    languages = fetch_languages(repositories)
    total_contributions, contribution_days, start, end = fetch_contributions()

    write_asset("metrics.svg", render_metrics(user, repositories, total_contributions))
    write_asset("languages.svg", render_languages(languages))
    write_asset(
        "contributions.svg",
        render_contributions(total_contributions, contribution_days, start, end),
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # Keep the Actions log concise and actionable.
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)

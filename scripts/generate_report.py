#!/usr/bin/env python3
"""Collect GitHub Trending snapshots and render a compact Chinese report."""

from __future__ import annotations

import json
import ssl
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS = ROOT / "reports"


def clean(text: str) -> str:
    return " ".join(text.split())


def number(text: str) -> int:
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else 0


class TrendingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[dict] = []
        self.current: dict[str, str] | None = None
        self.depth = 0
        self.capture_key: str | None = None
        self.capture_tag: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = (values.get("class") or "").split()
        if tag == "article" and "Box-row" in classes and self.current is None:
            self.current = {"name": "", "description": "", "language": "", "stars": "", "recent": ""}
            self.depth = 1
            return
        if self.current is None:
            return
        self.depth += 1
        key = None
        if tag == "h2":
            key = "name"
        elif tag == "p" and "col-9" in classes:
            key = "description"
        elif values.get("itemprop") == "programmingLanguage":
            key = "language"
        elif tag == "a" and (values.get("href") or "").endswith("/stargazers"):
            key = "stars"
        elif tag == "span" and "float-sm-right" in classes:
            key = "recent"
        if key:
            self.capture_key, self.capture_tag = key, tag

    def handle_endtag(self, tag: str) -> None:
        if self.current is None:
            return
        if tag == self.capture_tag:
            self.capture_key = self.capture_tag = None
        self.depth -= 1
        if self.depth == 0:
            self.rows.append(self.current)
            self.current = None

    def handle_data(self, data: str) -> None:
        if self.current is not None and self.capture_key:
            self.current[self.capture_key] += data


def fetch(period: str) -> list[dict]:
    url = "https://github.com/trending?" + urlencode({"since": period})
    request = Request(url, headers={
        "Accept": "text/html,application/xhtml+xml",
        "User-Agent": "github-trending-cn-mail/1.0",
    })
    with urlopen(request, timeout=25, context=ssl.create_default_context()) as response:
        body = response.read().decode("utf-8")
    parser = TrendingParser()
    parser.feed(body)
    rows = []
    for rank, article in enumerate(parser.rows, 1):
        name = "/".join(part.strip() for part in clean(article["name"]).split("/") if part.strip())
        if not name:
            continue
        rows.append({
            "rank": rank,
            "name": name,
            "url": f"https://github.com/{name}",
            "description": clean(article["description"]),
            "language": clean(article["language"]) or "未注明",
            "stars": number(article["stars"]),
            "period_stars": number(article["recent"]),
            "period": period,
        })
    if not rows:
        raise RuntimeError(f"GitHub Trending returned no {period} repositories")
    return rows


def load_previous() -> dict[str, int]:
    path = DATA / "current.json"
    if not path.exists():
        return {}
    try:
        return {item["name"]: int(item["stars"]) for item in json.loads(path.read_text())["repos"]}
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return {}


def main() -> None:
    DATA.mkdir(exist_ok=True)
    REPORTS.mkdir(exist_ok=True)
    now = datetime.now(timezone.utc)
    today = now.astimezone().date().isoformat()
    previous = load_previous()
    daily = fetch("daily")
    weekly = fetch("weekly")
    merged = {item["name"]: item for item in daily + weekly}
    for item in merged.values():
        old = previous.get(item["name"])
        item["snapshot_delta"] = max(item["stars"] - old, 0) if old is not None else None

    payload = {
        "generated_at": now.isoformat(),
        "daily": daily,
        "weekly": weekly,
        "repos": sorted(merged.values(), key=lambda item: item["stars"], reverse=True),
    }
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    (DATA / "current.json").write_text(encoded)
    (DATA / f"{today}.json").write_text(encoded)
    (REPORTS / "latest.json").write_text(encoded)

    lines = [
        f"# GitHub 热门项目日报｜{today}", "",
        f"> 数据更新时间：{now.strftime('%Y-%m-%d %H:%M UTC')}。近期新增 Star 来自 GitHub Trending；快照增量是与上次采集的总 Star 差值。",
        "", "## 最近一周热门 Top 10", "",
    ]
    for item in weekly[:10]:
        delta = merged[item["name"]].get("snapshot_delta")
        delta_text = "首次记录" if delta is None else f"较上次 +{delta}"
        lines.extend([
            f"### {item['rank']}. [{item['name']}]({item['url']})",
            f"- 语言：{item['language']}｜总 Star：{item['stars']:,}｜本周新增：{item['period_stars']:,}｜{delta_text}",
            f"- 项目简介：{item['description'] or '仓库未提供简介'}", "",
        ])
    lines.extend(["## 今日热门 Top 10", ""])
    for item in daily[:10]:
        lines.append(f"{item['rank']}. [{item['name']}]({item['url']}) — {item['language']}，今日新增 {item['period_stars']:,} Star")
    lines.extend([
        "", "## 口径说明", "",
        "- GitHub 没有公开的 Trending API；本项目读取公开 Trending 页面，因此页面结构变化可能导致采集失败。",
        "- Trending 的近期新增数由 GitHub 页面展示；快照增量仅在连续运行后有意义。",
        "- 邮件中的中文解读由 Mac 2019 上的 WorkBuddy 根据本报告生成，不修改原始数据。", "",
    ])
    (REPORTS / "latest.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()

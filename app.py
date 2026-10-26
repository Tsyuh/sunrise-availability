from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Iterable
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://ressha-kanko.com/train/sunrise"
OFFICIAL_URL = "https://www.jr-odekake.net/goyoyaku/campaign/sunriseseto_izumo/form.html"
JST = ZoneInfo("Asia/Tokyo")
STATUS_MAP = {
    "○": "空席あり",
    "△": "残りわずか",
    "×": "満席",
    "準": "販売前",
    "休": "運行なし",
    "!": "取得不可",
    "－": "設定なし",
    "-": "設定なし",
}

HTML = r'''<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
  <meta name="theme-color" content="#07111d">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="サンライズ空席">
  <link rel="manifest" href="/manifest.webmanifest">
  <title>サンライズ空席チェッカー</title>
  <style>
    :root{color-scheme:dark;--bg:#07111d;--card:#0f2032;--card2:#132941;--text:#f5f7fb;--muted:#9fb0c3;--line:rgba(255,255,255,.10);--accent:#f0c66e;--open:#5bd39a;--low:#f4c35b;--full:#ea6f76}
    *{box-sizing:border-box}html{background:var(--bg)}body{margin:0;min-height:100vh;font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue","Hiragino Sans","Yu Gothic",sans-serif;background:radial-gradient(circle at 100% 0%,#173a59 0,transparent 36rem),var(--bg);color:var(--text)}
    button,select,input{font:inherit}a{color:inherit}.shell{width:min(100%,720px);margin:0 auto;padding:max(28px,env(safe-area-inset-top)) 16px calc(110px + env(safe-area-inset-bottom))}.hero{padding:12px 4px 26px}.eyebrow{color:var(--accent);font-weight:800;letter-spacing:.18em;font-size:12px;margin:0 0 10px}h1{font-size:clamp(36px,12vw,58px);line-height:.95;letter-spacing:-.04em;margin:0}.sub{margin:16px 0 0;color:var(--muted)}
    .panel{background:rgba(15,32,50,.90);border:1px solid var(--line);border-radius:22px;padding:16px;box-shadow:0 16px 50px rgba(0,0,0,.2);backdrop-filter:blur(18px)}.controls{display:grid;gap:12px}label{display:grid;gap:7px;color:var(--muted);font-size:13px;font-weight:700}select,input[type=date]{width:100%;min-height:48px;border:1px solid var(--line);border-radius:14px;padding:0 13px;color:var(--text);background:var(--card2)}.actions{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:4px}button,.official{min-height:48px;border-radius:14px;border:0;display:inline-flex;align-items:center;justify-content:center;font-weight:800;text-decoration:none;cursor:pointer}.primary{background:var(--accent);color:#17202a}.secondary{background:#1c3853;color:var(--text);border:1px solid var(--line)}.official{background:var(--text);color:#0a1723}
    .summary{display:flex;gap:14px;flex-wrap:wrap;color:var(--muted);font-size:12px;margin:16px 4px}.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px}.dot-open{background:var(--open)}.dot-low{background:var(--low)}.dot-full{background:var(--full)}.status{min-height:24px;color:var(--muted);font-size:13px;margin:10px 4px}.status.error{color:#ffb2b7}.results{display:grid;gap:10px}.result-card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:15px;display:grid;grid-template-columns:1fr auto;gap:12px;align-items:center}.result-card .date{font-size:18px;font-weight:900}.result-card .train{margin-top:6px;font-size:14px;font-weight:800}.result-card .route{margin-top:3px;font-size:12px;color:var(--muted)}.badge{min-width:76px;text-align:center;border-radius:14px;padding:10px 8px;font-weight:900}.badge.open{color:var(--open);background:rgba(91,211,154,.10)}.badge.low{color:var(--low);background:rgba(244,195,91,.10)}.badge.full{color:var(--full);background:rgba(234,111,118,.10)}.badge.other{color:var(--muted);background:rgba(159,176,195,.10)}.empty{padding:24px;text-align:center;color:var(--muted);background:var(--card);border:1px solid var(--line);border-radius:18px}.sticky-actions{position:fixed;left:50%;transform:translateX(-50%);bottom:0;width:min(100%,720px);padding:12px 16px calc(12px + env(safe-area-inset-bottom));display:grid;grid-template-columns:1fr 1fr;gap:10px;background:linear-gradient(to top,#07111d 72%,rgba(7,17,29,0))}footer{margin-top:26px;color:var(--muted);font-size:11px;line-height:1.6}@media(min-width:620px){.controls{grid-template-columns:1fr 1fr 1fr}.actions{grid-column:1/-1}}
  </style>
</head>
<body>
<main class="shell">
  <header class="hero"><p class="eyebrow">SUNRISE EXPRESS</p><h1>サンライズ<br>空席チェッカー</h1><p class="sub">出雲・瀬戸の空席状況をスマホで確認</p></header>
  <section class="panel controls" aria-label="検索条件">
    <label>列車<select id="train"><option value="all">すべて</option><option value="出雲">サンライズ出雲</option><option value="瀬戸">サンライズ瀬戸</option><option value="出雲・瀬戸">併結区間</option></select></label>
    <label>方向<select id="direction"><option value="all">上下とも</option><option value="下り">下り</option><option value="上り">上り</option></select></label>
    <label>乗車日<input id="date" type="date"></label>
    <div class="actions"><button id="search" class="primary">空席を確認</button><button id="reset" class="secondary">条件を戻す</button></div>
  </section>
  <section class="summary"><div><span class="dot dot-open"></span>○ 空席あり</div><div><span class="dot dot-low"></span>△ 残りわずか</div><div><span class="dot dot-full"></span>× 満席</div></section>
  <section id="status" class="status">読み込み前</section><section id="results" class="results" aria-live="polite"></section>
  <div class="sticky-actions"><button id="refresh" class="secondary">最新情報に更新</button><a class="official" href="__OFFICIAL__" target="_blank" rel="noopener">JR公式で確認</a></div>
  <footer><p>表示は参考情報です。予約時はJR公式で最終確認してください。</p><p>取得元：<a href="__SOURCE__" target="_blank" rel="noopener">観光列車ナビ</a></p></footer>
</main>
<script>
const $=id=>document.getElementById(id),train=$('train'),direction=$('direction'),date=$('date'),statusBox=$('status'),results=$('results');
function badgeClass(s){if(s==='○')return'open';if(s==='△')return'low';if(s==='×')return'full';return'other'}
function formatDate(iso){const d=new Date(`${iso}T00:00:00+09:00`);return new Intl.DateTimeFormat('ja-JP',{month:'numeric',day:'numeric',weekday:'short'}).format(d)}
function saveFilters(){localStorage.setItem('sunriseFilters',JSON.stringify({train:train.value,direction:direction.value,date:date.value}))}
function restoreFilters(){try{const v=JSON.parse(localStorage.getItem('sunriseFilters')||'{}');if(v.train)train.value=v.train;if(v.direction)direction.value=v.direction;if(v.date)date.value=v.date}catch(_){}}
async function load(force=false){saveFilters();statusBox.classList.remove('error');statusBox.textContent=force?'最新情報を取得中…':'空席情報を取得中…';results.innerHTML='';const params=new URLSearchParams({train:train.value,direction:direction.value});if(date.value)params.set('date',date.value);if(force)params.set('force','1');try{const response=await fetch(`/api/availability?${params.toString()}`,{cache:'no-store'});const data=await response.json();if(!response.ok||!data.ok)throw new Error(data.error||'取得に失敗しました');const sourceTime=data.items[0]?.fetched_at;const timeText=sourceTime?new Date(sourceTime).toLocaleString('ja-JP'):'不明';statusBox.textContent=`${data.count}件表示・取得 ${timeText}${data.cached?'（キャッシュ）':''}`;if(!data.items.length){results.innerHTML='<div class="empty">指定条件の情報がありません。条件を変えるか、JR公式で確認してください。</div>';return}results.innerHTML=data.items.map(item=>`<article class="result-card"><div><div class="date">${formatDate(item.travel_date)}</div><div class="train">${item.train}</div><div class="route">${item.direction}</div></div><div class="badge ${badgeClass(item.status)}">${item.status}<br><small>${item.status_text}</small></div></article>`).join('')}catch(error){statusBox.textContent=`取得できませんでした：${error.message}`;statusBox.classList.add('error');results.innerHTML='<div class="empty">取得元の障害・通信エラー・ページ構造変更の可能性があります。JR公式ボタンから確認してください。</div>'}}
$('search').addEventListener('click',()=>load(false));$('refresh').addEventListener('click',()=>load(true));$('reset').addEventListener('click',()=>{train.value='all';direction.value='all';date.value='';saveFilters();load(false)});restoreFilters();load(false);
</script>
</body></html>'''

MANIFEST = json.dumps({
    "name": "サンライズ空席チェッカー",
    "short_name": "サンライズ空席",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#07111d",
    "theme_color": "#07111d",
}, ensure_ascii=False)

@dataclass(frozen=True)
class Availability:
    train: str
    direction: str
    travel_date: str
    status: str
    status_text: str
    fetched_at: str

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ")).strip()


def infer_date(month: int, day: int, today: date) -> date:
    candidates: list[date] = []
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            candidates.append(date(year, month, day))
        except ValueError:
            pass
    in_window = [d for d in candidates if -7 <= (d - today).days <= 62]
    if in_window:
        return min(in_window, key=lambda d: abs((d - today).days))
    return min(candidates, key=lambda d: abs((d - today).days))


def fetch_html(timeout: int = 20) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; SunriseMobileChecker/3.0; personal-use)",
        "Accept-Language": "ja,en;q=0.8",
        "Cache-Control": "no-cache",
    }
    response = requests.get(SOURCE_URL, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text


def _extract_train(joined: str, current: str) -> str:
    if "サンライズ出雲・瀬戸" in joined:
        return "サンライズ出雲・瀬戸"
    has_izumo = "サンライズ出雲" in joined
    has_seto = "サンライズ瀬戸" in joined
    if has_izumo and not has_seto:
        return "サンライズ出雲"
    if has_seto and not has_izumo:
        return "サンライズ瀬戸"
    return current


def parse_calendar(html: str, now: datetime | None = None) -> list[Availability]:
    soup = BeautifulSoup(html, "html.parser")
    now = now or datetime.now(JST)
    today = now.date()
    fetched_at = now.isoformat(timespec="seconds")
    results: list[Availability] = []

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        date_columns: list[tuple[int, date]] = []
        for row in rows[:8]:
            cells = row.find_all(["th", "td"])
            local: list[tuple[int, date]] = []
            for index, cell in enumerate(cells):
                txt = normalize_text(cell.get_text(" ", strip=True))
                match = re.search(r"(?<!\d)(\d{1,2})\s*/\s*(\d{1,2})(?!\d)", txt)
                if match:
                    local.append((index, infer_date(int(match.group(1)), int(match.group(2)), today)))
            if len(local) >= 3:
                date_columns = local
                break
        if not date_columns:
            continue

        current_train = ""
        n_dates = len(date_columns)
        for row in rows:
            cells = row.find_all(["th", "td"])
            if not cells:
                continue
            texts = [normalize_text(c.get_text(" ", strip=True)) for c in cells]
            joined = " | ".join(texts)
            current_train = _extract_train(joined, current_train)
            if not current_train:
                continue
            direction_text = ""
            for txt in texts[:6]:
                if any(word in txt for word in ("下り", "上り", "併結区間")):
                    direction_text = txt.replace("公式予約", "").strip()
                    break
            if not direction_text or len(cells) < n_dates:
                continue
            status_cells = cells[-n_dates:]
            for (_, travel_date), cell in zip(date_columns, status_cells):
                raw = normalize_text(cell.get_text(" ", strip=True))
                attrs = " ".join(str(v) for v in cell.attrs.values())
                status = next((s for s in STATUS_MAP if raw == s or raw.startswith(s)), "")
                if not status:
                    status = next((s for s in STATUS_MAP if s in attrs), "")
                if not status:
                    continue
                results.append(Availability(current_train, direction_text, travel_date.isoformat(), status, STATUS_MAP[status], fetched_at))

    deduped: dict[tuple[str, str, str], Availability] = {}
    for item in results:
        deduped[(item.train, item.direction, item.travel_date)] = item
    return sorted(deduped.values(), key=lambda x: (x.travel_date, x.train, x.direction))


def filter_items(items: Iterable[Availability], train: str | None = None, direction: str | None = None, travel_date: str | None = None) -> list[Availability]:
    output = list(items)
    if train and train != "all":
        output = [x for x in output if train in x.train]
    if direction and direction != "all":
        output = [x for x in output if direction in x.direction]
    if travel_date:
        output = [x for x in output if x.travel_date == travel_date]
    return output


class AvailabilityCache:
    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._items: list[Availability] = []
        self._stored_at = 0.0

    def get(self, force: bool = False) -> tuple[list[Availability], bool]:
        now = time.monotonic()
        with self._lock:
            if not force and self._items and now - self._stored_at < self.ttl_seconds:
                return self._items, True
        parsed = parse_calendar(fetch_html())
        if not parsed:
            raise RuntimeError("空席カレンダーを解析できませんでした。取得元のページ構造が変わった可能性があります。")
        with self._lock:
            self._items = parsed
            self._stored_at = time.monotonic()
        return parsed, False


cache = AvailabilityCache(ttl_seconds=int(os.getenv("CACHE_SECONDS", "300")))


def _respond(start_response, status: str, body: bytes, content_type: str, extra_headers=None):
    headers = [("Content-Type", content_type), ("Content-Length", str(len(body))), ("X-Content-Type-Options", "nosniff")]
    if extra_headers:
        headers.extend(extra_headers)
    start_response(status, headers)
    return [body]


def _json(start_response, payload: dict, status="200 OK"):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return _respond(start_response, status, body, "application/json; charset=utf-8", [("Cache-Control", "no-store")])


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO", "/")
    if method != "GET":
        return _respond(start_response, "405 Method Not Allowed", b"Method not allowed", "text/plain; charset=utf-8")
    if path == "/":
        html = HTML.replace("__OFFICIAL__", OFFICIAL_URL).replace("__SOURCE__", SOURCE_URL)
        return _respond(start_response, "200 OK", html.encode("utf-8"), "text/html; charset=utf-8", [("Cache-Control", "no-cache")])
    if path == "/manifest.webmanifest":
        return _respond(start_response, "200 OK", MANIFEST.encode("utf-8"), "application/manifest+json; charset=utf-8")
    if path == "/health":
        return _json(start_response, {"ok": True})
    if path == "/api/availability":
        params = parse_qs(environ.get("QUERY_STRING", ""))
        value = lambda key, default="": params.get(key, [default])[0]
        train = value("train", "all")
        direction = value("direction", "all")
        travel_date = value("date", "")
        force = value("force", "0") == "1"
        try:
            items, from_cache = cache.get(force=force)
            selected = filter_items(items, train=train, direction=direction, travel_date=travel_date or None)
            return _json(start_response, {
                "ok": True,
                "items": [item.to_dict() for item in selected],
                "count": len(selected),
                "cached": from_cache,
                "server_time": datetime.now(JST).isoformat(timespec="seconds"),
                "source": SOURCE_URL,
                "official": OFFICIAL_URL,
                "note": "参考情報です。予約可否はJR公式で最終確認してください。",
            })
        except Exception as exc:
            return _json(start_response, {"ok": False, "items": [], "count": 0, "error": str(exc), "official": OFFICIAL_URL}, "502 Bad Gateway")
    return _respond(start_response, "404 Not Found", b"Not found", "text/plain; charset=utf-8")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"Sunrise checker: http://127.0.0.1:{port}")
    with make_server("0.0.0.0", port, application) as server:
        server.serve_forever()

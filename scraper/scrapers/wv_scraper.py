"""West Virginia Lottery — full prize tier data with real-time remaining counts.
WV uses Next.js RSC (React Server Components) — prize data is embedded as a
server-rendered hydration payload in every page's HTML. No Playwright needed.
Individual game pages contain prizeDetails with prize/totalPrizes/remainingPrizes.
"""
import re
import json
import time
import requests
from datetime import datetime, timezone

_BASE = "https://wvlottery.com"
_LIST_URL = f"{_BASE}/games/scratch-offs"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"}


def _extract_scratch_offs(html: str) -> list[dict]:
    """Extract scratchOffs array from Next.js RSC hydration payload."""
    for chunk_m in re.finditer(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.DOTALL):
        chunk = chunk_m.group(1)
        if "scratchOffs" not in chunk and "scratchOff" not in chunk:
            continue
        try:
            unescaped = chunk.encode().decode("unicode_escape")
        except Exception:
            continue

        # Find "scratchOffs":[...] or "scratchOff":{...}
        for key in ('"scratchOffs":', '"scratchOff":'):
            idx = unescaped.find(key)
            if idx == -1:
                continue
            # Find the opening bracket/brace after the key
            val_start = idx + len(key)
            while val_start < len(unescaped) and unescaped[val_start] not in ('[', '{'):
                val_start += 1
            if val_start >= len(unescaped):
                continue
            open_c = unescaped[val_start]
            close_c = "]" if open_c == "[" else "}"
            depth = 0
            arr_end = val_start
            for i, c in enumerate(unescaped[val_start:], val_start):
                if c == open_c:
                    depth += 1
                elif c == close_c:
                    depth -= 1
                    if depth == 0:
                        arr_end = i + 1
                        break
            if arr_end == val_start:
                continue
            try:
                parsed = json.loads(unescaped[val_start:arr_end])
            except Exception:
                continue
            if isinstance(parsed, list) and parsed:
                return parsed
            if isinstance(parsed, dict):
                return [parsed]
    return []


def _is_active(game: dict) -> bool:
    now = datetime.now(timezone.utc)
    end = game.get("endDate", "")
    if not end:
        return True
    try:
        end_dt = datetime.fromisoformat(end)
        return end_dt > now
    except Exception:
        return True


def _parse_game_page(slug: str) -> list[dict]:
    """Return prizeDetails list from individual game page."""
    url = f"{_LIST_URL}/{slug}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception:
        return []
    items = _extract_scratch_offs(r.text)
    for item in items:
        if item.get("slug") == slug or str(item.get("gameNumber", "")) in slug:
            return item.get("prizeDetails", [])
        # Also try the first item if only one game is returned
        if len(items) == 1:
            return item.get("prizeDetails", [])
    return []


def scrape() -> list[dict]:
    r = requests.get(_LIST_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()

    all_games = _extract_scratch_offs(r.text)
    active = [g for g in all_games if _is_active(g) and g.get("ticketPrice", 0) > 0]

    tickets = []
    for g in active:
        slug = g.get("slug", "")
        name = g.get("title", "")
        price = float(g.get("ticketPrice", 0))
        game_num = str(g.get("gameNumber", ""))
        top_prize = g.get("topPrize", 0)
        odds_raw = g.get("odds", 0)
        odds_m = re.search(r"[\d.]+", str(odds_raw))
        overall_odds = float(odds_m.group(0)) if odds_m else 0.0

        if not name or price <= 0:
            continue

        # Image URL from RSC payload (Contentful CDN)
        img_obj = g.get("image") or g.get("appImage") or {}
        image_url = img_obj.get("url") if isinstance(img_obj, dict) else None

        # Fetch individual page for full prize tier data
        prize_details = _parse_game_page(slug)
        time.sleep(0.4)

        if prize_details:
            tiers = [
                {
                    "prize": pd["prize"],
                    "remaining": pd["remainingPrizes"],
                    "total": pd["totalPrizes"],
                }
                for pd in prize_details
                if pd.get("prize", 0) > 0
            ]
        else:
            # Fallback: top prize only using list page data
            tiers = [{"prize": top_prize, "remaining": 1, "total": 1}]

        if not tiers:
            continue

        tiers.sort(key=lambda t: t["prize"], reverse=True)

        # Estimate total/remaining tickets from overall odds and prize counts
        total_prizes = sum(t["total"] for t in tiers)
        remaining_prizes = sum(t["remaining"] for t in tiers)
        if overall_odds > 0 and total_prizes > 0:
            total_tickets = round(total_prizes * overall_odds)
            remaining_tickets = round(remaining_prizes * overall_odds)
        else:
            total_prize_value = sum(t["prize"] * t["total"] for t in tiers)
            total_tickets = int(total_prize_value / (0.65 * price)) if price > 0 else 0
            remaining_tickets = int(total_tickets * remaining_prizes / total_prizes) if total_prizes else 0

        tickets.append({
            "name": name,
            "price": price,
            "totalTickets": total_tickets,
            "remainingTickets": remaining_tickets,
            "gameNumber": game_num,
            "tiers": tiers,
            **({"imageUrl": image_url} if image_url else {}),
        })

    return tickets

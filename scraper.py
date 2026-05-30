import time
import random
import requests
from datetime import datetime
from database import Session, PainPoint, init_db

# Rotate User-Agents to avoid Reddit 403
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    }

# Keywords that signal frustration / unmet needs
PAIN_KEYWORDS = [
    # Explicit wishes
    "i wish there was", "wish there was", "i wish someone", "there should be",
    "why is there no", "why isn't there", "why doesn't exist",
    # Frustration
    "so frustrating", "it's annoying", "drives me crazy", "makes no sense",
    "hate that", "hate when", "tired of", "sick of",
    # Unmet needs
    "i need something that", "can't find a", "no good app for",
    "no solution for", "still no way to", "impossible to find",
    "looking for a tool", "looking for software", "does anyone know of",
    "is there an app", "is there a tool", "is there a way to",
    # Problems
    "struggle with", "pain in the", "biggest problem with",
    "anyone know how to fix", "keeps breaking", "doesn't work well",
    "workaround for", "manual process", "wasting hours",
    "takes forever to", "no easy way to",
]

SUBREDDITS = [
    "entrepreneur", "smallbusiness", "productivity", "personalfinance",
    "startups", "SaaS", "lifehacks", "technology", "freelance",
    "marketing", "webdev", "business", "nocode", "Entrepreneur",
    "digitalnomad", "passive_income",
]

# Keyword-based search queries for Reddit search
SEARCH_QUERIES = [
    "I wish there was an app",
    "why is there no tool for",
    "can't find a good solution",
    "so frustrated with",
    "there should be a service",
    "looking for software that",
    "wasting so much time on",
    "manual process that should be automated",
]


def text_has_pain_keyword(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in PAIN_KEYWORDS)


def safe_get(url: str, retries: int = 3) -> requests.Response | None:
    """GET with retry, rotating UA and exponential backoff."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=get_headers(), timeout=15)
            if resp.status_code == 429:
                wait = 10 * (attempt + 1)
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            if resp.status_code == 403:
                time.sleep(3 + attempt * 2)
                continue
            return resp
        except requests.RequestException as e:
            print(f"    Request error: {e}")
            time.sleep(2)
    return None


# ── Reddit via Arctic Shift (free public archive, no auth needed) ─────────────
# Arctic Shift mirrors all public Reddit data and has no 403 issues.

ARCTIC = "https://arctic-shift.photon-reddit.com/api"


def _arctic_save(session, post: dict) -> bool:
    """Save one Arctic Shift post to DB if it qualifies."""
    pid = post.get("id")
    if not pid or session.get(PainPoint, f"r_{pid}"):
        return False

    title  = post.get("title", "")
    body   = post.get("selftext", "") or ""
    sub    = post.get("subreddit", "unknown")
    score  = int(post.get("score") or 0)

    if body in ("[removed]", "[deleted]"):
        body = ""

    # Accept post if it has pain keywords OR decent score (Arctic Shift posts may be older with votes)
    if not text_has_pain_keyword(f"{title} {body}") and score < 2:
        return False

    created = post.get("created_utc") or post.get("created", 0)
    try:
        created_dt = datetime.utcfromtimestamp(float(created))
    except Exception:
        created_dt = datetime.utcnow()

    pp = PainPoint(
        id=f"r_{pid}",
        source=f"r/{sub}",
        author=post.get("author", "[deleted]"),
        title=title,
        body=body[:3000],
        url=f"https://reddit.com{post.get('permalink', f'/r/{sub}/comments/{pid}/')}",
        upvotes=score,
        num_comments=int(post.get("num_comments") or 0),
        created_at=created_dt,
    )
    session.add(pp)
    return True


def scrape_reddit_feed(subreddits: list[str], limit: int = 100) -> dict:
    """Search each subreddit for pain-point keywords via Arctic Shift."""
    from datetime import date, timedelta
    init_db()
    session = Session()
    results = {}

    after = (date.today() - timedelta(days=425)).strftime("%Y-%m-%d")

    # Use targeted keyword search — much better signal than generic feed
    keywords = [
        "I wish", "wish there was", "why is there no",
        "so frustrated", "there should be", "struggling with",
        "can't find", "hate that", "no solution", "wasting time",
    ]

    for sub in subreddits:
        saved = 0
        for kw in keywords[:6]:
            url = (f"{ARCTIC}/posts/search"
                   f"?subreddit={sub}&title={requests.utils.quote(kw)}"
                   f"&limit=25&after={after}")
            resp = safe_get(url)
            if not resp or resp.status_code != 200:
                continue
            for post in (resp.json().get("data") or []):
                if _arctic_save(session, post):
                    saved += 1
            try:
                session.commit()
            except Exception:
                session.rollback()
            time.sleep(0.3)

        results[sub] = saved
        print(f"  r/{sub} -> {saved} new posts")

    session.close()
    return results


def scrape_reddit_search(subreddits: list[str]) -> int:
    """Search subreddits for pain-point keywords via Arctic Shift."""
    from datetime import date, timedelta
    init_db()
    session = Session()
    saved = 0

    after = (date.today() - timedelta(days=425)).strftime("%Y-%m-%d")

    for sub in subreddits[:8]:
        for query in SEARCH_QUERIES[:5]:
            url = (f"{ARCTIC}/posts/search"
                   f"?subreddit={sub}&title={requests.utils.quote(query)}"
                   f"&limit=25&after={after}")
            resp = safe_get(url)
            if not resp or resp.status_code != 200:
                continue
            for post in (resp.json().get("data") or []):
                if _arctic_save(session, post):
                    saved += 1
            try:
                session.commit()
            except Exception:
                session.rollback()
            time.sleep(0.3)

    session.close()
    print(f"  Reddit keyword search -> {saved} new targeted posts")
    return saved


# ── Hacker News ───────────────────────────────────────────────────────────────

HN_BASE = "https://hacker-news.firebaseio.com/v0"
HN_ALGOLIA = "https://hn.algolia.com/api/v1"

HN_SEARCH_QUERIES = [
    "I wish", "why is there no", "frustrated with", "there should be",
    "can't find", "struggling with", "annoying", "hate that",
    "looking for tool", "no good solution", "wasting time",
]


def scrape_hn_ask(max_posts: int = 300) -> int:
    """Scrape Ask HN stories via Firebase API."""
    init_db()
    session = Session()
    saved = 0

    resp = safe_get(f"{HN_BASE}/askstories.json")
    if not resp:
        return 0

    story_ids = resp.json()[:max_posts]
    print(f"  Fetching {len(story_ids)} Ask HN stories...")

    for sid in story_ids:
        pid = f"hn_{sid}"
        if session.get(PainPoint, pid):
            continue

        resp = safe_get(f"{HN_BASE}/item/{sid}.json")
        if not resp:
            continue

        try:
            item = resp.json()
        except Exception:
            continue

        if not item or item.get("dead") or item.get("deleted"):
            continue

        # Skip posts older than 2 years
        import time as _time
        if item.get("time", 0) < _time.time() - (2 * 365 * 24 * 3600):
            continue

        title = item.get("title", "")
        body = item.get("text", "") or ""
        combined = f"{title} {body}"

        if not text_has_pain_keyword(combined) and item.get("score", 0) < 5:
            continue

        pp = PainPoint(
            id=pid,
            source="hackernews",
            author=item.get("by", "unknown"),
            title=title,
            body=body[:3000],
            url=f"https://news.ycombinator.com/item?id={sid}",
            upvotes=item.get("score", 0),
            num_comments=len(item.get("kids", [])),
            created_at=datetime.utcfromtimestamp(item.get("time", 0)),
        )
        session.add(pp)
        saved += 1
        time.sleep(0.15)

    try:
        session.commit()
    except Exception:
        session.rollback()

    session.close()
    print(f"  HackerNews Ask -> {saved} new posts")
    return saved


def scrape_hn_search() -> int:
    """Search HN via Algolia for pain-point keywords — last 2 years only."""
    init_db()
    session = Session()
    saved = 0

    # Only fetch posts from the last 2 years (avoids dead "Sorry." links)
    from datetime import timezone
    import time as _time
    cutoff = int(_time.time()) - (2 * 365 * 24 * 3600)

    for query in HN_SEARCH_QUERIES:
        url = (f"{HN_ALGOLIA}/search?query={requests.utils.quote(query)}"
               f"&tags=ask_hn&hitsPerPage=30&numericFilters=created_at_i>{cutoff}")
        resp = safe_get(url)
        if not resp or resp.status_code != 200:
            continue

        try:
            hits = resp.json().get("hits", [])
        except Exception:
            continue

        for hit in hits:
            pid = f"hn_{hit.get('objectID')}"
            if session.get(PainPoint, pid):
                continue

            title = hit.get("title", "")
            body = hit.get("story_text", "") or hit.get("comment_text", "") or ""

            pp = PainPoint(
                id=pid,
                source="hackernews",
                author=hit.get("author", "unknown"),
                title=title,
                body=body[:3000],
                url=f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                upvotes=hit.get("points", 0),
                num_comments=hit.get("num_comments", 0),
                created_at=datetime.utcfromtimestamp(hit.get("created_at_i", 0)),
            )
            session.add(pp)
            saved += 1

        try:
            session.commit()
        except Exception:
            session.rollback()

        time.sleep(0.5)

    session.close()
    print(f"  HackerNews search -> {saved} new posts")
    return saved


# ── YouTube (Shorts + Videos) ─────────────────────────────────────────────────

YT_SEARCH_QUERIES = [
    "I wish there was an app for",
    "why is there no solution for",
    "so frustrated with",
    "there should be a tool",
    "nobody has solved",
    "biggest problem with",
    "I hate that there's no",
    "why can't anyone fix",
    "this problem needs to be solved",
    "struggling with this every day",
]


def _yt_fetch_video_ids(queries: list, suffix: str, max_videos: int) -> list:
    """Search YouTube and return video IDs. suffix = '#shorts' or ''."""
    try:
        import yt_dlp
    except ImportError:
        return []

    ydl_opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "noplaylist": True}
    video_ids = []

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for query in queries:
            search = f"ytsearch5:{query} {suffix}".strip()
            try:
                info = ydl.extract_info(search, download=False)
                for entry in (info.get("entries", []) if info else []):
                    vid_id = entry.get("id")
                    if vid_id and vid_id not in video_ids:
                        video_ids.append(vid_id)
                        if len(video_ids) >= max_videos:
                            return video_ids
            except Exception as e:
                print(f"    YT search error: {e}")
            time.sleep(0.8)

    return video_ids


def _yt_scrape_comments(video_ids: list, source_label: str,
                        comments_per_video: int = 80) -> int:
    """Download top comments from a list of video IDs and save them.
    For YouTube we accept all comments with 2+ likes — Claude filters later."""
    try:
        from youtube_comment_downloader import YoutubeCommentDownloader, SORT_BY_POPULAR
    except ImportError:
        return 0

    init_db()
    session = Session()
    saved = 0
    dl = YoutubeCommentDownloader()

    for vid_id in video_ids:
        url = f"https://www.youtube.com/watch?v={vid_id}"
        count = 0
        try:
            for comment in dl.get_comments_from_url(url, sort_by=SORT_BY_POPULAR):
                if count >= comments_per_video:
                    break

                text = comment.get("text", "").strip()
                raw_votes = comment.get("votes", 0) or 0
                try:
                    votes = int(str(raw_votes).replace("K","000").replace("M","000000").replace(".","").replace(",",""))
                except Exception:
                    votes = 0

                # Accept if has pain keyword OR has decent likes (let Claude decide)
                if not text or (not text_has_pain_keyword(text) and votes < 2):
                    count += 1
                    continue

                cid = f"yt_{vid_id}_{comment.get('cid', count)}"
                if session.get(PainPoint, cid):
                    count += 1
                    continue

                pp = PainPoint(
                    id=cid,
                    source=source_label,
                    author=comment.get("author", "unknown"),
                    title=text[:120],
                    body=text[:3000],
                    url=url,
                    upvotes=votes,
                    num_comments=0,
                    created_at=datetime.utcnow(),
                )
                session.add(pp)
                saved += 1
                count += 1

            session.commit()
            time.sleep(1.2)

        except Exception as e:
            print(f"    Error on {vid_id}: {e}")
            session.rollback()

    session.close()
    return saved


def scrape_youtube_shorts(max_videos: int = 15, comments_per_video: int = 100) -> int:
    print(f"  Searching {max_videos} YouTube Shorts...")
    ids = _yt_fetch_video_ids(YT_SEARCH_QUERIES[:6], "#shorts", max_videos)
    print(f"  Found {len(ids)} Shorts — scraping comments...")
    count = _yt_scrape_comments(ids, "youtube_shorts", comments_per_video)
    print(f"  YouTube Shorts -> {count} new comments saved")
    return count


def scrape_youtube_videos(max_videos: int = 15, comments_per_video: int = 100) -> int:
    print(f"  Searching {max_videos} YouTube videos...")
    ids = _yt_fetch_video_ids(YT_SEARCH_QUERIES, "", max_videos)
    print(f"  Found {len(ids)} videos — scraping comments...")
    count = _yt_scrape_comments(ids, "youtube_videos", comments_per_video)
    print(f"  YouTube Videos -> {count} new comments saved")
    return count


# ── Product Hunt (Algolia — no API key needed) ────────────────────────────────

def scrape_producthunt(max_posts: int = 100) -> int:
    """Scrape Product Hunt discussions via Algolia — no API key needed."""
    init_db()
    session = Session()
    saved = 0

    PH_QUERIES = [
        "I wish", "why doesn't", "frustrated with", "there should be",
        "struggling with", "no good tool", "wish there was",
    ]

    for query in PH_QUERIES:
        url = (f"https://uj3wpecia4-dsn.algolia.net/1/indexes/Post_production/query"
               f"?x-algolia-application-id=UJ3WPECIA4"
               f"&x-algolia-api-key=8afe8d6bdb66e89e6bc5eb67e31c7d9b")

        try:
            resp = requests.post(url, json={"query": query, "hitsPerPage": 20}, timeout=15,
                               headers={"Content-Type": "application/json"})
            if resp.status_code != 200:
                continue
            hits = resp.json().get("hits", [])
        except Exception as e:
            print(f"    PH error: {e}")
            continue

        for hit in hits:
            pid = f"ph_{hit.get('objectID','')}"
            if session.get(PainPoint, pid):
                continue

            name = hit.get("name", "")
            tagline = hit.get("tagline", "") or ""
            desc = hit.get("description", "") or ""
            body = f"{tagline}\n{desc}".strip()

            if not body and not name:
                continue

            pp = PainPoint(
                id=pid,
                source="producthunt",
                author=hit.get("user", {}).get("name", "unknown") if isinstance(hit.get("user"), dict) else "unknown",
                title=name[:200],
                body=body[:3000],
                url=f"https://producthunt.com/posts/{hit.get('slug', '')}",
                upvotes=hit.get("votesCount", 0) or 0,
                num_comments=hit.get("commentsCount", 0) or 0,
                created_at=datetime.utcnow(),
            )
            session.add(pp)
            saved += 1

        try:
            session.commit()
        except Exception:
            session.rollback()
        time.sleep(0.3)

    session.close()
    print(f"  Product Hunt -> {saved} new posts")
    return saved


def mark_trending():
    """Mark posts as trending if they appeared in the last 7 days and have urgency >= 6."""
    from datetime import datetime, timedelta
    init_db()
    session = Session()
    cutoff = datetime.utcnow() - timedelta(days=7)
    updated = (session.query(PainPoint)
        .filter(PainPoint.scraped_at >= cutoff, PainPoint.urgency_score >= 6, PainPoint.is_pain_point == 1)
        .update({"trending": 1}))
    session.commit()
    session.close()
    print(f"  Marked {updated} posts as trending")
    return updated


# ── Main entry ────────────────────────────────────────────────────────────────

def run_scraper(
    subreddits: list[str] = None,
    limit: int = 100,
    include_reddit: bool = True,
    include_hn: bool = True,
    include_yt_shorts: bool = False,
    include_yt_videos: bool = False,
    include_ph: bool = False,
) -> dict:
    results = {}
    subs = subreddits or SUBREDDITS

    if include_reddit:
        print("Scraping Reddit feeds...")
        results.update(scrape_reddit_feed(subs, limit))
        print("Scraping Reddit search (targeted keywords)...")
        results["reddit_search"] = scrape_reddit_search(subs)

    if include_hn:
        print("Scraping Hacker News...")
        results["hn_ask"]    = scrape_hn_ask(max_posts=300)
        results["hn_search"] = scrape_hn_search()

    if include_yt_shorts:
        results["youtube_shorts"] = scrape_youtube_shorts()

    if include_yt_videos:
        results["youtube_videos"] = scrape_youtube_videos()

    if include_ph:
        print("Scraping Product Hunt...")
        results["producthunt"] = scrape_producthunt()

    return results


if __name__ == "__main__":
    run_scraper(["entrepreneur", "productivity", "smallbusiness"])

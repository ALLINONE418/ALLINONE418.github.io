import os
import json
import requests
from datetime import datetime, timezone, timedelta

# ─────────────────────────────────────────
# 在这里配置你想追踪的 YouTube 频道
# ─────────────────────────────────────────
CHANNELS = {
    "Bloomberg Markets":    "UCIALMKvObZNtJ6Rouzi4PYQ",
    "Bloomberg Technology": "UCrM7B7SL_g1edFOnmj-SDKg",
    "CNBC Television":      "UCvJJ_dzjViJCoLf5uKUTwoA",
    "CNBC International":   "UCo6Romania-LNr0D3BKwpMQtg",
    "Lex Fridman":          "UCSHZKyawb77ixDdsGog4iWA",
    "Y Combinator":         "UCcefcZRL2oaA_uBNeo5UNqg",
    "a16z":                 "UC9cn0TuPq4dnbTY-CBsm8XA",
}

KEEP_HOURS = 48          # 保留过去48小时的视频
MAX_PER_CHANNEL = 20     # 每个频道最多抓取条数

API_KEY = os.environ.get("YOUTUBE_API_KEY")
BASE_URL = "https://www.googleapis.com/youtube/v3"


def get_channel_uploads_playlist(channel_id):
    url = f"{BASE_URL}/channels"
    params = {"part": "contentDetails,snippet", "id": channel_id, "key": API_KEY}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    items = r.json().get("items", [])
    if not items:
        return None, None
    uploads_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    thumbnail = items[0]["snippet"]["thumbnails"].get("default", {}).get("url", "")
    return uploads_id, thumbnail


def get_videos_within_48h(playlist_id, cutoff):
    """从播放列表抓视频，只保留 cutoff 时间之后发布的"""
    url = f"{BASE_URL}/playlistItems"
    videos = []
    page_token = None

    while len(videos) < MAX_PER_CHANNEL:
        params = {
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": 10,
            "key": API_KEY,
        }
        if page_token:
            params["pageToken"] = page_token

        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()

        for item in data.get("items", []):
            snippet = item["snippet"]
            published_str = snippet.get("publishedAt", "")
            if not published_str:
                continue
            try:
                published_dt = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
            except:
                continue

            # 超过48小时就停止（播放列表按时间倒序排列）
            if published_dt < cutoff:
                return videos

            vid_id = snippet.get("resourceId", {}).get("videoId", "")
            if not vid_id:
                continue

            thumbs = snippet.get("thumbnails", {})
            thumb = (
                thumbs.get("maxres", {}).get("url") or
                thumbs.get("high", {}).get("url") or
                thumbs.get("medium", {}).get("url") or
                thumbs.get("default", {}).get("url") or ""
            )

            videos.append({
                "id": vid_id,
                "title": snippet.get("title", ""),
                "description": snippet.get("description", "")[:200],
                "thumbnail": thumb,
                "published_at": published_str,
                "url": f"https://www.youtube.com/watch?v={vid_id}",
                "embed_url": f"https://www.youtube.com/embed/{vid_id}",
            })

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return videos


def fetch_all():
    if not API_KEY:
        raise ValueError("YOUTUBE_API_KEY environment variable not set")

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=KEEP_HOURS)
    print(f"Fetching videos published after: {cutoff.isoformat()}")

    result = []
    for display_name, channel_id in CHANNELS.items():
        print(f"\nFetching: {display_name}")
        try:
            playlist_id, channel_thumb = get_channel_uploads_playlist(channel_id)
            if not playlist_id:
                print(f"  ⚠️  Channel not found")
                continue
            videos = get_videos_within_48h(playlist_id, cutoff)
            if videos:
                result.append({
                    "channel_name": display_name,
                    "channel_id": channel_id,
                    "channel_thumb": channel_thumb,
                    "videos": videos,
                })
                print(f"  ✅  {len(videos)} videos within 48h")
            else:
                print(f"  ℹ️  No videos in past 48h")
        except Exception as e:
            print(f"  ❌  Error: {e}")

    total = sum(len(ch["videos"]) for ch in result)
    output = {
        "updated_at": now.isoformat(),
        "keep_hours": KEEP_HOURS,
        "total_videos": total,
        "channels": result,
    }

    os.makedirs("data", exist_ok=True)
    with open("data/videos.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Saved — {len(result)} channels, {total} videos total (past 48h)")


if __name__ == "__main__":
    fetch_all()

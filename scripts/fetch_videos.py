import os
import json
import requests
from datetime import datetime, timezone

# ─────────────────────────────────────────
# 在这里配置你想追踪的 YouTube 频道
# 格式：{ "显示名称": "频道ID" }
# ─────────────────────────────────────────
CHANNELS = {
    "Bloomberg Markets": "UCIALMKvObZNtJ6Rouzi4PYQ",
    "Bloomberg Technology": "UCrM7B7SL_g1edFOnmj-SDKg",
    "CNBC Television":     "UCvJJ_dzjViJCoLf5uKUTwoA",
    "CNBC International":  "UCo6Romania-LNr0D3BKwpMQtg",
    "Lex Fridman":         "UCSHZKyawb77ixDdsGog4iWA",
    "Y Combinator":        "UCcefcZRL2oaA_uBNeo5UNqg",
    "a16z":                "UC9cn0TuPq4dnbTY-CBsm8XA",
}

# 每个频道抓取最新视频数量
VIDEOS_PER_CHANNEL = 3

API_KEY = os.environ.get("YOUTUBE_API_KEY")
BASE_URL = "https://www.googleapis.com/youtube/v3"


def get_channel_uploads_playlist(channel_id):
    """获取频道的上传播放列表 ID（uploads playlist）"""
    url = f"{BASE_URL}/channels"
    params = {
        "part": "contentDetails,snippet",
        "id": channel_id,
        "key": API_KEY,
    }
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    items = r.json().get("items", [])
    if not items:
        return None, None
    uploads_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    thumbnail = items[0]["snippet"]["thumbnails"].get("default", {}).get("url", "")
    return uploads_id, thumbnail


def get_latest_videos(playlist_id, max_results=3):
    """从播放列表获取最新视频"""
    url = f"{BASE_URL}/playlistItems"
    params = {
        "part": "snippet",
        "playlistId": playlist_id,
        "maxResults": max_results,
        "key": API_KEY,
    }
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    items = r.json().get("items", [])

    videos = []
    for item in items:
        snippet = item["snippet"]
        vid_id = snippet.get("resourceId", {}).get("videoId", "")
        if not vid_id:
            continue

        # 取最佳缩略图
        thumbs = snippet.get("thumbnails", {})
        thumb = (
            thumbs.get("maxres", {}).get("url")
            or thumbs.get("high", {}).get("url")
            or thumbs.get("medium", {}).get("url")
            or thumbs.get("default", {}).get("url")
            or ""
        )

        videos.append({
            "id": vid_id,
            "title": snippet.get("title", ""),
            "description": snippet.get("description", "")[:200],
            "thumbnail": thumb,
            "published_at": snippet.get("publishedAt", ""),
            "url": f"https://www.youtube.com/watch?v={vid_id}",
            "embed_url": f"https://www.youtube.com/embed/{vid_id}",
        })
    return videos


def fetch_all():
    if not API_KEY:
        raise ValueError("YOUTUBE_API_KEY environment variable not set")

    result = []
    for display_name, channel_id in CHANNELS.items():
        print(f"Fetching: {display_name} ({channel_id})")
        try:
            playlist_id, channel_thumb = get_channel_uploads_playlist(channel_id)
            if not playlist_id:
                print(f"  ⚠️  Channel not found: {channel_id}")
                continue
            videos = get_latest_videos(playlist_id, VIDEOS_PER_CHANNEL)
            result.append({
                "channel_name": display_name,
                "channel_id": channel_id,
                "channel_thumb": channel_thumb,
                "videos": videos,
            })
            print(f"  ✅  Got {len(videos)} videos")
        except Exception as e:
            print(f"  ❌  Error: {e}")

    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "channels": result,
    }

    os.makedirs("data", exist_ok=True)
    with open("data/videos.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Saved data/videos.json — {len(result)} channels")


if __name__ == "__main__":
    fetch_all()

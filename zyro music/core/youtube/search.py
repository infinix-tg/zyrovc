# ==============================================================================
# search.py - YouTube Search Manager
# ==============================================================================
# This file handles querying metadata from YouTube.
# Features:
# - Extracts single tracks and playlists via yt-dlp
# - Maintains a short-lived search cache for rapid lookups
# - Optimizes searches for high-quality audio
# ==============================================================================

import asyncio
import re
from dataclasses import replace
from HasiiMusic import config, logger
from HasiiMusic.helpers import Track, utils
import yt_dlp

class Searcher:
    def __init__(self, cookies_manager):
        self._cookies = cookies_manager
        self.search_cache = {}  # {"query_video": (result, timestamp)}

    def valid(self, url: str) -> bool:
        # Re-using the regex from utils - or we can just assume caller knows
        # Since this class needs it, we can import YouTubeUtils or take a valid_func
        from .utils import YouTubeUtils
        return YouTubeUtils().valid(url)

    async def search(self, query: str, m_id: int, music: bool = False) -> Track | None:
        cache_key = query
        current_time = asyncio.get_running_loop().time()

        if cache_key in self.search_cache:
            cached_result, cache_timestamp = self.search_cache[cache_key]
            if current_time - cache_timestamp < 600:  # 10 minutes
                fresh = replace(cached_result)
                fresh.message_id = m_id
                fresh.file_path = None
                fresh.user = None
                fresh.time = 0
                fresh.video = False
                return fresh

        if music and not query.lower().endswith("audio"):
            query = f"{query} Official Audio"
            
        try:
            if self.valid(query):
                def _extract():
                    cookie = self._cookies.get_cookies() if self._cookies.checked else None
                    ydl_opts = {
                        "quiet": True,
                        "noplaylist": True,
                        "extract_flat": "in_playlist",
                        "cookiefile": cookie
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        return ydl.extract_info(query, download=False)

                data = await asyncio.to_thread(_extract)
                if not data:
                    return None

                duration_sec = data.get("duration")
                is_live = data.get("is_live", False)
                if duration_sec is None and is_live:
                    duration = "LIVE"
                    duration_sec = 0
                else:
                    duration = utils.format_duration(int(duration_sec)) if duration_sec else "0:00"

                track = Track(
                    id=data.get("id"),
                    channel_name=data.get("uploader") or data.get("channel", ""),
                    duration=duration,
                    duration_sec=int(duration_sec) if duration_sec else 0,
                    message_id=m_id,
                    title=(data.get("title") or "")[:25],
                    thumbnail=data.get("thumbnail") or "",
                    url=data.get("webpage_url") or query,
                    view_count=str(data.get("view_count", "")),
                    is_live=is_live,
                )
            else:
                def _extract_search():
                    cookie = self._cookies.get_cookies() if self._cookies.checked else None
                    ydl_opts = {
                        "quiet": True,
                        "extract_flat": True,
                        "cookiefile": cookie
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        return ydl.extract_info(f"ytsearch1:{query}", download=False)
                        
                results = await asyncio.to_thread(_extract_search)
                
                if not results or "entries" not in results or not results["entries"]:
                    return None
                    
                data = results["entries"][0]
                duration_sec = data.get("duration")
                is_live = data.get("is_live", False)
                if duration_sec is None and is_live:
                    duration = "LIVE"
                    duration_sec = 0
                else:
                    duration = utils.format_duration(int(duration_sec)) if duration_sec else "0:00"

                track = Track(
                    id=data.get("id"),
                    channel_name=data.get("uploader") or data.get("channel", ""),
                    duration=duration,
                    duration_sec=int(duration_sec) if duration_sec else 0,
                    message_id=m_id,
                    title=(data.get("title") or "")[:25],
                    thumbnail=data.get("thumbnails", [{}])[-1].get("url", "").split("?")[0] if data.get("thumbnails") else "",
                    url=data.get("url") or data.get("webpage_url") or f"https://youtube.com/watch?v={data.get('id')}",
                    view_count=str(data.get("view_count", "")),
                    is_live=is_live,
                )

            self.search_cache[cache_key] = (track, current_time)
            if len(self.search_cache) > 100:
                oldest_key = min(self.search_cache.keys(),
                                 key=lambda k: self.search_cache[k][1])
                del self.search_cache[oldest_key]

            return replace(track)
            
        except Exception as e:
            logger.warning(f"YouTube search failed for '{query}': {e}")
            return None

    async def playlist(self, limit: int, user: str, url: str) -> list[Track]:
        try:
            def _extract_playlist():
                cookie = self._cookies.get_cookies() if self._cookies.checked else None
                ydl_opts = {
                    "quiet": True,
                    "extract_flat": "in_playlist",
                    "cookiefile": cookie
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=False)
                    
            plist = await asyncio.to_thread(_extract_playlist)
            tracks = []

            if not plist or "entries" not in plist or not plist["entries"]:
                return []

            for data in plist["entries"][:limit]:
                try:
                    duration_sec = data.get("duration")
                    is_live = data.get("is_live", False)
                    if duration_sec is None and is_live:
                        duration = "LIVE"
                        duration_sec = 0
                    else:
                        duration = utils.format_duration(int(duration_sec)) if duration_sec else "0:00"

                    track = Track(
                        id=data.get("id", ""),
                        channel_name=data.get("uploader") or data.get("channel", ""),
                        duration=duration,
                        duration_sec=int(duration_sec) if duration_sec else 0,
                        title=(data.get("title", "Unknown")[:25]),
                        thumbnail=data.get("thumbnails", [{}])[-1].get("url", "").split("?")[0] if data.get("thumbnails") else "",
                        url=data.get("url") or data.get("webpage_url") or f"https://youtube.com/watch?v={data.get('id')}",
                        user=user,
                        view_count="",
                    )
                    tracks.append(track)
                except Exception:
                    continue

            return tracks
        except Exception as e:
            logger.warning(f"YouTube playlist extraction failed for '{url}': {e}")
            return []

    async def related(self, seed, exclude: set, user: str = "Autoplay") -> Track | None:
        """Pick a song similar to `seed` for autoplay.

        Uses YouTube's own Mix for the seed video (the same "up next" radio
        YouTube plays), and falls back to a plain search on the title. Songs in
        `exclude` (already played), live streams and anything over the duration
        limit are skipped.
        """
        seed_id = getattr(seed, "id", "") or ""
        is_yt_id = bool(re.fullmatch(r"[A-Za-z0-9_-]{11}", seed_id))
        title = getattr(seed, "title", "") or ""
        channel = getattr(seed, "channel_name", "") or ""

        sources = []
        if is_yt_id:
            sources.append(
                (f"https://www.youtube.com/watch?v={seed_id}&list=RD{seed_id}", 16)
            )
        if title:
            sources.append((f"ytsearch10:{title} {channel} similar songs".strip(), 10))

        for src, count in sources:
            def _extract(src=src, count=count):
                cookie = self._cookies.get_cookies() if self._cookies.checked else None
                opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "extract_flat": True,
                    "skip_download": True,
                    "playlistend": count,
                    "cookiefile": cookie,
                }
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(src, download=False)

            try:
                data = await asyncio.wait_for(asyncio.to_thread(_extract), timeout=25)
            except Exception as e:
                logger.debug(f"Autoplay source failed ({src[:60]}): {e}")
                continue

            for entry in (data or {}).get("entries") or []:
                vid = entry.get("id") or ""
                dur = entry.get("duration") or 0
                if (
                    not re.fullmatch(r"[A-Za-z0-9_-]{11}", vid)
                    or vid in exclude
                    or entry.get("is_live")
                    or dur < 60
                    or dur > min(config.DURATION_LIMIT, 20 * 60)
                ):
                    continue
                thumbs = entry.get("thumbnails") or []
                return Track(
                    id=vid,
                    channel_name=entry.get("uploader") or entry.get("channel") or "",
                    duration=utils.format_duration(int(dur)),
                    duration_sec=int(dur),
                    title=(entry.get("title") or "Unknown")[:25],
                    thumbnail=(thumbs[-1].get("url", "").split("?")[0] if thumbs else ""),
                    url=entry.get("url") or f"https://youtube.com/watch?v={vid}",
                    user=user,
                    view_count="",
                )
        return None

import asyncio
from urllib.parse import urlparse

from ....utils.logger import logger
from .base import PlatformHandler, StreamData

try:
    import streamlink

    streamlink_session_factory = streamlink.Streamlink
except ImportError:
    streamlink = None

# Map StreamCap quality presets to streamlink quality candidates, tried in order.
QUALITY_CANDIDATES = {
    "OD": ["best"],
    "UHD": ["2160p", "1440p", "best"],
    "HD": ["1080p", "720p", "best"],
    "SD": ["480p", "360p", "best"],
    "LD": ["360p", "240p", "worst"],
}


def _pick_stream(streams: dict, record_quality: str | None):
    """Pick the preferred stream variant from a streamlink streams mapping."""
    non_audio = {k: v for k, v in streams.items() if k != "audio" and not k.endswith("_unselected")}
    for name in QUALITY_CANDIDATES.get(record_quality or "OD", ["best"]):
        if name in non_audio:
            return non_audio[name]
    # Fall back to the highest resolution key like "1080p" / "720p60".
    resolution_keys = [k for k in non_audio if k.rstrip("0123456789") == "p" and k[:-1].isdigit()]
    if resolution_keys:
        best_key = max(resolution_keys, key=lambda k: int(k[:-1]))
        return non_audio[best_key]
    return non_audio.get("best") or non_audio.get("worst")


class StreamLinkFallbackHandler(PlatformHandler):
    """Fallback extractor for live URLs that no built-in platform handler matches.

    Uses the optional ``streamlink`` dependency to resolve the stream. It is
    never registered in the URL-pattern registry; it is invoked explicitly from
    ``stream_manager.fetch_stream`` when no built-in handler matched."""

    platform = "streamlink"

    def __init__(
        self,
        proxy: str | None = None,
        cookies: str | None = None,
        record_quality: str | None = None,
        platform: str | None = None,
    ) -> None:
        super().__init__(proxy, cookies, record_quality, platform)
        self._session = None

    def _get_session(self):
        if streamlink is None:
            return None
        if self._session is None:
            try:
                self._session = streamlink_session_factory()
            except Exception as e:
                logger.error(f"Failed to create streamlink session: {e}")
        return self._session

    async def get_stream_info(self, live_url: str) -> StreamData | None:
        session = self._get_session()
        if session is None:
            logger.info("streamlink is not installed, skip fallback extraction (optional: pip install streamlink)")
            return None

        try:
            # streamlink resolves plugins with blocking I/O, keep it off the event loop.
            streams = await asyncio.to_thread(session.streams, live_url)
        except Exception as e:
            logger.warning(f"streamlink fallback failed for {live_url}: {e}")
            return None

        if not streams:
            logger.info(f"streamlink fallback found no stream: {live_url}")
            return None

        stream = _pick_stream(streams, self.record_quality)
        if stream is None or not getattr(stream, "url", None):
            logger.warning(f"streamlink fallback found no usable stream URL: {live_url}")
            return None

        stream_url = stream.url
        anchor_name = urlparse(live_url).netloc or "StreamLink"
        stream_data = StreamData(
            platform="StreamLink",
            anchor_name=anchor_name,
            is_live=True,
            record_url=stream_url,
        )
        if ".m3u8" in stream_url:
            stream_data.m3u8_url = stream_url
        elif ".flv" in stream_url:
            stream_data.flv_url = stream_url
        logger.info(f"streamlink fallback resolved stream for {anchor_name}: {stream_url[:80]}")
        return stream_data

import asyncio
import hashlib
import logging
import os
import re
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import aiofiles
from cachetools import TTLCache
from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

dotenv_path = find_dotenv()
load_dotenv(dotenv_path)
CUSTOM_VIDEO_ROOT_DIR = os.getenv("CUSTOM_VIDEO_ROOT_DIR")
VIDEO_API_PORT = os.getenv("VIDEO_API_PORT") or 6007

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_VIDEO_ROOT_DIR = Path(os.path.split(os.path.realpath(sys.argv[0]))[0]).parent.parent / "downloads"
VIDEO_DIR = Path(CUSTOM_VIDEO_ROOT_DIR or DEFAULT_VIDEO_ROOT_DIR)
os.makedirs(VIDEO_DIR, exist_ok=True)

VIDEO_META_CACHE = TTLCache(maxsize=50, ttl=300)
CHUNK_CACHE = TTLCache(maxsize=25, ttl=60)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if not VIDEO_DIR.exists():
        logger.error(f"Video directory does not exist: {VIDEO_DIR}")
        raise RuntimeError(f"Video directory does not exist: {VIDEO_DIR}")
    _app.mount("/api/videos", StaticFiles(directory=VIDEO_DIR), name="videos")
    yield

    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    _app.mount("/api/videos", StaticFiles(directory=None))
    logger.info("Shutting down the application.")


app = FastAPI(lifespan=lifespan)


def validate_filename(filename: str):
    if re.search(r"[\\/]", filename):
        raise HTTPException(status_code=400, detail="Invalid filename")


@app.get("/api/videos")
async def get_video(request: Request, filename: str = Query(...), subfolder: str | None = None):

    cache_key = f"{filename}-{subfolder}"
    if meta := VIDEO_META_CACHE.get(cache_key):
        if_none_match = request.headers.get("If-None-Match")
        if_modified_since = request.headers.get("If-Modified-Since")

        if if_none_match and if_none_match == meta["etag"]:
            return Response(status_code=304)

        if if_modified_since:
            last_modified = datetime.fromisoformat(meta["last_modified"])
            if datetime.strptime(if_modified_since, "%a, %d %b %Y %H:%M:%S GMT") >= last_modified:
                return Response(status_code=304)

    try:
        validate_filename(filename)
        if subfolder:
            video_path = VIDEO_DIR / subfolder / filename
        else:
            video_path = VIDEO_DIR / filename

    except Exception as e:
        logger.exception("Invalid filename or subfolder")
        raise e

    if not video_path.is_file():
        logger.error(f"File not found: {video_path}")
        raise HTTPException(status_code=404, detail="Video file not found")

    # Prevent path traversal attacks
    try:
        video_path.relative_to(VIDEO_DIR)
    except ValueError:
        logger.exception(f"Path traversal attempt: {video_path}")
        raise HTTPException(status_code=400, detail="Invalid file path")

    stat = video_path.stat()
    file_size = stat.st_size
    last_modified = datetime.fromtimestamp(stat.st_mtime).isoformat()
    etag = hashlib.md5(f"{file_size}-{last_modified}".encode()).hexdigest()

    VIDEO_META_CACHE[cache_key] = {"etag": etag, "last_modified": last_modified, "file_size": file_size}

    # Parse Range header
    range_header = request.headers.get("Range")
    if range_header:
        start, end = range_header.replace("bytes=", "").split("-")
        start = int(start)
        end = int(end) if end else file_size - 1

        if start >= file_size or end >= file_size:
            logger.error(f"Invalid range request: {range_header}, file size: {file_size}")
            raise HTTPException(status_code=416, detail="Requested range not satisfiable")

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(end - start + 1),
            "Content-Type": "video/mp4",
        }
        return StreamingResponse(
            file_sender_range(video_path, start, end),
            status_code=206,
            headers=headers,
        )

    # If no Range header, return the whole file
    headers = {
        "Content-Length": str(file_size),
        "Content-Type": "video/mp4",
        "Cache-Control": "public, max-age=300",
        "ETag": etag,
        "Last-Modified": datetime.fromisoformat(last_modified).strftime("%a, %d %b %Y %H:%M:%S GMT"),
    }
    try:
        return StreamingResponse(file_sender(video_path), headers=headers)
    except Exception:
        logger.exception("Streaming error")
        raise HTTPException(status_code=500, detail="Internal Server Error")


# Async file sender (full content)
async def file_sender(video_path: Path):
    async with aiofiles.open(video_path, "rb") as file:
        while True:
            chunk = await file.read(65536)
            if not chunk:
                break
            yield chunk


# Async file sender (range content)
async def file_sender_range(video_path: Path, start: int, end: int):
    cache_key = f"{video_path.name}-{start}-{end}"

    if cached := CHUNK_CACHE.get(cache_key):
        yield cached
        return

    async with aiofiles.open(video_path, "rb") as file:
        await file.seek(start)
        chunks = []
        while start <= end:
            chunk_size = min(65536, end - start + 1)
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            chunks.append(chunk)
            start += len(chunk)

        full_chunk = b"".join(chunks)
        if len(full_chunk) < 1024 * 1024:
            CHUNK_CACHE[cache_key] = full_chunk
        yield full_chunk


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(VIDEO_API_PORT), log_level="debug")

#!/usr/bin/env python3
"""YouTube search, persistent content blocks, and web-triggered downloads."""
from __future__ import annotations

import json
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path

from library import ROOT, load_config
from whytea import build_command, find_ytdlp

BLOCKS_PATH = ROOT / "blocked_content.json"
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,}$")


def load_blocks() -> dict:
    try:
        data = json.loads(BLOCKS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    videos = data.get("videos", [])
    channels = data.get("channels", [])
    return {
        "videos": videos if isinstance(videos, list) else [],
        "channels": channels if isinstance(channels, list) else [],
    }


def save_blocks(data: dict) -> None:
    tmp = BLOCKS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(BLOCKS_PATH)


def _safe_proxy(proxy: str | None) -> str | None:
    if not proxy:
        return None
    proxy = str(proxy).strip()
    if not proxy:
        return None
    if not re.fullmatch(r"(?:socks5h?|https?)://[A-Za-z0-9._:-]+", proxy):
        raise ValueError("Proxy must look like socks5://127.0.0.1:10808 or http://host:port")
    return proxy


def _base_ytdlp_args(proxy: str | None = None) -> list[str]:
    cfg = load_config()
    args = [
        find_ytdlp(),
        "--no-warnings",
        "--ignore-errors",
        "--extractor-args", "youtube:player_js_variant=tv",
        "--remote-components", "ejs:npm",
    ]
    browser = str(cfg.get("cookies_from_browser", "")).strip()
    if browser:
        args += ["--cookies-from-browser", browser]
    if proxy:
        args += ["--proxy", proxy]
    return args


def search_videos(query: str, limit: int = 20, proxy: str | None = None) -> list[dict]:
    query = str(query).strip()
    if not query:
        raise ValueError("Enter a search query.")
    limit = max(1, min(int(limit), 50))
    proxy = _safe_proxy(proxy)
    command = _base_ytdlp_args(proxy) + [
        "--flat-playlist", "--dump-single-json", "--skip-download",
        "--playlist-end", str(limit), "ytsearch" + str(limit) + ":" + query,
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=90,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("YouTube search timed out after 90 seconds.")
    except OSError as exc:
        raise RuntimeError("Could not start yt-dlp: " + str(exc))
    if result.returncode and not result.stdout.strip():
        raise RuntimeError((result.stderr or "yt-dlp search failed").strip()[-3000:])
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("yt-dlp returned invalid search data: " + str(exc))
    entries = payload.get("entries", []) if isinstance(payload, dict) else []
    blocks = load_blocks()
    blocked_videos = set(str(x.get("id", "")) for x in blocks["videos"] if isinstance(x, dict))
    blocked_channels = set(str(x.get("id", "")) for x in blocks["channels"] if isinstance(x, dict))
    found = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        video_id = str(item.get("id") or "")
        if not ID_RE.fullmatch(video_id) or video_id in blocked_videos:
            continue
        channel_id = str(item.get("channel_id") or item.get("uploader_id") or "")
        if channel_id and channel_id in blocked_channels:
            continue
        thumbnails = item.get("thumbnails") or []
        thumbnail = item.get("thumbnail")
        if not thumbnail and thumbnails:
            thumbnail = next((x.get("url") for x in reversed(thumbnails)
                              if isinstance(x, dict) and x.get("url")), None)
        found.append({
            "id": video_id,
            "title": str(item.get("title") or "Untitled"),
            "channel": str(item.get("channel") or item.get("uploader") or "Unknown channel"),
            "channel_id": channel_id,
            "duration": item.get("duration"),
            "view_count": item.get("view_count"),
            "upload_date": item.get("upload_date") or "",
            "thumbnail": thumbnail,
            "url": "https://www.youtube.com/watch?v=" + video_id,
        })
    return found


def change_block(kind: str, item_id: str, name: str = "", blocked: bool = True) -> dict:
    if kind not in {"video", "channel"}:
        raise ValueError("Block type must be video or channel.")
    item_id = str(item_id).strip()
    if not ID_RE.fullmatch(item_id):
        raise ValueError("Invalid YouTube ID.")
    key = "videos" if kind == "video" else "channels"
    data = load_blocks()
    entries = [x for x in data[key] if isinstance(x, dict) and str(x.get("id")) != item_id]
    if blocked:
        entries.append({"id": item_id, "name": str(name)[:300]})
    data[key] = entries
    save_blocks(data)
    return {"ok": True, "blocks": data}


def get_blocks() -> dict:
    return load_blocks()


def _run_download(job_id: str, video_id: str, proxy: str | None) -> None:
    try:
        cfg = load_config()
        command = build_command(
            find_ytdlp(),
            "https://www.youtube.com/watch?v=" + video_id,
            cfg,
            source_type="video",
            proxy=proxy,
        )
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "running"
            JOBS[job_id]["started_at"] = time.time()
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
        tail = []
        assert process.stdout is not None
        for line in process.stdout:
            line = line.rstrip()
            if line:
                tail.append(line)
                tail = tail[-35:]
                with JOBS_LOCK:
                    JOBS[job_id]["output"] = tail[-12:]
        code = process.wait()
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "completed" if code == 0 else "failed"
            JOBS[job_id]["returncode"] = code
            JOBS[job_id]["output"] = tail[-20:]
            JOBS[job_id]["finished_at"] = time.time()
    except Exception as exc:
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "failed"
            JOBS[job_id]["error"] = str(exc)
            JOBS[job_id]["finished_at"] = time.time()


def start_download(video_id: str, proxy: str | None = None) -> dict:
    video_id = str(video_id).strip()
    if not ID_RE.fullmatch(video_id):
        raise ValueError("Invalid YouTube video ID.")
    proxy = _safe_proxy(proxy)
    with JOBS_LOCK:
        for job in JOBS.values():
            if job["video_id"] == video_id and job["status"] in {"queued", "running"}:
                return dict(job)
        job_id = uuid.uuid4().hex[:12]
        job = {
            "job_id": job_id, "video_id": video_id, "status": "queued",
            "output": [], "created_at": time.time(),
        }
        JOBS[job_id] = job
    thread = threading.Thread(target=_run_download, args=(job_id, video_id, proxy), daemon=True)
    thread.start()
    return dict(job)


def get_downloads() -> list[dict]:
    with JOBS_LOCK:
        return [dict(job) for job in sorted(JOBS.values(), key=lambda x: x["created_at"], reverse=True)]

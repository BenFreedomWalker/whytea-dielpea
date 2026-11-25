#!/usr/bin/env python3
"""YouTube search, persistent content blocks, and web-triggered downloads."""
from __future__ import annotations

import json
import mimetypes
import re
import subprocess
import threading
import time
import tempfile
from urllib.parse import urlparse
import uuid
from pathlib import Path

from library import ROOT, load_config
from whytea import build_command, find_ytdlp

BLOCKS_PATH = ROOT / "blocked_content.json"
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,}$")
PROGRESS_RE = re.compile(r"\[download\]\s+(\d+(?:\.\d+)?)%")


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
    try:
        ytdlp = find_ytdlp()
    except SystemExit as exc:
        raise RuntimeError(str(exc))
    args = [
        ytdlp,
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


THUMB_CACHE = ROOT / "cache" / "thumbnails"
THUMB_HOSTS = {"i.ytimg.com", "yt3.ggpht.com", "lh3.googleusercontent.com", "ytimg.com"}


def fetch_thumbnail(video_id: str, proxy: str | None = None, thumbnail_url: str | None = None) -> tuple[bytes, str]:
    """Cache the thumbnail URL returned by search; never re-extract the video."""
    video_id = str(video_id).strip()
    if not ID_RE.fullmatch(video_id):
        raise ValueError("Invalid YouTube video ID.")
    THUMB_CACHE.mkdir(parents=True, exist_ok=True)
    cached = list(THUMB_CACHE.glob(video_id + ".*"))
    for path in cached:
        content_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        if content_type.startswith("image/"):
            return path.read_bytes(), content_type
    if not thumbnail_url:
        raise RuntimeError("No thumbnail URL was supplied by YouTube search.")
    parsed = urlparse(thumbnail_url)
    if parsed.scheme != "https" or not (parsed.hostname or "").endswith(("ytimg.com", "googleusercontent.com")):
        raise ValueError("Untrusted thumbnail URL.")
    proxy = _safe_proxy(proxy)
    try:
        ytdlp = find_ytdlp()
    except SystemExit as exc:
        raise RuntimeError(str(exc))
    output = str(THUMB_CACHE / (video_id + ".%(ext)s"))
    command = [ytdlp, "--no-warnings", "--no-playlist", "--output", output]
    if proxy:
        command += ["--proxy", proxy]
    command.append(thumbnail_url)
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=25)
    except subprocess.TimeoutExpired:
        raise RuntimeError("Thumbnail download timed out.")
    except OSError as exc:
        raise RuntimeError("Could not start yt-dlp for thumbnail: " + str(exc))
    files = list(THUMB_CACHE.glob(video_id + ".*"))
    if result.returncode != 0 or not files:
        detail = (result.stderr or result.stdout or "yt-dlp did not save the thumbnail").strip()
        raise RuntimeError("Thumbnail download failed: " + detail[-1000:])
    image_path = files[0]
    content_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
    if not content_type.startswith("image/") or image_path.stat().st_size > 4 * 1024 * 1024:
        image_path.unlink(missing_ok=True)
        raise RuntimeError("Invalid or oversized thumbnail.")
    return image_path.read_bytes(), content_type


SEARCH_PROGRESS: dict[str, dict] = {}
SEARCH_PROGRESS_LOCK = threading.Lock()

def _set_search_progress(key: str, line: str) -> None:
    if not key: return
    with SEARCH_PROGRESS_LOCK:
        entry = SEARCH_PROGRESS.setdefault(key, {"lines": [], "done": False})
        entry["lines"].append(line.rstrip())
        entry["lines"] = entry["lines"][-100:]

def get_search_progress(key: str) -> dict:
    with SEARCH_PROGRESS_LOCK:
        return dict(SEARCH_PROGRESS.get(key, {"lines": [], "done": False}))

def search_videos(query: str, limit: int = 10, proxy: str | None = None, offset: int = 0, progress_key: str = "") -> list[dict]:
    query = str(query).strip()
    if not query: raise ValueError("Enter a search query.")
    limit = max(1, min(int(limit), 50))
    offset = max(0, min(int(offset), 500))
    proxy = _safe_proxy(proxy)
    end = offset + limit
    command = _base_ytdlp_args(proxy) + ["--flat-playlist", "--dump-single-json", "--skip-download", "--playlist-start", str(offset + 1), "--playlist-end", str(end), "ytsearch" + str(end) + ":" + query]
    _set_search_progress(progress_key, "[whytea] Starting yt-dlp search...")
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    except OSError as exc:
        _set_search_progress(progress_key, "[error] Could not start yt-dlp: " + str(exc))
        raise RuntimeError("Could not start yt-dlp: " + str(exc))
    stderr_lines, stdout_box = [], []
    def read_stderr():
        assert process.stderr is not None
        for line in process.stderr:
            line=line.rstrip()
            if line: stderr_lines.append(line); _set_search_progress(progress_key,line)
    def read_stdout():
        if process.stdout: stdout_box.append(process.stdout.read())
    err_thread=threading.Thread(target=read_stderr,daemon=True)
    out_thread=threading.Thread(target=read_stdout,daemon=True)
    err_thread.start();out_thread.start()
    try: code=process.wait(timeout=90)
    except subprocess.TimeoutExpired:
        process.kill();process.wait();_set_search_progress(progress_key,"[error] Search timed out after 90 seconds.");raise RuntimeError("YouTube search timed out after 90 seconds.")
    err_thread.join(timeout=3);out_thread.join(timeout=3)
    stdout=stdout_box[0] if stdout_box else ""
    if code and not stdout.strip(): raise RuntimeError(("\n".join(stderr_lines) or "yt-dlp search failed")[-3000:])
    try: payload=json.loads(stdout)
    except json.JSONDecodeError as exc: raise RuntimeError("yt-dlp returned invalid search data: "+str(exc))
    entries=payload.get("entries",[]) if isinstance(payload,dict) else []
    blocks=load_blocks()
    blocked_videos=set(str(x.get("id","")) for x in blocks["videos"] if isinstance(x,dict))
    blocked_channels=set(str(x.get("id","")) for x in blocks["channels"] if isinstance(x,dict))
    found=[]
    for item in entries:
        if not isinstance(item,dict): continue
        video_id=str(item.get("id") or "")
        if not ID_RE.fullmatch(video_id) or video_id in blocked_videos: continue
        channel_id=str(item.get("channel_id") or item.get("uploader_id") or "")
        if channel_id and channel_id in blocked_channels: continue
        thumbnails=item.get("thumbnails") or [];thumbnail=item.get("thumbnail")
        if not thumbnail and thumbnails: thumbnail=next((x.get("url") for x in reversed(thumbnails) if isinstance(x,dict) and x.get("url")),None)
        found.append({"id":video_id,"title":str(item.get("title") or "Untitled"),"channel":str(item.get("channel") or item.get("uploader") or "Unknown channel"),"channel_id":channel_id,"duration":item.get("duration"),"view_count":item.get("view_count"),"upload_date":item.get("upload_date") or "","thumbnail":thumbnail,"url":"https://www.youtube.com/watch?v="+video_id})
    _set_search_progress(progress_key,"[whytea] Search finished; found "+str(len(found))+" usable results.")
    with SEARCH_PROGRESS_LOCK:
        if progress_key in SEARCH_PROGRESS: SEARCH_PROGRESS[progress_key]["done"]=True
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


LOG_DIR = ROOT / "logs"


def _append_log(job_id: str, line: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with (LOG_DIR / (job_id + ".log")).open("a", encoding="utf-8", errors="replace") as log:
        log.write(line + "\n")


def get_download_log(job_id: str) -> dict:
    if not re.fullmatch(r"[a-f0-9]{12}", str(job_id)):
        raise ValueError("Invalid download job ID.")
    path = LOG_DIR / (job_id + ".log")
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        content = ""
    with JOBS_LOCK:
        job = JOBS.get(job_id, {})
        status = job.get("status", "unknown")
    return {"job_id": job_id, "status": status, "log": content[-60000:]}


def _run_thumbnail_worker(job_id: str, video_id: str, proxy: str | None, cfg: dict) -> None:
    try:
        ytdlp = find_ytdlp()
        download_dir = ROOT / str(cfg["download_dir"])
        output = str(download_dir / "%(uploader)s" / "%(upload_date)s - %(title)s [%(id)s].%(ext)s")
        command = [ytdlp, "--no-warnings", "--no-playlist", "--skip-download", "--write-thumbnail",
                   "--convert-thumbnails", "jpg", "--output", output,
                   "--extractor-args", "youtube:player_js_variant=tv", "--remote-components", "ejs:npm"]
        if proxy:
            command += ["--proxy", proxy]
        browser = str(cfg.get("cookies_from_browser", "")).strip()
        if browser:
            command += ["--cookies-from-browser", browser]
        command.append("https://www.youtube.com/watch?v=" + video_id)
        _append_log(job_id, "[thumbnail] Starting separate thumbnail worker")
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        for line in (result.stdout + "\n" + result.stderr).splitlines():
            if line.strip():
                _append_log(job_id, "[thumbnail] " + line.rstrip())
        if result.returncode:
            _append_log(job_id, f"[thumbnail] Worker exited with code {result.returncode}")
    except Exception as exc:
        _append_log(job_id, "[thumbnail] " + str(exc))


def _run_thumbnail_worker(job_id: str, video_id: str, proxy: str | None, cfg: dict) -> None:
    process = None
    try:
        ytdlp = find_ytdlp()
        download_dir = ROOT / str(cfg["download_dir"])
        output = str(download_dir / "%(uploader)s" / "%(upload_date)s - %(title)s [%(id)s].%(ext)s")
        command = [ytdlp, "--no-warnings", "--no-playlist", "--skip-download", "--write-thumbnail", "--convert-thumbnails", "jpg", "--output", output, "--extractor-args", "youtube:player_js_variant=tv", "--remote-components", "ejs:npm"]
        if proxy:
            command += ["--proxy", proxy]
        browser = str(cfg.get("cookies_from_browser", "")).strip()
        if browser:
            command += ["--cookies-from-browser", browser]
        command.append("https://www.youtube.com/watch?v=" + video_id)
        with JOBS_LOCK:
            if JOBS[job_id].get("cancel_requested"):
                return
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
            JOBS[job_id]["thumbnail_process"] = process
        _append_log(job_id, "[thumbnail] Starting separate thumbnail worker")
        assert process.stdout is not None
        for line in process.stdout:
            if line.strip():
                _append_log(job_id, "[thumbnail] " + line.rstrip())
        code = process.wait()
        if code:
            _append_log(job_id, "[thumbnail] Worker exited with code " + str(code))
    except Exception as exc:
        _append_log(job_id, "[thumbnail] " + str(exc))
    finally:
        with JOBS_LOCK:
            if JOBS.get(job_id, {}).get("thumbnail_process") is process:
                JOBS[job_id]["thumbnail_process"] = None
def _run_download(job_id: str, video_id: str, proxy: str | None) -> None:
    process = None
    try:
        cfg = load_config()
        command = build_command(find_ytdlp(), "https://www.youtube.com/watch?v=" + video_id, cfg, source_type="video", proxy=proxy, include_thumbnail=False)
        thumb_thread = threading.Thread(target=_run_thumbnail_worker, args=(job_id, video_id, proxy, cfg), daemon=True)
        thumb_thread.start()
        command.insert(-1, "--newline")
        with JOBS_LOCK:
            if JOBS[job_id].get("cancel_requested"):
                return
            JOBS[job_id]["status"] = "running"
            JOBS[job_id]["started_at"] = time.time()
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
            JOBS[job_id]["process"] = process
        tail = []
        assert process.stdout is not None
        for line in process.stdout:
            line = line.rstrip()
            if line:
                _append_log(job_id, "[video] " + line)
                match = PROGRESS_RE.search(line)
                with JOBS_LOCK:
                    if match:
                        JOBS[job_id]["progress"] = min(100.0, max(0.0, float(match.group(1))))
                    tail.append(line)
                    tail = tail[-35:]
                    JOBS[job_id]["output"] = tail[-12:]
        code = process.wait()
        thumb_thread.join(timeout=185)
        with JOBS_LOCK:
            cancelled = JOBS[job_id].get("cancel_requested", False)
            JOBS[job_id]["status"] = "cancelled" if cancelled else ("completed" if code == 0 else "failed")
            JOBS[job_id]["returncode"] = code
            JOBS[job_id]["output"] = tail[-20:]
            JOBS[job_id]["finished_at"] = time.time()
    except (Exception, SystemExit) as exc:
        with JOBS_LOCK:
            cancelled = JOBS.get(job_id, {}).get("cancel_requested", False)
            JOBS[job_id]["status"] = "cancelled" if cancelled else "failed"
            JOBS[job_id]["error"] = str(exc)
            JOBS[job_id]["finished_at"] = time.time()
        _append_log(job_id, "[error] " + str(exc))
    finally:
        with JOBS_LOCK:
            if job_id in JOBS:
                JOBS[job_id]["process"] = None
                JOBS[job_id]["thumbnail_process"] = None

def cancel_download(job_id: str) -> dict:
    if not re.fullmatch(r"[a-f0-9]{12}", str(job_id)):
        raise ValueError("Invalid download job ID.")
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise ValueError("Download job not found.")
        if job["status"] not in {"queued", "running"}:
            return {k: v for k, v in job.items() if k not in {"process", "thumbnail_process"}}
        job["cancel_requested"] = True
        job["status"] = "cancelled"
        job["finished_at"] = time.time()
        processes = [job.get("process"), job.get("thumbnail_process")]
    for process in processes:
        if process is not None and process.poll() is None:
            process.terminate()
    _append_log(job_id, "[cancel] Cancellation requested by user")
    with JOBS_LOCK:
        return {k: v for k, v in JOBS[job_id].items() if k not in {"process", "thumbnail_process"}}
def start_download(video_id: str, proxy: str | None = None) -> dict:
    video_id = str(video_id).strip()
    if not ID_RE.fullmatch(video_id):
        raise ValueError("Invalid YouTube video ID.")
    proxy = _safe_proxy(proxy)
    with JOBS_LOCK:
        for job in JOBS.values():
            if job["video_id"] == video_id and job["status"] in {"queued", "running"}:
                return {k: v for k, v in job.items() if k not in {"process", "thumbnail_process"}}
        job_id = uuid.uuid4().hex[:12]
        job = {
            "job_id": job_id, "video_id": video_id, "status": "queued",
            "output": [], "progress": 0.0, "created_at": time.time(), "process": None, "thumbnail_process": None, "cancel_requested": False,
        }
        JOBS[job_id] = job
    thread = threading.Thread(target=_run_download, args=(job_id, video_id, proxy), daemon=True)
    thread.start()
    return dict(job)


def get_downloads() -> list[dict]:
    with JOBS_LOCK:
        return [{k: v for k, v in job.items() if k not in {"process", "thumbnail_process"}} for job in sorted(JOBS.values(), key=lambda x: x["created_at"], reverse=True)]

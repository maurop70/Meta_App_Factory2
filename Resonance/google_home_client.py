"""
google_home_client.py — Plan v2 Phase 3: local TTS + Chromecast / Google Home casting.

Generates speech with gTTS, caches it under uploads/tts_cache/ with random
(non-enumerable) filenames, serves it via the FastAPI static mount, and casts to
Google Home / Chromecast devices via pychromecast.

Privacy & safety hardening:
  - Random uuid filenames (never MD5(text)) so cache contents aren't guessable.
  - In-memory MD5(text) -> uuid map for cache reuse, validated against disk.
  - Atomic writes (temp file + os.replace) so a speaker never fetches a partial.
  - 1-hour TTL cleanup of cached audio, pruning the in-memory map in lockstep.
  - test_mode / RESONANCE_TEST_MODE bypasses mDNS discovery to keep tests fast.

gTTS (network) and pychromecast (mDNS) are imported lazily inside the functions
that need them, so importing this module never requires those packages or hits
the network — and unit tests can stub the indirection points.
"""

import os
import time
import uuid
import socket
import hashlib
import logging
import threading

logger = logging.getLogger("GoogleHome")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(SCRIPT_DIR, "uploads")
TTS_CACHE_DIR = os.path.join(UPLOADS_DIR, "tts_cache")
BACKING_TRACKS_DIR = os.path.join(UPLOADS_DIR, "backing_tracks")
os.makedirs(TTS_CACHE_DIR, exist_ok=True)
os.makedirs(BACKING_TRACKS_DIR, exist_ok=True)

# The LAN media server port (must match the uvicorn launch port).
MEDIA_PORT = int(os.environ.get("RESONANCE_MEDIA_PORT", os.environ.get("PORT", "5006")))
CACHE_TTL_SECONDS = 3600  # 1 hour

# In-memory MD5(text) -> uuid filename, guarded by a lock for thread safety.
_cache_map = {}
_cache_lock = threading.Lock()


def _is_test_mode(explicit=False):
    return bool(explicit) or os.environ.get("RESONANCE_TEST_MODE", "").lower() == "true"


def get_lan_ip():
    """Best-effort LAN IP — the local interface that routes toward the internet.

    Uses a UDP socket with no packets actually sent; falls back to loopback.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def cleanup_cache(ttl_seconds=CACHE_TTL_SECONDS):
    """Delete cached audio older than ttl, then prune the in-memory map so it can
    never point at a file that no longer exists on disk."""
    now = time.time()
    try:
        for name in os.listdir(TTS_CACHE_DIR):
            if not name.endswith(".mp3"):
                continue
            path = os.path.join(TTS_CACHE_DIR, name)
            try:
                if now - os.path.getmtime(path) > ttl_seconds:
                    os.remove(path)
            except OSError:
                pass
    except OSError:
        return
    # Prune any map entry whose target file is gone (TTL-deleted or otherwise).
    with _cache_lock:
        for key in list(_cache_map.keys()):
            if not os.path.exists(os.path.join(TTS_CACHE_DIR, _cache_map[key])):
                _cache_map.pop(key, None)


def _load_known_speakers():
    """Configured Chromecast speakers (friendly_name + ip) for mDNS-free casting.

    Pulled from parent_config's ``google_home.known_speakers``. Only entries with a
    usable ``ip`` are returned. Best-effort: any failure yields an empty list, so
    casting simply falls back to mDNS discovery.
    """
    try:
        import resonance_config
        speakers = (resonance_config.load_config().get("google_home") or {}).get("known_speakers") or []
        return [s for s in speakers if isinstance(s, dict) and s.get("ip")]
    except Exception as e:
        logger.warning(f"Could not load known speakers (non-fatal): {e}")
        return []


def discover_speakers(test_mode=False, known_speakers=None):
    """List available cast devices.

    Resolution order:
      1. test mode (explicit or RESONANCE_TEST_MODE=true) -> mock list, NO scanning;
      2. configured ``known_speakers`` (friendly_name + ip) -> returned directly,
         NO mDNS — the reliable path on Docker Desktop / when mDNS can't reach the LAN;
      3. otherwise -> an mDNS scan (the convenience path on native Linux).
    """
    if _is_test_mode(test_mode):
        return [{"name": "Mock Living Room", "model": "Google Home Mini", "uuid": "mock-uuid"}]

    if known_speakers is None:
        known_speakers = _load_known_speakers()
    if known_speakers:
        return [
            {
                "name": s.get("friendly_name") or s.get("name") or s.get("ip"),
                "model": s.get("model", "configured"),
                "ip": s.get("ip"),
                "uuid": s.get("uuid"),
            }
            for s in known_speakers if isinstance(s, dict) and s.get("ip")
        ]

    import pychromecast
    chromecasts, browser = pychromecast.get_chromecasts()
    try:
        return [
            {
                "name": cc.cast_info.friendly_name,
                "model": cc.cast_info.model_name,
                "uuid": str(cc.cast_info.uuid),
            }
            for cc in chromecasts
        ]
    finally:
        try:
            pychromecast.discovery.stop_discovery(browser)
        except Exception:
            pass


def _generate_tts(text, out_path):
    """Generate speech for ``text`` into ``out_path`` via gTTS (network call).

    Isolated so tests can stub it without touching gTTS or the network.
    """
    from gtts import gTTS
    gTTS(text=text, lang="en").save(out_path)


def _cast_media(media_url, speaker_name=None, content_type="audio/mpeg", known_speakers=None):
    """Resolve a cast device by name (or first found) and play ``media_url``.

    If ``known_speakers`` are configured (friendly_name + ip), connect directly to
    those hosts via ``get_chromecasts(known_hosts=[...])`` — no mDNS. This is the
    reliable route on Docker Desktop, where host networking can't see the LAN.
    Falls back to an mDNS scan when no IPs are configured.
    """
    import pychromecast
    if known_speakers is None:
        known_speakers = _load_known_speakers()
    known_hosts = [s["ip"] for s in known_speakers if isinstance(s, dict) and s.get("ip")]

    if known_hosts:
        chromecasts, browser = pychromecast.get_chromecasts(known_hosts=known_hosts)
    else:
        chromecasts, browser = pychromecast.get_chromecasts()
    try:
        target = None
        for cc in chromecasts:
            if speaker_name is None or cc.cast_info.friendly_name == speaker_name:
                target = cc
                break
        if target is None:
            raise RuntimeError(f"Cast device not found: {speaker_name!r}")
        target.wait()
        target.media_controller.play_media(media_url, content_type)
        target.media_controller.block_until_active(timeout=15)
    finally:
        try:
            pychromecast.discovery.stop_discovery(browser)
        except Exception:
            pass


def speak_to_room(text, speaker_name=None, test_mode=False):
    """Speak ``text`` on a Google Home speaker, reusing a cached clip when valid.

    Cache key is MD5(text); the on-disk file has a random uuid name. A cache hit
    is honoured only if the mapped file still exists on disk, else it's
    regenerated. Audio is written to a temp file and os.replace()d into place so
    a speaker never fetches a partially-written clip. Returns a dict describing
    the cast (in test mode the cast is skipped and ``cast`` is False).
    """
    if not text or not text.strip():
        raise ValueError("speak_to_room requires non-empty text")

    cleanup_cache()  # routine TTL sweep on every speech request

    digest = hashlib.md5(text.encode("utf-8")).hexdigest()
    filename = None
    with _cache_lock:
        cached = _cache_map.get(digest)
        if cached and os.path.exists(os.path.join(TTS_CACHE_DIR, cached)):
            filename = cached

    if filename is None:
        filename = uuid.uuid4().hex + ".mp3"
        final_path = os.path.join(TTS_CACHE_DIR, filename)
        tmp_path = final_path + ".tmp"
        try:
            _generate_tts(text, tmp_path)
            os.replace(tmp_path, final_path)
        except Exception:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            raise
        with _cache_lock:
            _cache_map[digest] = filename

    media_url = f"http://{get_lan_ip()}:{MEDIA_PORT}/static/tts_cache/{filename}"
    if _is_test_mode(test_mode):
        return {"cast": False, "media_url": media_url, "speaker": speaker_name, "test_mode": True}

    _cast_media(media_url, speaker_name, content_type="audio/mpeg")
    return {"cast": True, "media_url": media_url, "speaker": speaker_name}


def list_backing_tracks():
    """Return the available backing-track filenames (.mp3 only)."""
    if not os.path.isdir(BACKING_TRACKS_DIR):
        return []
    return sorted(n for n in os.listdir(BACKING_TRACKS_DIR) if n.lower().endswith(".mp3"))


def play_backing_track(track_name, speaker_name=None, test_mode=False):
    """Cast a backing track from uploads/backing_tracks/ to a speaker.

    ``track_name`` is validated against the available tracks (allowlist) and
    reduced to its basename, so a caller can't escape the directory.
    """
    safe_name = os.path.basename(track_name or "")
    if safe_name not in list_backing_tracks():
        raise ValueError(f"Unknown backing track: {track_name!r}")

    media_url = f"http://{get_lan_ip()}:{MEDIA_PORT}/static/backing_tracks/{safe_name}"
    if _is_test_mode(test_mode):
        return {"cast": False, "media_url": media_url, "speaker": speaker_name, "test_mode": True}

    _cast_media(media_url, speaker_name, content_type="audio/mpeg")
    return {"cast": True, "media_url": media_url, "speaker": speaker_name}

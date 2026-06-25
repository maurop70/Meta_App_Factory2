"""Phase 3 tests: secured LAN endpoints + Google Home casting.

Covers fail-closed auth (missing/empty/wrong X-Resonance-Token -> 401), authorized
access with gTTS + pychromecast fully mocked, and verification that unit tests
never perform real mDNS discovery. TestClient is used WITHOUT its context manager
so the app lifespan (and the fail-closed boot check / nerve-center thread) does
not run for the per-request tests; the boot check is exercised separately.
"""

import sys
import types

import pytest
from fastapi.testclient import TestClient

import server
import google_home_client as ghc

TOKEN = "secret-test-token"

# (method, path, json-body) for EVERY LAN endpoint added across Phases 3-4 that
# must reject missing/empty/wrong tokens with 401.
PROTECTED = [
    ("post", "/api/telemetry/screen-time", {"minutes": 5}),
    ("get", "/api/engagement/log", None),
    ("post", "/api/google-home/cast", {"text": "Hello Leo"}),
    ("get", "/api/guitar/backing-tracks", None),
    ("post", "/api/guitar/backing-tracks/cast", {"track_name": "riff.mp3"}),
]


def _call(client, method, path, body, headers=None):
    if method == "post":
        return client.post(path, json=body, headers=headers or {})
    return client.get(path, headers=headers or {})


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("RESONANCE_TOKEN", TOKEN)
    monkeypatch.setenv("RESONANCE_TEST_MODE", "true")  # bypass mDNS + real casting

    # Hermetic cache/track dirs so tests never touch the real uploads/ tree.
    cache = tmp_path / "tts_cache"; cache.mkdir()
    tracks = tmp_path / "backing_tracks"; tracks.mkdir()
    monkeypatch.setattr(ghc, "TTS_CACHE_DIR", str(cache))
    monkeypatch.setattr(ghc, "BACKING_TRACKS_DIR", str(tracks))
    (tracks / "riff.mp3").write_bytes(b"FAKE-MP3")

    # Mock gTTS: write a dummy file instead of calling Google's TTS service.
    monkeypatch.setattr(ghc, "_generate_tts",
                        lambda text, out_path: open(out_path, "wb").write(b"ID3-FAKE"))
    return TestClient(server.app)


# ── Fail-closed auth: 401 without a valid token ─────────────────────────────

@pytest.mark.parametrize("method,path,body", PROTECTED)
def test_missing_token_is_401(client, method, path, body):
    assert _call(client, method, path, body).status_code == 401


@pytest.mark.parametrize("method,path,body", PROTECTED)
def test_empty_token_is_401(client, method, path, body):
    resp = _call(client, method, path, body, headers={"X-Resonance-Token": ""})
    assert resp.status_code == 401


@pytest.mark.parametrize("method,path,body", PROTECTED)
def test_wrong_token_is_401(client, method, path, body):
    resp = _call(client, method, path, body, headers={"X-Resonance-Token": "wrong"})
    assert resp.status_code == 401


# ── Authorized access (mocked gTTS + pychromecast bypass) ───────────────────

def test_authorized_telemetry_ok(client):
    resp = client.post("/api/telemetry/screen-time",
                       json={"minutes": 12, "app_name": "YouTube"},
                       headers={"X-Resonance-Token": TOKEN})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_authorized_cast_ok_with_mocked_tts(client):
    resp = client.post("/api/google-home/cast",
                       json={"text": "Yo Leo, nice riff!", "speaker_name": "Mock Living Room"},
                       headers={"X-Resonance-Token": TOKEN})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "ok"
    assert "/static/tts_cache/" in data["media_url"]
    assert data["media_url"].endswith(".mp3")
    # Random (non-enumerable) filename — never MD5(text).
    import hashlib
    assert hashlib.md5(b"Yo Leo, nice riff!").hexdigest() not in data["media_url"]
    assert data["cast"] is False  # test mode: no real device contacted


def test_authorized_list_backing_tracks(client):
    resp = client.get("/api/guitar/backing-tracks", headers={"X-Resonance-Token": TOKEN})
    assert resp.status_code == 200
    assert "riff.mp3" in resp.json()["tracks"]


def test_authorized_cast_backing_track(client):
    resp = client.post("/api/guitar/backing-tracks/cast",
                       json={"track_name": "riff.mp3", "speaker_name": "Mock Living Room"},
                       headers={"X-Resonance-Token": TOKEN})
    assert resp.status_code == 200, resp.text
    assert resp.json()["media_url"].endswith("/static/backing_tracks/riff.mp3")


def test_unknown_backing_track_rejected(client):
    resp = client.post("/api/guitar/backing-tracks/cast",
                       json={"track_name": "../../etc/passwd"},
                       headers={"X-Resonance-Token": TOKEN})
    assert resp.status_code == 400


# ── Discovery bypass: no real mDNS during tests ─────────────────────────────

def test_discovery_bypass_returns_mock_without_mdns(monkeypatch):
    monkeypatch.setenv("RESONANCE_TEST_MODE", "true")
    speakers = ghc.discover_speakers()
    assert speakers and speakers[0]["name"] == "Mock Living Room"


def test_explicit_test_mode_bypass():
    # Works even if pychromecast were absent — proves no scan path is taken.
    speakers = ghc.discover_speakers(test_mode=True)
    assert speakers[0]["uuid"] == "mock-uuid"


# ── Fail-closed boot: refuse to start without a token ───────────────────────

def test_startup_refuses_to_boot_without_token(monkeypatch):
    monkeypatch.delenv("RESONANCE_TOKEN", raising=False)
    with pytest.raises(Exception):
        with TestClient(server.app):
            pass


# ── Discovery-independent (IP) casting fallback — de-risks mDNS ─────────────

def test_discover_speakers_uses_configured_ips_without_mdns(monkeypatch):
    """Configured known_speakers are returned directly — no mDNS scan. (If mDNS
    were attempted, importing the absent-in-test pychromecast path would surface;
    here we assert the IP list short-circuits it.)"""
    monkeypatch.delenv("RESONANCE_TEST_MODE", raising=False)  # not the test-mode bypass
    speakers = ghc.discover_speakers(
        test_mode=False,
        known_speakers=[{"friendly_name": "Living Room", "ip": "192.168.1.50"}],
    )
    assert speakers == [{"name": "Living Room", "model": "configured",
                         "ip": "192.168.1.50", "uuid": None}]


def test_load_known_speakers_reads_config(monkeypatch):
    import resonance_config
    monkeypatch.setattr(
        resonance_config, "load_config",
        lambda *a, **k: {"google_home": {"known_speakers": [
            {"friendly_name": "Kitchen", "ip": "192.168.1.60"},
            {"friendly_name": "no-ip — ignored"},  # dropped: no ip
        ]}},
    )
    out = ghc._load_known_speakers()
    assert out == [{"friendly_name": "Kitchen", "ip": "192.168.1.60"}]


def test_cast_connects_by_ip_known_hosts_not_mdns(monkeypatch):
    """The cast client connects via get_chromecasts(known_hosts=[ip]) — never a
    broad mDNS scan — when speakers are configured."""
    captured = {}

    class _MediaController:
        def play_media(self, url, content_type):
            captured["url"] = url
            captured["content_type"] = content_type
        def block_until_active(self, timeout=None):
            pass

    class _Cast:
        def __init__(self):
            self.cast_info = types.SimpleNamespace(friendly_name="Living Room")
            self.media_controller = _MediaController()
        def wait(self):
            captured["waited"] = True

    def _get_chromecasts(known_hosts=None):
        captured["known_hosts"] = known_hosts
        return ([_Cast()], "browser-sentinel")

    fake = types.SimpleNamespace(
        get_chromecasts=_get_chromecasts,
        discovery=types.SimpleNamespace(
            stop_discovery=lambda b: captured.__setitem__("stopped", b)),
    )
    monkeypatch.setitem(sys.modules, "pychromecast", fake)

    ghc._cast_media(
        "http://192.168.1.10:5006/static/tts_cache/abc.mp3",
        speaker_name="Living Room",
        known_speakers=[{"friendly_name": "Living Room", "ip": "192.168.1.50"}],
    )

    assert captured["known_hosts"] == ["192.168.1.50"]   # IP path, not mDNS
    assert captured["url"].endswith("abc.mp3")
    assert captured["waited"] is True
    assert captured["stopped"] == "browser-sentinel"     # discovery cleaned up


# ── Stored-audio privacy: TTL cleanup prunes the cache map in lockstep ──────

def test_cache_ttl_prunes_map_and_regenerates_on_miss(monkeypatch, tmp_path):
    """A cache hit can NEVER point at a TTL-deleted file: cleanup_cache prunes the
    in-memory MD5->UUID map in the same pass, and a miss regenerates a new clip."""
    import os, time, hashlib
    monkeypatch.setenv("RESONANCE_TEST_MODE", "true")  # skip mDNS + real cast
    cache = tmp_path / "tts_cache"; cache.mkdir()
    monkeypatch.setattr(ghc, "TTS_CACHE_DIR", str(cache))
    monkeypatch.setattr(ghc, "_generate_tts",
                        lambda text, out_path: open(out_path, "wb").write(b"ID3-FAKE"))
    ghc._cache_map.clear()

    text = "Yo Leo, late-night riff?"
    digest = hashlib.md5(text.encode("utf-8")).hexdigest()

    r1 = ghc.speak_to_room(text, test_mode=True)
    fname1 = r1["media_url"].rsplit("/", 1)[-1]
    assert os.path.exists(os.path.join(str(cache), fname1))
    assert ghc._cache_map.get(digest) == fname1          # cached: md5 -> uuid

    # A cache HIT reuses the same on-disk file while it exists.
    r2 = ghc.speak_to_room(text, test_mode=True)
    assert r2["media_url"].endswith(fname1)

    # Simulate TTL expiry: age the file past the TTL, then run cleanup.
    old = time.time() - (ghc.CACHE_TTL_SECONDS + 10)
    os.utime(os.path.join(str(cache), fname1), (old, old))
    ghc.cleanup_cache()
    assert not os.path.exists(os.path.join(str(cache), fname1))  # file deleted
    assert digest not in ghc._cache_map                          # map pruned in lockstep

    # The next request is a MISS -> regenerate a fresh clip (never a dangling URL).
    r3 = ghc.speak_to_room(text, test_mode=True)
    fname3 = r3["media_url"].rsplit("/", 1)[-1]
    assert fname3 != fname1
    assert os.path.exists(os.path.join(str(cache), fname3))

"""Tests for GCS-backed TTS cache behavior."""

from app.services.tts import TTSService


class FakeBlob:
    """Minimal storage blob fake for invalidation tests."""

    def __init__(self, exists: bool) -> None:
        self._exists = exists
        self.deleted = False

    def exists(self) -> bool:
        return self._exists

    def delete(self) -> None:
        self.deleted = True


class FakeBucket:
    """Capture the requested GCS object name."""

    def __init__(self, blob: FakeBlob) -> None:
        self._blob = blob
        self.requested_name = ""

    def blob(self, name: str) -> FakeBlob:
        self.requested_name = name
        return self._blob


def test_invalidate_cache_deletes_voice_specific_blob(monkeypatch):
    """Invalidation uses the same text/voice/language hash as normal cache reads."""
    blob = FakeBlob(exists=True)
    bucket = FakeBucket(blob)
    service = object.__new__(TTSService)
    service.bucket = bucket
    monkeypatch.setattr(TTSService, "voice_name", property(lambda self: "pt-PT-Voice"))
    monkeypatch.setattr(TTSService, "language_code", property(lambda self: "pt-PT"))

    invalidated = service.invalidate_cache(" olá ", "spreadsheet", "123")

    expected_key = service._get_cache_key(" olá ", "pt-PT-Voice", "pt-PT")
    assert bucket.requested_name == f"spreadsheet/123/{expected_key}.mp3"
    assert invalidated is True
    assert blob.deleted is True


def test_invalidate_cache_treats_missing_blob_as_successful_noop(monkeypatch):
    """Repeated invalidation is idempotent and does not attempt a delete."""
    blob = FakeBlob(exists=False)
    service = object.__new__(TTSService)
    service.bucket = FakeBucket(blob)
    monkeypatch.setattr(TTSService, "voice_name", property(lambda self: "pt-PT-Voice"))
    monkeypatch.setattr(TTSService, "language_code", property(lambda self: "pt-PT"))

    assert service.invalidate_cache("olá", "spreadsheet", "123") is False
    assert blob.deleted is False

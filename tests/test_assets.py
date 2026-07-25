from __future__ import annotations

import io
from copy import deepcopy
from email.message import Message
from pathlib import Path
from typing import Any

import pytest

from aws_agent_eval.assets import (
    fetch_dataset_assets,
    materialize_cached_assets,
    validate_case_public_assets,
)
from aws_agent_eval.dataset import load_dataset

ROOT = Path(__file__).resolve().parents[1]


class FakeResponse:
    def __init__(self, url: str, body: bytes, media_type: str) -> None:
        self._url = url
        self._stream = io.BytesIO(body)
        self.headers = Message()
        self.headers["Content-Type"] = media_type
        self.headers["Content-Length"] = str(len(body))
        self.headers["ETag"] = '"fixture-etag"'
        self.headers["Last-Modified"] = "Sat, 25 Jul 2026 00:00:00 GMT"

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        self._stream.close()

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def geturl(self) -> str:
        return self._url


def _fake_urlopen(request: Any, *, timeout: int) -> FakeResponse:
    assert timeout > 0
    url = request.full_url
    if url.endswith(".png"):
        return FakeResponse(url, b"\x89PNG\r\n\x1a\nfixture", "image/png")
    return FakeResponse(url, b'{"AWSTemplateFormatVersion":"2010-09-09"}\n', "text/plain")


def test_official_assets_download_without_aws_credentials_and_materialize(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = load_dataset(ROOT / "datasets/aws-official-solutions-v1")
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    cache = tmp_path / "asset-cache"
    lock = fetch_dataset_assets(dataset, cache)

    assert lock["dataset"] == {"id": dataset.id, "version": dataset.version}
    assert len(lock["assets"]) == 6
    assert all(item["resolved_url"] == item["url"] for item in lock["assets"])
    assert all(len(item["sha256"]) == 64 for item in lock["assets"])

    case = dataset.cases[0]
    workspace = tmp_path / "workspace"
    materialized = materialize_cached_assets(dataset, case, cache, workspace)
    assert {item["local_path"] for item in materialized} == {
        "public-assets/architecture.png",
        "public-assets/solution.template",
    }
    assert (workspace / "public-assets/architecture.png").read_bytes().startswith(b"\x89PNG")
    assert (workspace / "public-assets/solution.template").is_file()


def test_cached_asset_digest_mismatch_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = load_dataset(ROOT / "datasets/aws-official-solutions-v1")
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    cache = tmp_path / "asset-cache"
    lock = fetch_dataset_assets(dataset, cache)
    first = lock["assets"][0]
    cached = cache / dataset.id / dataset.version / first["cache_path"]
    cached.write_bytes(b"tampered")

    with pytest.raises(ValueError, match="digest mismatch"):
        materialize_cached_assets(dataset, dataset.cases[0], cache, tmp_path / "workspace")


def test_untrusted_redirect_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = load_dataset(ROOT / "datasets/aws-official-solutions-v1")

    def redirecting_urlopen(request: Any, *, timeout: int) -> FakeResponse:
        del request, timeout
        return FakeResponse("https://example.com/asset.png", b"png", "image/png")

    monkeypatch.setattr("urllib.request.urlopen", redirecting_urlopen)
    with pytest.raises(ValueError, match="host is not allowed"):
        fetch_dataset_assets(dataset, tmp_path / "asset-cache")


def test_official_cost_page_cannot_be_exposed_to_agent() -> None:
    dataset = load_dataset(ROOT / "datasets/aws-official-solutions-v1")
    case_data = deepcopy(dataset.cases[0].data)
    reference = case_data["official_reference"]
    case_data["public_assets"][0]["url"] = reference["cost_page_url"]

    with pytest.raises(ValueError, match="evaluator-only oracle"):
        validate_case_public_assets(str(case_data["id"]), case_data)

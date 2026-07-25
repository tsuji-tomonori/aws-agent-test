from __future__ import annotations

import hashlib
import shutil
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .types import Case, Dataset, JsonObject
from .utils import dump_json, load_json, safe_relative, utc_now

ALLOWED_PUBLIC_ASSET_HOSTS = frozenset(
    {
        "docs.aws.amazon.com",
        "raw.githubusercontent.com",
        "s3.amazonaws.com",
        "solutions-reference.s3.amazonaws.com",
        "pricing.us-east-1.amazonaws.com",
    }
)
DEFAULT_MAX_ASSET_BYTES = 50 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 60


def validate_case_public_assets(case_id: str, case_data: JsonObject) -> None:
    assets = case_data.get("public_assets", [])
    if not isinstance(assets, list):
        raise ValueError(f"{case_id}: public_assets must be an array")

    ids: set[str] = set()
    targets: set[str] = set()
    for raw_asset in assets:
        if not isinstance(raw_asset, dict):
            raise ValueError(f"{case_id}: every public asset must be an object")
        asset_id = str(raw_asset["id"])
        target_text = str(raw_asset["target"])
        if asset_id in ids:
            raise ValueError(f"{case_id}: duplicate public asset id: {asset_id}")
        if target_text in targets:
            raise ValueError(f"{case_id}: duplicate public asset target: {target_text}")
        ids.add(asset_id)
        targets.add(target_text)
        safe_relative(target_text)
        _validate_public_https_url(case_id, str(raw_asset["url"]))
        _validate_public_https_url(case_id, str(raw_asset["source_page_url"]))
        if raw_asset["authentication"] != "none":
            raise ValueError(f"{case_id}: public asset authentication must be none")

    reference = case_data.get("official_reference")
    if reference is None:
        return
    if not isinstance(reference, dict):
        raise ValueError(f"{case_id}: official_reference must be an object")
    if reference["credentials_required"] is not False:
        raise ValueError(f"{case_id}: official reference cases must be credential-free")
    for field in ("architecture_page_url", "cost_page_url", "template_page_url"):
        _validate_public_https_url(case_id, str(reference[field]))

    roles = {str(item.get("role")) for item in assets if isinstance(item, dict)}
    if "architecture-diagram" not in roles:
        raise ValueError(f"{case_id}: official reference case requires an architecture diagram")
    if "cloudformation-template" not in roles:
        raise ValueError(f"{case_id}: official reference case requires a CloudFormation template")

    cost_page_url = str(reference["cost_page_url"])
    exposed_urls = {
        str(item[field])
        for item in assets
        if isinstance(item, dict)
        for field in ("url", "source_page_url")
    }
    if cost_page_url in exposed_urls:
        raise ValueError(f"{case_id}: official cost page must remain an evaluator-only oracle")

    snapshot = case_data["price_snapshot"]
    assert isinstance(snapshot, dict)
    sources = snapshot["sources"]
    assert isinstance(sources, list)
    source_urls = {str(item["url"]) for item in sources if isinstance(item, dict) and "url" in item}
    if cost_page_url not in source_urls:
        raise ValueError(f"{case_id}: cost_page_url must be included in price_snapshot.sources")


def fetch_dataset_assets(
    dataset: Dataset,
    cache_dir: Path,
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_asset_bytes: int = DEFAULT_MAX_ASSET_BYTES,
) -> JsonObject:
    root = _dataset_cache_root(dataset, cache_dir)
    entries: list[JsonObject] = []
    for case in dataset.cases:
        raw_assets = case.data.get("public_assets", [])
        assert isinstance(raw_assets, list)
        for raw_asset in raw_assets:
            assert isinstance(raw_asset, dict)
            entries.append(
                _fetch_asset(
                    case,
                    raw_asset,
                    root,
                    timeout_seconds=timeout_seconds,
                    max_asset_bytes=max_asset_bytes,
                )
            )

    lock: JsonObject = {
        "schema_version": "1.0",
        "dataset": {"id": dataset.id, "version": dataset.version},
        "retrieved_at": utc_now(),
        "assets": entries,
    }
    dump_json(root / "assets.lock.json", lock)
    return lock


def materialize_cached_assets(
    dataset: Dataset,
    case: Case,
    cache_dir: Path,
    workspace: Path,
) -> list[JsonObject]:
    raw_assets = case.data.get("public_assets", [])
    assert isinstance(raw_assets, list)
    if not raw_assets:
        return []

    root = _dataset_cache_root(dataset, cache_dir)
    lock_path = root / "assets.lock.json"
    if not lock_path.is_file():
        raise ValueError(
            f"Asset cache is not initialized for {dataset.id} {dataset.version}; "
            "run aws-agent-eval fetch-assets first"
        )
    lock = load_json(lock_path)
    lock_dataset = lock.get("dataset")
    if not isinstance(lock_dataset, dict) or lock_dataset != {
        "id": dataset.id,
        "version": dataset.version,
    }:
        raise ValueError(f"Asset lock dataset mismatch: {lock_path}")
    raw_entries = lock.get("assets", [])
    if not isinstance(raw_entries, list):
        raise ValueError(f"Invalid asset lock: {lock_path}")
    index: dict[tuple[str, str], JsonObject] = {}
    for raw_entry in raw_entries:
        if isinstance(raw_entry, dict):
            index[(str(raw_entry["case_id"]), str(raw_entry["asset_id"]))] = raw_entry

    materialized: list[JsonObject] = []
    destination_root = (workspace / "public-assets").resolve()
    destination_root.mkdir(parents=True, exist_ok=True)
    for raw_asset in raw_assets:
        assert isinstance(raw_asset, dict)
        key = (case.id, str(raw_asset["id"]))
        entry = index.get(key)
        if entry is None:
            raise ValueError(f"Missing cached asset for {case.id}/{raw_asset['id']}")
        cache_relative = safe_relative(str(entry["cache_path"]))
        source = (root / cache_relative).resolve()
        if not source.is_relative_to(root) or not source.is_file():
            raise ValueError(f"Cached asset is missing or unsafe: {source}")
        expected_digest = str(entry["sha256"])
        if _sha256_file(source) != expected_digest:
            raise ValueError(f"Cached asset digest mismatch: {source}")

        target_relative = safe_relative(str(raw_asset["target"]))
        destination = (destination_root / target_relative).resolve()
        if not destination.is_relative_to(destination_root):
            raise ValueError(f"Public asset target escapes workspace: {target_relative}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        item: JsonObject = dict(raw_asset)
        item["local_path"] = str(destination.relative_to(workspace))
        item["sha256"] = expected_digest
        materialized.append(item)
    return materialized


def public_asset_prompt_items(case: Case) -> list[JsonObject]:
    raw_assets = case.data.get("public_assets", [])
    assert isinstance(raw_assets, list)
    return [dict(item) for item in raw_assets if isinstance(item, dict)]


def _fetch_asset(
    case: Case,
    asset: JsonObject,
    root: Path,
    *,
    timeout_seconds: int,
    max_asset_bytes: int,
) -> JsonObject:
    target_relative = safe_relative(str(asset["target"]))
    case_root = (root / case.id).resolve()
    destination = (case_root / target_relative).resolve()
    if not destination.is_relative_to(case_root):
        raise ValueError(f"Public asset target escapes cache: {target_relative}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(  # noqa: S310 - URL is validated against an HTTPS allowlist.
        str(asset["url"]),
        headers={
            "User-Agent": "aws-agent-eval/0.2 (+https://github.com/tsuji-tomonori/aws-agent-test)",
            "Accept": "*/*",
        },
    )
    digest = hashlib.sha256()
    size = 0
    resolved_url = str(asset["url"])
    response_content_type = ""
    etag: str | None = None
    last_modified: str | None = None
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            resolved_url = str(response.geturl())
            _validate_public_https_url(case.id, resolved_url)
            response_content_type = response.headers.get_content_type()
            etag = response.headers.get("ETag")
            last_modified = response.headers.get("Last-Modified")
            declared_length = response.headers.get("Content-Length")
            if declared_length is not None and int(declared_length) > max_asset_bytes:
                raise ValueError(f"Public asset exceeds {max_asset_bytes} bytes: {asset['url']}")
            with temporary.open("wb") as stream:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > max_asset_bytes:
                        raise ValueError(
                            f"Public asset exceeds {max_asset_bytes} bytes: {asset['url']}"
                        )
                    digest.update(chunk)
                    stream.write(chunk)
    except (OSError, urllib.error.URLError, ValueError) as exc:
        temporary.unlink(missing_ok=True)
        raise ValueError(f"Failed to fetch public asset {asset['url']}: {exc}") from exc

    temporary.replace(destination)
    expected_media_type = str(asset["media_type"])
    if response_content_type and not _media_type_compatible(
        expected_media_type, response_content_type
    ):
        destination.unlink(missing_ok=True)
        raise ValueError(
            f"Unexpected media type for {asset['url']}: "
            f"expected {expected_media_type}, got {response_content_type}"
        )

    cache_relative = destination.relative_to(root)
    return {
        "case_id": case.id,
        "asset_id": asset["id"],
        "role": asset["role"],
        "url": asset["url"],
        "resolved_url": resolved_url,
        "source_page_url": asset["source_page_url"],
        "cache_path": str(cache_relative),
        "media_type": response_content_type or expected_media_type,
        "bytes": size,
        "sha256": digest.hexdigest(),
        "etag": etag,
        "last_modified": last_modified,
    }


def _dataset_cache_root(dataset: Dataset, cache_dir: Path) -> Path:
    root = (cache_dir.resolve() / dataset.id / dataset.version).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _validate_public_https_url(case_id: str, value: str) -> None:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError(f"{case_id}: public asset URL must use HTTPS: {value}")
    if parsed.hostname not in ALLOWED_PUBLIC_ASSET_HOSTS:
        raise ValueError(f"{case_id}: public asset host is not allowed: {parsed.hostname}")
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError(f"{case_id}: public asset URL contains forbidden components: {value}")


def _media_type_compatible(expected: str, actual: str) -> bool:
    if expected == actual:
        return True
    if expected.startswith("text/") and actual in {
        "application/octet-stream",
        "binary/octet-stream",
    }:
        return True
    return False


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

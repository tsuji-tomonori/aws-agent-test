from __future__ import annotations

import re
from urllib.parse import quote

_BASE_URL = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws"
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")


def build_public_offer_url(
    service_code: str,
    *,
    region_code: str | None = None,
    version: str = "current",
    file_format: str = "json",
) -> str:
    """Build a public AWS Price List offer-file URL without AWS credentials.

    The returned URL points to AWS-hosted bulk price-list content. This function only
    constructs a URL; it never loads AWS SDK credentials or calls an account API.
    """
    service = _segment(service_code, "service_code")
    selected_version = _segment(version, "version")
    selected_format = file_format.casefold()
    if selected_format not in {"json", "csv"}:
        raise ValueError("file_format must be 'json' or 'csv'")

    parts = [_BASE_URL, quote(service, safe=""), quote(selected_version, safe="")]
    if region_code is not None:
        parts.append(quote(_segment(region_code, "region_code"), safe=""))
    parts.append(f"index.{selected_format}")
    return "/".join(parts)


def build_public_region_index_url(service_code: str, *, version: str = "current") -> str:
    """Build the public region-index URL for an AWS service offer."""
    service = _segment(service_code, "service_code")
    selected_version = _segment(version, "version")
    return f"{_BASE_URL}/{quote(service, safe='')}/{quote(selected_version, safe='')}/region_index.json"


def _segment(value: str, label: str) -> str:
    if not value or not _SAFE_SEGMENT.fullmatch(value):
        raise ValueError(f"{label} contains an unsafe URL segment")
    return value

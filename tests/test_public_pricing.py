import pytest

from aws_agent_eval.public_pricing import (
    build_public_offer_url,
    build_public_region_index_url,
)


def test_builds_credential_free_public_offer_urls() -> None:
    assert build_public_offer_url("AmazonRDS") == (
        "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonRDS/current/index.json"
    )
    assert build_public_offer_url("AmazonRDS", region_code="us-east-1") == (
        "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/"
        "AmazonRDS/current/us-east-1/index.json"
    )
    assert build_public_region_index_url("AmazonRDS") == (
        "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/"
        "AmazonRDS/current/region_index.json"
    )


def test_rejects_unsafe_url_segments() -> None:
    with pytest.raises(ValueError, match="unsafe"):
        build_public_offer_url("../secrets")
    with pytest.raises(ValueError, match="file_format"):
        build_public_offer_url("AmazonRDS", file_format="xml")

"""check_response: the rules for reading SWPC's HTTP answers, without a client."""

from pathlib import Path

import pytest

from swpc_kit.errors import RateLimited, SourceNotReady, UnexpectedContent
from swpc_kit.http import check_response
from swpc_kit.parse import parse_planetary_k_index

URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
FIXTURES = Path(__file__).parent / "fixtures"


def test_a_200_with_data_passes_and_the_parser_reads_the_body() -> None:
    body = (FIXTURES / "kp-3h" / "2026-10-15.json").read_bytes()
    check_response(200, {"Content-Type": "application/json"}, url=URL)
    assert parse_planetary_k_index(body).values


def test_a_200_without_content_type_passes() -> None:
    check_response(200, {}, url=URL)


@pytest.mark.parametrize("content_type", ["text/html", "text/html; charset=utf-8"])
def test_an_html_page_is_unexpected(content_type: str) -> None:
    with pytest.raises(UnexpectedContent, match="HTML"):
        check_response(200, {"content-type": content_type}, url=URL)


def test_a_429_is_rate_limited_with_its_retry_after() -> None:
    with pytest.raises(RateLimited, match="429") as info:
        check_response(429, {"retry-after": "120"}, url=URL)
    assert info.value.retry_after == "120"
    # Code that catches SourceNotReady today keeps working.
    assert isinstance(info.value, SourceNotReady)


def test_a_429_without_retry_after() -> None:
    with pytest.raises(RateLimited) as info:
        check_response(429, {}, url=URL)
    assert info.value.retry_after is None


@pytest.mark.parametrize("status", [408, 425, 500, 502, 503, 504])
def test_transient_statuses_are_not_ready_and_not_rate_limited(status: int) -> None:
    with pytest.raises(SourceNotReady, match=str(status)) as info:
        check_response(status, {"Retry-After": "60"}, url=URL)
    assert not isinstance(info.value, RateLimited)


@pytest.mark.parametrize("status", [301, 302, 307, 308])
def test_a_redirect_is_unexpected_with_its_location(status: int) -> None:
    moved = "https://www.weather.gov/notification/"
    with pytest.raises(UnexpectedContent, match=r"weather\.gov") as info:
        check_response(status, {"LOCATION": moved}, url=URL)
    assert info.value.status == status
    assert info.value.location == moved


@pytest.mark.parametrize("status", [201, 204, 400, 403, 404, 410])
def test_other_statuses_are_unexpected(status: int) -> None:
    with pytest.raises(UnexpectedContent, match=str(status)) as info:
        check_response(status, {}, url=URL)
    assert info.value.status == status
    assert info.value.location is None


def test_a_304_is_the_callers_to_handle() -> None:
    # Only the caller holds the copy that a 304 refers to.
    with pytest.raises(ValueError, match="304"):
        check_response(304, {}, url=URL)

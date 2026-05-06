"""HTTP client and parsers for Blaby waste collections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import html
import re
from typing import Any

try:
    from aiohttp import ClientError, ClientSession
except ImportError:  # pragma: no cover - fallback for parser-only test environments
    ClientError = Exception
    ClientSession = Any

from .const import BASE_URL, COLLECTIONS_PATH, SET_LOCATION_PATH, USER_AGENT

ADDRESS_RE = re.compile(
    r'href="set-location\.php\?ref=(?P<ref>\d+)&redirect=collections[^"]*"><strong>(?P<label>.*?)</strong>',
    re.IGNORECASE | re.DOTALL,
)
COLLECTION_DAY_RE = re.compile(
    r'<h2 class="collection-day">Your collection day is (?P<day>[^<]+)</h2>',
    re.IGNORECASE,
)
NO_COLLECTIONS_RE = re.compile(
    r'<h2 class="collection-day">(?P<message>No domestic refuse or recycling collection information available for this property\.)</h2>',
    re.IGNORECASE,
)
COLLECTION_BLOCK_RE = re.compile(
    r'<span class="box-item [^"]*"[^>]*>\s*<h2>(?P<name>[^<]+)</h2>(?P<body>.*?)</span>',
    re.IGNORECASE | re.DOTALL,
)
LOCATION_RE = re.compile(
    r"Displaying collection dates near to\s*<br\s*/?><strong>(?P<address>.*?)</strong>",
    re.IGNORECASE | re.DOTALL,
)
DATE_RE = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
TAG_RE = re.compile(r"<[^>]+>")


class BlabyWasteError(Exception):
    """Base Blaby waste error."""


class BlabyWasteCommunicationError(BlabyWasteError):
    """Communication error while talking to Blaby."""


class BlabyWasteParseError(BlabyWasteError):
    """Unexpected response content from Blaby."""


@dataclass(slots=True, frozen=True)
class AddressOption:
    """A selectable address from the postcode lookup."""

    location_ref: str
    label: str


@dataclass(slots=True, frozen=True)
class Collection:
    """Collection details for one waste stream."""

    name: str
    next_date: date
    following_date: date | None


@dataclass(slots=True, frozen=True)
class CollectionResult:
    """Parsed collection data for a property."""

    address: str
    collection_day: str
    collections: dict[str, Collection]


class BlabyWasteClient:
    """Client for the Blaby collections website."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session

    async def lookup_addresses(self, postcode: str) -> list[AddressOption]:
        """Return selectable addresses for a postcode."""
        normalized = normalize_postcode(postcode)
        html_text = await self._get(
            f"{BASE_URL}{COLLECTIONS_PATH}",
            params={"address": normalized, "location": "change"},
        )
        return _parse_address_options(html_text)

    async def fetch_collections(self, location_ref: str) -> CollectionResult:
        """Return collection data for a selected address."""
        html_text = await self._get(
            f"{BASE_URL}{SET_LOCATION_PATH}",
            params={
                "ref": location_ref,
                "redirect": "collections",
                "rememberloc": "",
            },
        )
        return _parse_collection_page(html_text)

    async def _get(self, url: str, params: dict[str, str]) -> str:
        """GET a page from the council site."""
        try:
            async with self._session.get(
                url,
                params=params,
                headers={"User-Agent": USER_AGENT},
                raise_for_status=True,
            ) as response:
                return await response.text()
        except ClientError as err:
            raise BlabyWasteCommunicationError(
                f"Error requesting {url}: {err}"
            ) from err


def normalize_postcode(postcode: str) -> str:
    """Normalize a UK postcode for lookup."""
    return postcode.replace(" ", "").upper()


def _parse_collection_page(html_text: str) -> CollectionResult:
    """Parse the main collections page."""
    day_match = COLLECTION_DAY_RE.search(html_text)
    location_match = LOCATION_RE.search(html_text)
    no_collections_match = NO_COLLECTIONS_RE.search(html_text)

    if no_collections_match:
        return CollectionResult(
            address=_clean_text(location_match["address"]) if location_match else "",
            collection_day=_clean_text(no_collections_match["message"]),
            collections={},
        )

    if not day_match or not location_match:
        raise BlabyWasteParseError("Could not find the collection summary on the page")

    collections: dict[str, Collection] = {}
    for match in COLLECTION_BLOCK_RE.finditer(html_text):
        name = _clean_text(match["name"])
        dates = [datetime.strptime(value, "%d/%m/%Y").date() for value in DATE_RE.findall(match["body"])]
        if not dates:
            continue

        collections[name] = Collection(
            name=name,
            next_date=dates[0],
            following_date=dates[1] if len(dates) > 1 else None,
        )

    if not collections:
        raise BlabyWasteParseError("No collection dates were found on the page")

    return CollectionResult(
        address=_clean_text(location_match["address"]),
        collection_day=_clean_text(day_match["day"]),
        collections=collections,
    )


def _parse_address_options(html_text: str) -> list[AddressOption]:
    """Parse selectable addresses from the postcode lookup page."""
    options = [
        AddressOption(match["ref"], _clean_text(match["label"]))
        for match in ADDRESS_RE.finditer(html_text)
    ]

    deduped: dict[str, AddressOption] = {}
    for option in options:
        deduped[option.location_ref] = option

    return list(deduped.values())


def _clean_text(value: str) -> str:
    """Strip HTML and normalize whitespace."""
    cleaned = TAG_RE.sub(" ", value.replace("<br>", ", ").replace("<br />", ", "))
    cleaned = html.unescape(cleaned)
    return " ".join(cleaned.split())

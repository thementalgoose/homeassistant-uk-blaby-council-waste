"""Live integration tests against the Blaby collections website."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen
import http.cookiejar


ROOT = Path(__file__).resolve().parents[2]
INTEGRATION_ROOT = ROOT / "custom_components" / "blaby_waste"
POSTCODE = "LE192EL"
EXPECTED_FIRST_ADDRESS = "Ivy House 2 Desford Road, Narborough, LE19 2EL"
NO_COLLECTIONS_POSTCODE = "LE192EP"
NO_COLLECTIONS_FIRST_ADDRESS = "Council Offices Desford Road, Narborough, LE19 2EP"
OUTSIDE_AREA_POSTCODE = "SW11 8DD"
USER_AGENT = "UK-Blaby-Council-Waste-IntegrationTests/1.0"


def _load_api_module():
    """Load the integration API module without importing Home Assistant."""
    custom_components = types.ModuleType("custom_components")
    custom_components.__path__ = [str((ROOT / "custom_components").resolve())]
    sys.modules.setdefault("custom_components", custom_components)

    blaby_pkg = types.ModuleType("custom_components.blaby_waste")
    blaby_pkg.__path__ = [str(INTEGRATION_ROOT.resolve())]
    sys.modules.setdefault("custom_components.blaby_waste", blaby_pkg)

    for name in ("const", "api"):
        module_name = f"custom_components.blaby_waste.{name}"
        if module_name in sys.modules:
            continue

        spec = importlib.util.spec_from_file_location(
            module_name, INTEGRATION_ROOT / f"{name}.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)

    return sys.modules["custom_components.blaby_waste.api"]


API = _load_api_module()


def _get_text(url: str, params: dict[str, str]) -> str:
    """Fetch a page from the live site."""
    request = Request(
        f"{url}?{urlencode(params)}",
        headers={"User-Agent": USER_AGENT},
    )
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def _build_browser_session():
    """Create a cookie-aware opener to mimic the browser flow."""
    cookie_jar = http.cookiejar.CookieJar()
    return build_opener(HTTPCookieProcessor(cookie_jar))


class TestLiveBlabySite(unittest.TestCase):
    """Validate the live website still matches the parser assumptions."""

    def test_lookup_page_returns_addresses(self) -> None:
        html_text = _get_text(
            f"{API.BASE_URL}{API.COLLECTIONS_PATH}",
            {"address": POSTCODE, "location": "change"},
        )

        options = API._parse_address_options(html_text)

        self.assertGreater(len(options), 0)
        self.assertEqual(options[0].label, EXPECTED_FIRST_ADDRESS)
        self.assertTrue(all(item.location_ref.isdigit() for item in options))

    def test_collection_page_parses_selected_property(self) -> None:
        opener = _build_browser_session()
        lookup_request = Request(
            (
                f"{API.BASE_URL}{API.COLLECTIONS_PATH}?"
                f"{urlencode({'address': POSTCODE, 'location': 'change'})}"
            ),
            headers={"User-Agent": USER_AGENT},
        )
        with opener.open(lookup_request, timeout=30) as response:
            lookup_html = response.read().decode("utf-8")

        options = API._parse_address_options(lookup_html)
        self.assertGreater(len(options), 0)

        collections_request = Request(
            (
                f"{API.BASE_URL}{API.SET_LOCATION_PATH}?"
                f"{urlencode({
                "ref": options[0].location_ref,
                "redirect": "collections",
                "rememberloc": "",
                })}"
            ),
            headers={"User-Agent": USER_AGENT},
        )
        with opener.open(collections_request, timeout=30) as response:
            collections_html = response.read().decode("utf-8")

        result = API._parse_collection_page(collections_html)

        self.assertEqual(options[0].label, EXPECTED_FIRST_ADDRESS)
        self.assertEqual(result.address, EXPECTED_FIRST_ADDRESS)
        self.assertTrue(result.collection_day)
        self.assertGreater(len(result.collections), 0)

        for collection in result.collections.values():
            self.assertIsNotNone(collection.next_date)
            if collection.following_date is not None:
                self.assertGreaterEqual(collection.following_date, collection.next_date)

    def test_no_collection_address_returns_empty_collections(self) -> None:
        opener = _build_browser_session()
        lookup_request = Request(
            (
                f"{API.BASE_URL}{API.COLLECTIONS_PATH}?"
                f"{urlencode({'address': NO_COLLECTIONS_POSTCODE, 'location': 'change'})}"
            ),
            headers={"User-Agent": USER_AGENT},
        )
        with opener.open(lookup_request, timeout=30) as response:
            lookup_html = response.read().decode("utf-8")

        options = API._parse_address_options(lookup_html)
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0].label, NO_COLLECTIONS_FIRST_ADDRESS)

        collections_request = Request(
            (
                f"{API.BASE_URL}{API.SET_LOCATION_PATH}?"
                f"{urlencode({'ref': options[0].location_ref, 'redirect': 'collections', 'rememberloc': ''})}"
            ),
            headers={"User-Agent": USER_AGENT},
        )
        with opener.open(collections_request, timeout=30) as response:
            collections_html = response.read().decode("utf-8")

        result = API._parse_collection_page(collections_html)

        self.assertEqual(result.collections, {})
        self.assertEqual(
            result.collection_day,
            "No domestic refuse or recycling collection information available for this property.",
        )

    def test_outside_area_postcode_returns_zero_addresses(self) -> None:
        html_text = _get_text(
            f"{API.BASE_URL}{API.COLLECTIONS_PATH}",
            {"address": OUTSIDE_AREA_POSTCODE.replace(" ", ""), "location": "change"},
        )

        options = API._parse_address_options(html_text)

        self.assertEqual(options, [])


if __name__ == "__main__":
    unittest.main()

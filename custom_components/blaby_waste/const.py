"""Constants for the Blaby waste integration."""

from datetime import timedelta

DOMAIN = "blaby_waste"
NAME = "UK Blaby Council Waste"

BASE_URL = "https://my.blaby.gov.uk"
COLLECTIONS_PATH = "/collections"
SET_LOCATION_PATH = "/set-location.php"

CONF_ADDRESS = "address"
CONF_POSTCODE = "postcode"
CONF_LOCATION_REF = "location_ref"
CONF_SCAN_INTERVAL_HOURS = "scan_interval_hours"

DEFAULT_SCAN_INTERVAL_HOURS = 24
DEFAULT_SCAN_INTERVAL = timedelta(hours=DEFAULT_SCAN_INTERVAL_HOURS)

ATTR_FOLLOWING_DATE = "following_date"
ATTR_NEXT_DATE = "next_date"
ATTR_DAYS_UNTIL = "days_until"
ATTR_DAYS_UNTIL_COUNT = "days_until_count"
ATTR_COLLECTION_DAY = "collection_day"
ATTR_ADDRESS = "address"

USER_AGENT = "HomeAssistant-BlabyWaste/1.0"

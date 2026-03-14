"""Constants for the SentryBox integration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any
from urllib.parse import SplitResult, urlsplit, urlunsplit

from homeassistant.const import Platform

DOMAIN = "sentrybox"
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CAMERA,
    Platform.SENSOR,
]

CONF_CONFIDENCE_THRESHOLD = "confidence_threshold"
CONF_CROP_HEIGHT = "crop_height"
CONF_CROP_WIDTH = "crop_width"
CONF_CROP_X = "crop_x"
CONF_CROP_Y = "crop_y"
CONF_CUSTOM_DETECTION_LABEL = "custom_detection_label"
CONF_DETECTION_PROFILE = "detection_profile"
CONF_DETECTION_PROMPT = "detection_prompt"
CONF_FFMPEG_TIMEOUT = "ffmpeg_timeout"
CONF_NEGATIVE_DETECTIONS_REQUIRED = "negative_detections_required"
CONF_OLLAMA_BASE_URL = "ollama_base_url"
CONF_OLLAMA_MODEL = "ollama_model"
CONF_OLLAMA_TIMEOUT = "ollama_timeout"
CONF_POLL_INTERVAL = "poll_interval"
CONF_POSITIVE_DETECTIONS_REQUIRED = "positive_detections_required"
CONF_RETAIN_LATEST_SNAPSHOT = "retain_latest_snapshot"
CONF_STREAM_URL = "stream_url"

ATTR_ENTRY_ID = "entry_id"

DEFAULT_NAME = "SentryBox"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "gemma3:4b"
DEFAULT_POLL_INTERVAL = 60
DEFAULT_CONFIDENCE_THRESHOLD = 0.7
DEFAULT_RETAIN_LATEST_SNAPSHOT = False
DEFAULT_POSITIVE_DETECTIONS_REQUIRED = 2
DEFAULT_NEGATIVE_DETECTIONS_REQUIRED = 2
DEFAULT_FFMPEG_TIMEOUT = 20
DEFAULT_OLLAMA_TIMEOUT = 45

DETECTION_PROFILE_PACKAGE = "package_delivery"
DETECTION_PROFILE_GARBAGE = "garbage_truck_pickup"
DETECTION_PROFILE_CUSTOM = "custom"
DEFAULT_DETECTION_PROFILE = DETECTION_PROFILE_PACKAGE


@dataclass(slots=True, frozen=True)
class DetectionProfileDefinition:
    """Metadata for a built-in detection profile."""

    key: str
    option_label: str
    detection_label: str
    binary_sensor_name: str
    icon: str
    default_prompt: str


LEGACY_PACKAGE_DETECTION_PROMPT = (
    "You are analyzing a security camera image of a home entrance. Determine "
    "whether a delivery package is currently visible at or immediately next to "
    "the front door, doorstep, porch landing, or entryway. Only answer based on "
    "objects that appear to be actual delivered parcels such as cardboard "
    "boxes, padded mailers, shipping envelopes, or delivery bags placed at the "
    "entrance. Ignore unrelated objects, distant items, decorations, shoes, "
    "furniture, shadows, and people. Return strict JSON with keys: "
    "package_detected (true or false), confidence (0.0 to 1.0), summary (short string)."
)

PACKAGE_DETECTION_PROMPT = (
    "You are analyzing a security camera image of a home entrance. Determine "
    "whether a delivery package is currently visible at or immediately next to "
    "the front door, doorstep, porch landing, or entryway. Only answer based on "
    "objects that appear to be actual delivered parcels such as cardboard "
    "boxes, padded mailers, shipping envelopes, or delivery bags placed at the "
    "entrance. Ignore unrelated objects, distant items, decorations, shoes, "
    "furniture, shadows, reflections, and people. If you are uncertain, answer "
    "false. Return strict JSON with keys: event_detected (true or false), "
    "confidence (0.0 to 1.0), summary (short string)."
)

GARBAGE_TRUCK_PICKUP_PROMPT = (
    "You are analyzing a security camera image of a driveway or curbside trash "
    "collection area. Determine whether a garbage truck or recycling truck is "
    "currently at the bins and actively picking up, servicing, or immediately "
    "positioned to service trash or recycling bins placed at the end of the "
    "driveway or curb. Only answer true when the truck is clearly present at the "
    "bins for pickup. Ignore ordinary cars, parked trucks that are not servicing "
    "the bins, distant street traffic, bins sitting alone, people, shadows, and "
    "reflections. If you are uncertain, answer false. Return strict JSON with "
    "keys: event_detected (true or false), confidence (0.0 to 1.0), summary "
    "(short string)."
)

DEFAULT_DETECTION_PROMPT = PACKAGE_DETECTION_PROMPT

DETECTION_PROFILES: dict[str, DetectionProfileDefinition] = {
    DETECTION_PROFILE_PACKAGE: DetectionProfileDefinition(
        key=DETECTION_PROFILE_PACKAGE,
        option_label="Package at door",
        detection_label="package delivery",
        binary_sensor_name="Package Detected",
        icon="mdi:package-variant-closed-check",
        default_prompt=PACKAGE_DETECTION_PROMPT,
    ),
    DETECTION_PROFILE_GARBAGE: DetectionProfileDefinition(
        key=DETECTION_PROFILE_GARBAGE,
        option_label="Garbage truck pickup",
        detection_label="garbage truck pickup",
        binary_sensor_name="Trash Pickup Detected",
        icon="mdi:trash-can",
        default_prompt=GARBAGE_TRUCK_PICKUP_PROMPT,
    ),
    DETECTION_PROFILE_CUSTOM: DetectionProfileDefinition(
        key=DETECTION_PROFILE_CUSTOM,
        option_label="Custom detection",
        detection_label="custom detection",
        binary_sensor_name="Target Detected",
        icon="mdi:crosshairs-question",
        default_prompt="",
    ),
}

OLLAMA_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "event_detected": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "summary": {"type": "string"},
    },
    "required": ["event_detected", "confidence", "summary"],
    "additionalProperties": False,
}

SNAPSHOT_DIRECTORY = ".sentrybox"
SERVICE_REANALYZE_NOW = "reanalyze_now"

MAX_SUMMARY_LENGTH = 255


def get_detection_profile(profile_key: str | None) -> DetectionProfileDefinition:
    """Return a profile definition, falling back to the package profile."""
    if profile_key and profile_key in DETECTION_PROFILES:
        return DETECTION_PROFILES[profile_key]
    return DETECTION_PROFILES[DEFAULT_DETECTION_PROFILE]


def get_custom_detection_label(
    data: Mapping[str, Any], options: Mapping[str, Any]
) -> str:
    """Return the configured custom detection label."""
    return str(
        get_entry_value(data, options, CONF_CUSTOM_DETECTION_LABEL) or ""
    ).strip()


def get_detection_label(data: Mapping[str, Any], options: Mapping[str, Any]) -> str:
    """Return the human-readable detection label for an entry."""
    profile = get_detection_profile(
        get_entry_value(data, options, CONF_DETECTION_PROFILE)
    )
    if profile.key == DETECTION_PROFILE_CUSTOM:
        return get_custom_detection_label(data, options) or "custom detection"
    return profile.detection_label


def get_binary_sensor_name(data: Mapping[str, Any], options: Mapping[str, Any]) -> str:
    """Return the binary sensor name for an entry."""
    profile = get_detection_profile(
        get_entry_value(data, options, CONF_DETECTION_PROFILE)
    )
    if profile.key == DETECTION_PROFILE_CUSTOM:
        custom_label = get_custom_detection_label(data, options)
        return f"{custom_label} Detected" if custom_label else profile.binary_sensor_name
    return profile.binary_sensor_name


def get_binary_sensor_icon(data: Mapping[str, Any], options: Mapping[str, Any]) -> str:
    """Return the binary sensor icon for an entry."""
    profile = get_detection_profile(
        get_entry_value(data, options, CONF_DETECTION_PROFILE)
    )
    return profile.icon


def get_default_detection_prompt(
    profile_key: str | None,
    *,
    custom_label: str = "",
) -> str:
    """Return the built-in default prompt for a profile."""
    profile = get_detection_profile(profile_key)
    if profile.key != DETECTION_PROFILE_CUSTOM:
        return profile.default_prompt

    label = custom_label.strip() or "custom event or object"
    return (
        "You are analyzing a security camera image. Determine whether the "
        f"following target event or object is clearly visible in the intended "
        f"scene area: {label}. Only answer true when the target is clearly "
        "present or actively happening in the relevant area. Ignore unrelated "
        "objects, distant activity, shadows, reflections, and uncertain cases. "
        "If you are uncertain, answer false. Return strict JSON with keys: "
        "event_detected (true or false), confidence (0.0 to 1.0), summary "
        "(short string)."
    )


def get_effective_detection_prompt(
    data: Mapping[str, Any],
    options: Mapping[str, Any],
) -> str:
    """Return the effective prompt for an entry."""
    profile_key = get_entry_value(data, options, CONF_DETECTION_PROFILE)
    custom_label = get_custom_detection_label(data, options)
    prompt = str(get_entry_value(data, options, CONF_DETECTION_PROMPT) or "").strip()
    if not prompt or prompt == LEGACY_PACKAGE_DETECTION_PROMPT:
        return get_default_detection_prompt(profile_key, custom_label=custom_label)
    return prompt


def get_default_options(
    *,
    profile_key: str = DEFAULT_DETECTION_PROFILE,
    custom_label: str = "",
) -> dict[str, Any]:
    """Return the default options payload for a new entry."""
    return {
        CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
        CONF_DETECTION_PROFILE: profile_key,
        CONF_CUSTOM_DETECTION_LABEL: custom_label,
        CONF_DETECTION_PROMPT: get_default_detection_prompt(
            profile_key,
            custom_label=custom_label,
        ),
        CONF_CONFIDENCE_THRESHOLD: DEFAULT_CONFIDENCE_THRESHOLD,
        CONF_RETAIN_LATEST_SNAPSHOT: DEFAULT_RETAIN_LATEST_SNAPSHOT,
        CONF_POSITIVE_DETECTIONS_REQUIRED: DEFAULT_POSITIVE_DETECTIONS_REQUIRED,
        CONF_NEGATIVE_DETECTIONS_REQUIRED: DEFAULT_NEGATIVE_DETECTIONS_REQUIRED,
        CONF_FFMPEG_TIMEOUT: DEFAULT_FFMPEG_TIMEOUT,
        CONF_OLLAMA_TIMEOUT: DEFAULT_OLLAMA_TIMEOUT,
        CONF_CROP_X: None,
        CONF_CROP_Y: None,
        CONF_CROP_WIDTH: None,
        CONF_CROP_HEIGHT: None,
    }


def get_entry_value(data: Mapping[str, Any], options: Mapping[str, Any], key: str) -> Any:
    """Return the effective value for a config entry key."""
    if key in options:
        return options[key]
    return data.get(key, get_default_options().get(key))


def normalize_url(url: str) -> str:
    """Normalize a URL for hashing and duplicate detection."""
    parsed = urlsplit(url.strip())
    netloc = parsed.netloc.lower()
    return urlunsplit(
        SplitResult(
            scheme=parsed.scheme.lower(),
            netloc=netloc,
            path=parsed.path or "",
            query=parsed.query,
            fragment="",
        )
    )


def make_entry_unique_id(
    stream_url: str,
    model_name: str,
    profile_key: str = DEFAULT_DETECTION_PROFILE,
    custom_label: str = "",
) -> str:
    """Build a stable unique ID from the stream URL, model, and detection profile."""
    digest = sha256(
        (
            f"{normalize_url(stream_url)}|{model_name.strip().lower()}|"
            f"{profile_key.strip().lower()}|{custom_label.strip().lower()}"
        ).encode("utf-8")
    ).hexdigest()
    return f"{DOMAIN}_{digest}"


def make_legacy_entry_unique_id(stream_url: str, model_name: str) -> str:
    """Build the legacy unique ID used before profile-aware entries."""
    digest = sha256(
        f"{normalize_url(stream_url)}|{model_name.strip().lower()}".encode("utf-8")
    ).hexdigest()
    return f"{DOMAIN}_{digest}"


def redact_url(url: str) -> str:
    """Redact credentials from a URL before logging it."""
    parsed = urlsplit(url)
    hostname = parsed.hostname or ""
    if parsed.port:
        hostname = f"{hostname}:{parsed.port}"
    if parsed.username or parsed.password:
        netloc = f"***:***@{hostname}"
    else:
        netloc = parsed.netloc
    return urlunsplit(
        SplitResult(
            scheme=parsed.scheme,
            netloc=netloc,
            path=parsed.path,
            query=parsed.query,
            fragment="",
        )
    )

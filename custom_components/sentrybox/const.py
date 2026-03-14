"""Constants for the SentryBox integration."""

from __future__ import annotations

from collections.abc import Mapping
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

CONF_CROP_HEIGHT = "crop_height"
CONF_CROP_WIDTH = "crop_width"
CONF_CROP_X = "crop_x"
CONF_CROP_Y = "crop_y"
CONF_FFMPEG_TIMEOUT = "ffmpeg_timeout"
CONF_CONFIDENCE_THRESHOLD = "confidence_threshold"
CONF_DETECTION_PROMPT = "detection_prompt"
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
DEFAULT_DETECTION_PROMPT = (
    "You are analyzing a security camera image of a home entrance. Determine "
    "whether a delivery package is currently visible at or immediately next to "
    "the front door, doorstep, porch landing, or entryway. Only answer based on "
    "objects that appear to be actual delivered parcels such as cardboard "
    "boxes, padded mailers, shipping envelopes, or delivery bags placed at the "
    "entrance. Ignore unrelated objects, distant items, decorations, shoes, "
    "furniture, shadows, and people. Return strict JSON with keys: "
    "package_detected (true or false), confidence (0.0 to 1.0), summary (short string)."
)

OLLAMA_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "package_detected": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "summary": {"type": "string"},
    },
    "required": ["package_detected", "confidence", "summary"],
    "additionalProperties": False,
}

SNAPSHOT_DIRECTORY = ".sentrybox"
SERVICE_REANALYZE_NOW = "reanalyze_now"

MAX_SUMMARY_LENGTH = 255


def get_default_options() -> dict[str, Any]:
    """Return the default options payload for a new entry."""
    return {
        CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
        CONF_DETECTION_PROMPT: DEFAULT_DETECTION_PROMPT,
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


def make_entry_unique_id(stream_url: str, model_name: str) -> str:
    """Build a stable unique ID from the stream URL and model."""
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

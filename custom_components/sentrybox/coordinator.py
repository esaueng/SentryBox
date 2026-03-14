"""Coordinator logic for SentryBox."""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_CONFIDENCE_THRESHOLD,
    CONF_CROP_HEIGHT,
    CONF_CROP_WIDTH,
    CONF_CROP_X,
    CONF_CROP_Y,
    CONF_DETECTION_PROMPT,
    CONF_NEGATIVE_DETECTIONS_REQUIRED,
    CONF_OLLAMA_BASE_URL,
    CONF_OLLAMA_MODEL,
    CONF_POLL_INTERVAL,
    CONF_POSITIVE_DETECTIONS_REQUIRED,
    CONF_RETAIN_LATEST_SNAPSHOT,
    CONF_STREAM_URL,
    DEFAULT_NAME,
    FFMPEG_TIMEOUT_SECONDS,
    MAX_SUMMARY_LENGTH,
    OLLAMA_JSON_SCHEMA,
    OLLAMA_TIMEOUT_SECONDS,
    SNAPSHOT_DIRECTORY,
    get_entry_value,
    redact_url,
)

LOGGER = logging.getLogger(__name__)
SentryBoxConfigEntry = ConfigEntry


@dataclass(slots=True, frozen=True)
class ParsedDetection:
    """The normalized detection payload from Ollama."""

    package_detected: bool
    confidence: float
    summary: str
    raw_response: str


@dataclass(slots=True, frozen=True)
class SentryBoxResult:
    """State exposed by the coordinator."""

    package_detected: bool
    raw_package_detected: bool
    model_package_detected: bool
    confidence: float
    summary: str
    last_analyzed: datetime
    model_name: str
    raw_response: str | None
    snapshot_path: str | None
    confidence_threshold: float
    positive_streak: int
    negative_streak: int
    positive_required: int
    negative_required: int
    error: str | None = None


class SentryBoxCoordinator(DataUpdateCoordinator[SentryBoxResult]):
    """Coordinate frame capture and package analysis."""

    config_entry: SentryBoxConfigEntry

    def __init__(self, hass: HomeAssistant, entry: SentryBoxConfigEntry) -> None:
        """Initialize the coordinator."""
        self.config_entry = entry
        self._session = async_get_clientsession(hass)
        self._positive_streak = 0
        self._negative_streak = 0
        self._stable_detected = False
        self._last_error_fingerprint: str | None = None
        self._last_error_message: str | None = None

        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=entry.title or DEFAULT_NAME,
            update_interval=self._build_update_interval(),
        )

    def _build_update_interval(self):
        seconds = int(
            get_entry_value(
                self.config_entry.data,
                self.config_entry.options,
                CONF_POLL_INTERVAL,
            )
        )
        return timedelta(seconds=seconds)

    @property
    def stream_url(self) -> str:
        """Return the configured stream URL."""
        return self.config_entry.data[CONF_STREAM_URL]

    @property
    def ollama_base_url(self) -> str:
        """Return the Ollama base URL."""
        return self.config_entry.data[CONF_OLLAMA_BASE_URL]

    @property
    def model_name(self) -> str:
        """Return the configured model name."""
        return self.config_entry.data[CONF_OLLAMA_MODEL]

    @property
    def detection_prompt(self) -> str:
        """Return the effective prompt."""
        return get_entry_value(
            self.config_entry.data,
            self.config_entry.options,
            CONF_DETECTION_PROMPT,
        )

    @property
    def confidence_threshold(self) -> float:
        """Return the configured confidence threshold."""
        return float(
            get_entry_value(
                self.config_entry.data,
                self.config_entry.options,
                CONF_CONFIDENCE_THRESHOLD,
            )
        )

    @property
    def retain_latest_snapshot(self) -> bool:
        """Return whether to keep the latest snapshot."""
        return bool(
            get_entry_value(
                self.config_entry.data,
                self.config_entry.options,
                CONF_RETAIN_LATEST_SNAPSHOT,
            )
        )

    @property
    def positive_required(self) -> int:
        """Return consecutive positives required to turn on."""
        return int(
            get_entry_value(
                self.config_entry.data,
                self.config_entry.options,
                CONF_POSITIVE_DETECTIONS_REQUIRED,
            )
        )

    @property
    def negative_required(self) -> int:
        """Return consecutive negatives required to turn off."""
        return int(
            get_entry_value(
                self.config_entry.data,
                self.config_entry.options,
                CONF_NEGATIVE_DETECTIONS_REQUIRED,
            )
        )

    @property
    def crop_region(self) -> tuple[float, float, float, float] | None:
        """Return the configured crop region."""
        values = tuple(
            get_entry_value(self.config_entry.data, self.config_entry.options, key)
            for key in (
                CONF_CROP_X,
                CONF_CROP_Y,
                CONF_CROP_WIDTH,
                CONF_CROP_HEIGHT,
            )
        )
        if any(value is None for value in values):
            return None
        return values  # type: ignore[return-value]

    async def _async_update_data(self) -> SentryBoxResult:
        """Capture a frame, analyze it with Ollama, and update entity state."""
        image_path: str | None = None
        analyzed_at = datetime.now(timezone.utc)

        try:
            image_path = await self.hass.async_add_executor_job(self._capture_frame_sync)
            encoded_image = await self.hass.async_add_executor_job(
                self._encode_image_sync,
                image_path,
            )
            raw_response = await self._async_call_ollama(encoded_image)
            parsed = self._parse_ollama_response(raw_response)
            raw_detected = (
                parsed.package_detected
                and parsed.confidence >= self.confidence_threshold
            )
            stable_detected = self._apply_debounce(raw_detected)
            self._clear_failure_state()
            return SentryBoxResult(
                package_detected=stable_detected,
                raw_package_detected=raw_detected,
                model_package_detected=parsed.package_detected,
                confidence=parsed.confidence,
                summary=parsed.summary,
                last_analyzed=analyzed_at,
                model_name=self.model_name,
                raw_response=parsed.raw_response,
                snapshot_path=image_path if self.retain_latest_snapshot else None,
                confidence_threshold=self.confidence_threshold,
                positive_streak=self._positive_streak,
                negative_streak=self._negative_streak,
                positive_required=self.positive_required,
                negative_required=self.negative_required,
            )
        except UpdateFailed as err:
            self._log_failure_once(type(err).__name__, str(err))
            raise
        except Exception as err:
            self._log_failure_once(type(err).__name__, str(err))
            raise UpdateFailed(str(err)) from err
        finally:
            if image_path and not self.retain_latest_snapshot:
                await self.hass.async_add_executor_job(self._delete_file_sync, image_path)

    def _apply_debounce(self, raw_detected: bool) -> bool:
        """Apply consecutive-result debounce to the raw detection."""
        if raw_detected:
            self._positive_streak += 1
            self._negative_streak = 0
            if self._positive_streak >= self.positive_required:
                self._stable_detected = True
        else:
            self._negative_streak += 1
            self._positive_streak = 0
            if self._negative_streak >= self.negative_required:
                self._stable_detected = False
        return self._stable_detected

    async def _async_call_ollama(self, encoded_image: str) -> str:
        """Send the captured frame to Ollama and return the raw model output."""
        request_url = f"{self.ollama_base_url}/api/chat"
        payload = {
            "model": self.model_name,
            "stream": False,
            "format": OLLAMA_JSON_SCHEMA,
            "options": {"temperature": 0},
            "messages": [
                {
                    "role": "user",
                    "content": self.detection_prompt,
                    "images": [encoded_image],
                }
            ],
        }

        try:
            async with self._session.post(
                request_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=OLLAMA_TIMEOUT_SECONDS),
            ) as response:
                body = await response.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise UpdateFailed(f"Ollama request failed: {err}") from err
        except ValueError as err:
            raise UpdateFailed(f"Ollama returned invalid JSON: {err}") from err

        if not isinstance(body, dict):
            raise UpdateFailed("Ollama returned a non-object JSON response")

        if response.status >= 400:
            error_message = body.get("error", response.reason)
            raise UpdateFailed(f"Ollama returned HTTP {response.status}: {error_message}")

        message = body.get("message", {})
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise UpdateFailed("Ollama response did not include a message content string")
        return content.strip()

    def _parse_ollama_response(self, content: str) -> ParsedDetection:
        """Parse and normalize the model JSON response."""
        parsed_payload: dict[str, Any] | None = None
        try:
            candidate = json.loads(content)
            if isinstance(candidate, dict):
                parsed_payload = candidate
        except json.JSONDecodeError:
            extracted = self._extract_json_object(content)
            if extracted is not None:
                try:
                    candidate = json.loads(extracted)
                    if isinstance(candidate, dict):
                        parsed_payload = candidate
                except json.JSONDecodeError:
                    parsed_payload = None

        if parsed_payload is None:
            LOGGER.debug("SentryBox received malformed JSON from Ollama")
            return ParsedDetection(
                package_detected=False,
                confidence=0.0,
                summary="Model response was not valid JSON",
                raw_response=content,
            )

        package_detected = bool(parsed_payload.get("package_detected", False))
        confidence = parsed_payload.get("confidence", 0.0)
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            confidence = 0.0

        summary = str(parsed_payload.get("summary", "No summary provided")).strip()
        if not summary:
            summary = "No summary provided"
        summary = summary[:MAX_SUMMARY_LENGTH]

        return ParsedDetection(
            package_detected=package_detected,
            confidence=confidence,
            summary=summary,
            raw_response=content,
        )

    def _capture_frame_sync(self) -> str:
        """Capture a still frame from the configured camera stream."""
        target_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        target_path = Path(target_file.name)
        target_file.close()

        snapshot_path = self._snapshot_path()
        if not self.retain_latest_snapshot:
            self._delete_file_sync(str(snapshot_path))

        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-rtsp_transport",
            "tcp",
            "-i",
            self.stream_url,
            "-frames:v",
            "1",
            "-q:v",
            "2",
        ]

        crop_filter = self._crop_filter()
        if crop_filter is not None:
            command.extend(["-vf", crop_filter])

        command.append(str(target_path))

        LOGGER.debug("Capturing frame from %s", redact_url(self.stream_url))

        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=FFMPEG_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as err:
            self._delete_file_sync(str(target_path))
            raise UpdateFailed("ffmpeg is not installed or not in PATH") from err
        except subprocess.TimeoutExpired as err:
            self._delete_file_sync(str(target_path))
            raise UpdateFailed("ffmpeg timed out while capturing a frame") from err
        except subprocess.CalledProcessError as err:
            self._delete_file_sync(str(target_path))
            stderr = (err.stderr or "").strip() or "Unknown ffmpeg error"
            raise UpdateFailed(f"ffmpeg failed to capture a frame: {stderr}") from err

        if self.retain_latest_snapshot:
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target_path), snapshot_path)
            return str(snapshot_path)

        return str(target_path)

    def _snapshot_path(self) -> Path:
        """Return the persistent snapshot path for this entry."""
        return (
            Path(self.hass.config.path(SNAPSHOT_DIRECTORY))
            / f"{self.config_entry.entry_id}.jpg"
        )

    def _crop_filter(self) -> str | None:
        """Return the ffmpeg crop filter for the normalized crop region."""
        if self.crop_region is None:
            return None
        x, y, width, height = self.crop_region
        return (
            f"crop=trunc(iw*{width}):trunc(ih*{height}):"
            f"trunc(iw*{x}):trunc(ih*{y})"
        )

    @staticmethod
    def _encode_image_sync(path: str) -> str:
        """Read and base64-encode an image file."""
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    @staticmethod
    def _delete_file_sync(path: str) -> None:
        """Delete a file if it exists."""
        file_path = Path(path)
        if file_path.exists():
            file_path.unlink(missing_ok=True)

    @staticmethod
    def _extract_json_object(content: str) -> str | None:
        """Extract the first JSON object from a noisy string."""
        start = content.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escaping = False
        for index, char in enumerate(content[start:], start=start):
            if in_string:
                if escaping:
                    escaping = False
                elif char == "\\":
                    escaping = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return content[start : index + 1]
        return None

    def _log_failure_once(self, error_type: str, message: str) -> None:
        """Log a warning once for a repeating error and downgrade repeats to debug."""
        fingerprint = f"{error_type}:{message}"
        if self._last_error_fingerprint == fingerprint:
            LOGGER.debug("SentryBox refresh still failing: %s", message)
            return

        self._last_error_fingerprint = fingerprint
        self._last_error_message = message
        LOGGER.warning("SentryBox refresh failed: %s", message)

    def _clear_failure_state(self) -> None:
        """Clear repeated-failure tracking and log recovery."""
        if self._last_error_message is not None:
            LOGGER.info("SentryBox recovered after error: %s", self._last_error_message)
        self._last_error_fingerprint = None
        self._last_error_message = None

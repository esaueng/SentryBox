"""Config flow for the SentryBox integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_NAME

from .const import (
    CONF_CONFIDENCE_THRESHOLD,
    CONF_CROP_HEIGHT,
    CONF_CROP_WIDTH,
    CONF_CROP_X,
    CONF_CROP_Y,
    CONF_FFMPEG_TIMEOUT,
    CONF_DETECTION_PROMPT,
    CONF_NEGATIVE_DETECTIONS_REQUIRED,
    CONF_OLLAMA_BASE_URL,
    CONF_OLLAMA_MODEL,
    CONF_OLLAMA_TIMEOUT,
    CONF_POLL_INTERVAL,
    CONF_POSITIVE_DETECTIONS_REQUIRED,
    CONF_RETAIN_LATEST_SNAPSHOT,
    CONF_STREAM_URL,
    DEFAULT_NAME,
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    DOMAIN,
    get_default_options,
    get_entry_value,
    make_entry_unique_id,
)


@dataclass(slots=True)
class ValidationResult:
    """Validation result for config or options payloads."""

    errors: dict[str, str]
    cleaned_data: dict[str, Any]


def _coerce_int(
    user_input: dict[str, Any],
    key: str,
    *,
    minimum: int,
    maximum: int,
    error_key: str,
) -> tuple[int | None, str | None]:
    """Parse and validate a bounded integer."""
    try:
        value = int(user_input[key])
    except (TypeError, ValueError):
        return None, error_key

    if value < minimum or value > maximum:
        return None, error_key
    return value, None


def _validate_stream_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"rtsp", "rtsps"} or not parsed.netloc:
        raise ValueError("invalid_stream_url")
    return value.strip()


def _validate_ollama_base_url(value: str) -> str:
    parsed = urlsplit(value.strip().rstrip("/"))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("invalid_ollama_url")
    return value.strip().rstrip("/")


def _parse_optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _validate_crop(cleaned_data: dict[str, Any]) -> None:
    keys = (CONF_CROP_X, CONF_CROP_Y, CONF_CROP_WIDTH, CONF_CROP_HEIGHT)
    values = [cleaned_data[key] for key in keys]
    if all(value is None for value in values):
        return
    if any(value is None for value in values):
        raise ValueError("crop_incomplete")

    x, y, width, height = values
    if any(not 0 <= value <= 1 for value in values):
        raise ValueError("crop_out_of_range")
    if width <= 0 or height <= 0:
        raise ValueError("crop_out_of_range")
    if x + width > 1 or y + height > 1:
        raise ValueError("crop_bounds")


def _validate_options_payload(user_input: dict[str, Any]) -> ValidationResult:
    errors: dict[str, str] = {}
    cleaned_data: dict[str, Any] = {}
    cleaned_data[CONF_NAME] = (
        str(user_input.get(CONF_NAME, DEFAULT_NAME)).strip() or DEFAULT_NAME
    )

    poll_interval, poll_interval_error = _coerce_int(
        user_input,
        CONF_POLL_INTERVAL,
        minimum=5,
        maximum=3600,
        error_key="invalid_poll_interval",
    )
    if poll_interval_error:
        errors[CONF_POLL_INTERVAL] = poll_interval_error
    else:
        cleaned_data[CONF_POLL_INTERVAL] = poll_interval

    ffmpeg_timeout, ffmpeg_timeout_error = _coerce_int(
        user_input,
        CONF_FFMPEG_TIMEOUT,
        minimum=5,
        maximum=300,
        error_key="invalid_ffmpeg_timeout",
    )
    if ffmpeg_timeout_error:
        errors[CONF_FFMPEG_TIMEOUT] = ffmpeg_timeout_error
    else:
        cleaned_data[CONF_FFMPEG_TIMEOUT] = ffmpeg_timeout

    ollama_timeout, ollama_timeout_error = _coerce_int(
        user_input,
        CONF_OLLAMA_TIMEOUT,
        minimum=5,
        maximum=300,
        error_key="invalid_ollama_timeout",
    )
    if ollama_timeout_error:
        errors[CONF_OLLAMA_TIMEOUT] = ollama_timeout_error
    else:
        cleaned_data[CONF_OLLAMA_TIMEOUT] = ollama_timeout

    try:
        cleaned_data[CONF_CONFIDENCE_THRESHOLD] = float(
            user_input[CONF_CONFIDENCE_THRESHOLD]
        )
        if not 0 <= cleaned_data[CONF_CONFIDENCE_THRESHOLD] <= 1:
            raise ValueError("invalid_confidence_threshold")
    except ValueError as err:
        errors[CONF_CONFIDENCE_THRESHOLD] = (
            str(err)
            if str(err) == "invalid_confidence_threshold"
            else "invalid_confidence_threshold"
        )
    except TypeError:
        errors[CONF_CONFIDENCE_THRESHOLD] = "invalid_confidence_threshold"

    for key in (
        CONF_POSITIVE_DETECTIONS_REQUIRED,
        CONF_NEGATIVE_DETECTIONS_REQUIRED,
    ):
        try:
            cleaned_data[key] = int(user_input[key])
            if cleaned_data[key] < 1 or cleaned_data[key] > 10:
                raise ValueError("invalid_debounce_count")
        except ValueError:
            errors[key] = "invalid_debounce_count"
        except TypeError:
            errors[key] = "invalid_debounce_count"

    cleaned_data[CONF_DETECTION_PROMPT] = str(user_input[CONF_DETECTION_PROMPT]).strip()
    cleaned_data[CONF_RETAIN_LATEST_SNAPSHOT] = bool(
        user_input[CONF_RETAIN_LATEST_SNAPSHOT]
    )

    for key in (CONF_CROP_X, CONF_CROP_Y, CONF_CROP_WIDTH, CONF_CROP_HEIGHT):
        try:
            cleaned_data[key] = _parse_optional_float(user_input.get(key))
        except (TypeError, ValueError):
            errors[key] = "invalid_crop_value"

    if not errors:
        try:
            _validate_crop(cleaned_data)
        except ValueError as err:
            crop_error = str(err)
            for key in (CONF_CROP_X, CONF_CROP_Y, CONF_CROP_WIDTH, CONF_CROP_HEIGHT):
                errors[key] = crop_error

    if not cleaned_data[CONF_DETECTION_PROMPT]:
        errors[CONF_DETECTION_PROMPT] = "empty_prompt"

    return ValidationResult(errors=errors, cleaned_data=cleaned_data)


def _validate_config_payload(user_input: dict[str, Any]) -> ValidationResult:
    errors: dict[str, str] = {}
    cleaned_data: dict[str, Any] = {}

    name = str(user_input.get(CONF_NAME, DEFAULT_NAME)).strip() or DEFAULT_NAME
    cleaned_data[CONF_NAME] = name

    try:
        cleaned_data[CONF_STREAM_URL] = _validate_stream_url(user_input[CONF_STREAM_URL])
    except (KeyError, ValueError) as err:
        errors[CONF_STREAM_URL] = str(err)

    try:
        cleaned_data[CONF_OLLAMA_BASE_URL] = _validate_ollama_base_url(
            user_input[CONF_OLLAMA_BASE_URL]
        )
    except (KeyError, ValueError) as err:
        errors[CONF_OLLAMA_BASE_URL] = str(err)

    model_name = str(user_input.get(CONF_OLLAMA_MODEL, "")).strip()
    if not model_name:
        errors[CONF_OLLAMA_MODEL] = "empty_model_name"
    cleaned_data[CONF_OLLAMA_MODEL] = model_name

    return ValidationResult(errors=errors, cleaned_data=cleaned_data)


def _options_schema(current: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=current[CONF_NAME]): str,
            vol.Required(CONF_STREAM_URL, default=current[CONF_STREAM_URL]): str,
            vol.Required(
                CONF_OLLAMA_BASE_URL,
                default=current[CONF_OLLAMA_BASE_URL],
            ): str,
            vol.Required(CONF_OLLAMA_MODEL, default=current[CONF_OLLAMA_MODEL]): str,
            vol.Required(
                CONF_POLL_INTERVAL,
                default=current[CONF_POLL_INTERVAL],
            ): int,
            vol.Required(
                CONF_FFMPEG_TIMEOUT,
                default=current[CONF_FFMPEG_TIMEOUT],
            ): int,
            vol.Required(
                CONF_OLLAMA_TIMEOUT,
                default=current[CONF_OLLAMA_TIMEOUT],
            ): int,
            vol.Required(
                CONF_CONFIDENCE_THRESHOLD,
                default=current[CONF_CONFIDENCE_THRESHOLD],
            ): vol.Coerce(float),
            vol.Required(
                CONF_DETECTION_PROMPT,
                default=current[CONF_DETECTION_PROMPT],
            ): str,
            vol.Required(
                CONF_RETAIN_LATEST_SNAPSHOT,
                default=current[CONF_RETAIN_LATEST_SNAPSHOT],
            ): bool,
            vol.Required(
                CONF_POSITIVE_DETECTIONS_REQUIRED,
                default=current[CONF_POSITIVE_DETECTIONS_REQUIRED],
            ): int,
            vol.Required(
                CONF_NEGATIVE_DETECTIONS_REQUIRED,
                default=current[CONF_NEGATIVE_DETECTIONS_REQUIRED],
            ): int,
            vol.Optional(CONF_CROP_X, default=_display_float(current[CONF_CROP_X])): str,
            vol.Optional(CONF_CROP_Y, default=_display_float(current[CONF_CROP_Y])): str,
            vol.Optional(
                CONF_CROP_WIDTH, default=_display_float(current[CONF_CROP_WIDTH])
            ): str,
            vol.Optional(
                CONF_CROP_HEIGHT, default=_display_float(current[CONF_CROP_HEIGHT])
            ): str,
        }
    )


def _display_float(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.4f}".rstrip("0").rstrip(".")


class SentryBoxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SentryBox."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return SentryBoxOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            validation = _validate_config_payload(user_input)
            errors = validation.errors
            if not errors:
                unique_id = make_entry_unique_id(
                    validation.cleaned_data[CONF_STREAM_URL],
                    validation.cleaned_data[CONF_OLLAMA_MODEL],
                )
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=validation.cleaned_data[CONF_NAME],
                    data=validation.cleaned_data,
                    options=get_default_options(),
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_STREAM_URL): str,
                    vol.Required(
                        CONF_OLLAMA_BASE_URL,
                        default=DEFAULT_OLLAMA_BASE_URL,
                    ): str,
                    vol.Required(
                        CONF_OLLAMA_MODEL,
                        default=DEFAULT_OLLAMA_MODEL,
                    ): str,
                }
            ),
            errors=errors,
        )


class SentryBoxOptionsFlow(OptionsFlowWithReload):
    """Handle SentryBox options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the integration options."""
        errors: dict[str, str] = {}

        current_options = {
            key: get_entry_value(self.config_entry.data, self.config_entry.options, key)
            for key in get_default_options()
        }
        current_options[CONF_NAME] = self.config_entry.title or self.config_entry.data.get(
            CONF_NAME, DEFAULT_NAME
        )
        current_options[CONF_STREAM_URL] = self.config_entry.data[CONF_STREAM_URL]
        current_options[CONF_OLLAMA_BASE_URL] = self.config_entry.data[
            CONF_OLLAMA_BASE_URL
        ]
        current_options[CONF_OLLAMA_MODEL] = self.config_entry.data[CONF_OLLAMA_MODEL]

        if user_input is not None:
            config_validation = _validate_config_payload(user_input)
            options_validation = _validate_options_payload(user_input)
            errors = {
                **config_validation.errors,
                **options_validation.errors,
            }
            if not errors:
                new_unique_id = make_entry_unique_id(
                    config_validation.cleaned_data[CONF_STREAM_URL],
                    config_validation.cleaned_data[CONF_OLLAMA_MODEL],
                )
                for entry in self.hass.config_entries.async_entries(DOMAIN):
                    if (
                        entry.entry_id != self.config_entry.entry_id
                        and entry.unique_id == new_unique_id
                    ):
                        errors["base"] = "already_configured"
                        break

            if not errors:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    title=config_validation.cleaned_data[CONF_NAME],
                    data=config_validation.cleaned_data,
                    unique_id=new_unique_id,
                )
                options_validation.cleaned_data.pop(CONF_NAME, None)
                return self.async_create_entry(
                    title="",
                    data=options_validation.cleaned_data,
                )

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(current_options),
            errors=errors,
        )

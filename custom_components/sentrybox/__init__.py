"""The SentryBox integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_ENTRY_ID,
    DOMAIN,
    PLATFORMS,
    SERVICE_REANALYZE_NOW,
    get_custom_detection_label,
    get_entry_value,
    make_entry_unique_id,
    make_legacy_entry_unique_id,
    CONF_DETECTION_PROFILE,
    CONF_OLLAMA_MODEL,
    CONF_STREAM_URL,
)
from .coordinator import SentryBoxCoordinator

LOGGER = logging.getLogger(__name__)
SentryBoxConfigEntry = ConfigEntry


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the SentryBox integration."""
    hass.data.setdefault(DOMAIN, {})

    if not hass.services.has_service(DOMAIN, SERVICE_REANALYZE_NOW):

        async def _handle_reanalyze(call: ServiceCall) -> None:
            entry_id = call.data.get(ATTR_ENTRY_ID)
            coordinators: dict[str, SentryBoxCoordinator] = hass.data.get(DOMAIN, {})

            if entry_id:
                coordinator = coordinators.get(entry_id)
                if coordinator is None:
                    LOGGER.warning("Service call referenced unknown entry_id %s", entry_id)
                    return
                hass.async_create_task(coordinator.async_request_refresh())
                return

            for coordinator in coordinators.values():
                hass.async_create_task(coordinator.async_request_refresh())

        hass.services.async_register(
            DOMAIN,
            SERVICE_REANALYZE_NOW,
            _handle_reanalyze,
            schema=vol.Schema({vol.Optional(ATTR_ENTRY_ID): cv.string}),
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: SentryBoxConfigEntry) -> bool:
    """Set up SentryBox from a config entry."""
    await _async_migrate_entry_unique_id(hass, entry)
    coordinator = SentryBoxCoordinator(hass, entry)
    entry.runtime_data = coordinator
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await _async_remove_legacy_entities(hass, entry)
    await coordinator.async_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SentryBoxConfigEntry) -> bool:
    """Unload a SentryBox config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_remove_legacy_entities(
    hass: HomeAssistant, entry: SentryBoxConfigEntry
) -> None:
    """Remove legacy entities after SentryBox entity migrations."""
    entity_registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if entity.domain == "image" and entity.unique_id.endswith("last_analysis_frame"):
            entity_registry.async_remove(entity.entity_id)
        if (
            entity.domain == "binary_sensor"
            and entity.unique_id.endswith("package_detected")
        ):
            entity_registry.async_remove(entity.entity_id)


async def _async_migrate_entry_unique_id(
    hass: HomeAssistant, entry: SentryBoxConfigEntry
) -> None:
    """Migrate legacy unique IDs to the profile-aware format."""
    profile_key = str(
        get_entry_value(entry.data, entry.options, CONF_DETECTION_PROFILE)
    )
    custom_label = get_custom_detection_label(entry.data, entry.options)
    new_unique_id = make_entry_unique_id(
        entry.data[CONF_STREAM_URL],
        entry.data[CONF_OLLAMA_MODEL],
        profile_key,
        custom_label,
    )
    if entry.unique_id == new_unique_id:
        return

    legacy_unique_id = make_legacy_entry_unique_id(
        entry.data[CONF_STREAM_URL],
        entry.data[CONF_OLLAMA_MODEL],
    )
    if entry.unique_id not in {None, legacy_unique_id}:
        return

    for other_entry in hass.config_entries.async_entries(DOMAIN):
        if other_entry.entry_id != entry.entry_id and other_entry.unique_id == new_unique_id:
            LOGGER.warning(
                "Skipping SentryBox unique_id migration for %s because %s already uses %s",
                entry.entry_id,
                other_entry.entry_id,
                new_unique_id,
            )
            return

    hass.config_entries.async_update_entry(entry, unique_id=new_unique_id)

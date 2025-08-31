"""The MiraMode BLE integration."""
from __future__ import annotations
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import MiraModeCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MiraMode BLE device from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    address = entry.unique_id
    client_id = entry.data.get("client_id")
    device_id = entry.data.get("device_id")

    if address is None or client_id is None or device_id is None:
        raise ConfigEntryNotReady("Missing required device identifiers")

    coordinator = MiraModeCoordinator(hass, address, client_id, device_id)

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

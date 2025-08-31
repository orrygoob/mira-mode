"""Support for Mira Mode BLE valves (bath + shower)."""
from __future__ import annotations

import logging

from homeassistant import config_entries
from homeassistant.components.valve import ValveEntity, ValveDeviceClass, ValveEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .coordinator import MiraModeCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MiraMode BLE bath and shower valves."""
    coordinator: MiraModeCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        MiraModeValve(coordinator, valve_type="shower"),
        MiraModeValve(coordinator, valve_type="bath"),
    ]
    async_add_entities(entities)


class MiraModeValve(CoordinatorEntity[MiraModeCoordinator], ValveEntity):
    """Valve entity for Mira Mode (shower or bath)."""

    _attr_device_class = ValveDeviceClass.WATER
    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
    _attr_has_entity_name = True

    def __init__(self, coordinator: MiraModeCoordinator, valve_type: str) -> None:
        """Initialize the valve entity."""
        super().__init__(coordinator)
        self._valve_type = valve_type
        device = coordinator.data
        name = f"{valve_type.capitalize()}"
        self._attr_name = name
        self._attr_unique_id = f"{device.address}_{valve_type}_valve"
        self._id = device.address

        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, device.address)},
            name=device.name,
            manufacturer="Mira Showers",
            model="Mira Mode",
        )

    @property
    def is_closed(self) -> str:
        data = self.coordinator.data
        _LOGGER.error(f"Valve state data: {data}")  # Debug log
        if data is None:
            return None  # unknown
        if self._valve_type == "shower":
            return not data.shower
        else:
            return not data.bath

    @property
    def is_open(self) -> str:
        data = self.coordinator.data
        _LOGGER.error(f"Valve state data: {data}")  # Debug log
        if data is None:
            return None  # unknown
        if self._valve_type == "shower":
            return data.shower
        else:
            return data.bath

    async def async_turn_on(self, **kwargs):
        await self._set_valve(True)

    async def async_turn_off(self, **kwargs):
        await self._set_valve(False)

    async def async_open_valve(self, **kwargs):
        await self._set_valve(True)

    async def async_close_valve(self, **kwargs):
        await self._set_valve(False)

    async def _set_valve(self, on: bool):
        if self._valve_type == "shower":
            await self.coordinator._async_set_shower(on)
        else:
            await self.coordinator._async_set_bath(on)

    @property
    def reports_position(self) -> bool:
        return False

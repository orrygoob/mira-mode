"""Support for miramode ble sensors."""
from __future__ import annotations

import logging
import dataclasses

from .miramode import MiraModeState

from homeassistant import config_entries
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .coordinator import MiraModeCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MiraMode BLE sensors."""

    coordinator: MiraModeCoordinator = hass.data[DOMAIN][entry.entry_id]
    

    entities = [MiraModeTemperatureSensor(coordinator)]
    async_add_entities(entities)


class MiraModeTemperatureSensor(CoordinatorEntity[MiraModeCoordinator], SensorEntity):
    """MiraMode BLE sensors for the device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator
    ) -> None:
        """Populate the miramode entity with relevant data."""
        super().__init__(coordinator)

        device = coordinator.data
        name = f"{device.name}"

        self._attr_unique_id = f"{name}_temperature"
        self.entity_description = SensorEntityDescription(
            key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            name="Temperature",
        )

        self._id = device.address
        self._attr_device_info = DeviceInfo(
            connections={
                (
                    CONNECTION_BLUETOOTH,
                    device.address,
                )
            },
            name=name,
            manufacturer="Mira Showers",
            model="Mira Mode"
        )

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        try:
            return self.coordinator.data.temperature
        except KeyError:
            return None

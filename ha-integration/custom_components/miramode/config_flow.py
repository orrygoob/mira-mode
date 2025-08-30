"""Config flow for MiraMode BlE integration."""

from __future__ import annotations

import dataclasses
import logging
from typing import Any

from .miramode import MiraModeBluetoothDeviceData, MiraModeDevice
from bleak import BleakError
import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothServiceInfo,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class Discovery:
    """A discovered bluetooth device."""

    name: str
    discovery_info: BluetoothServiceInfo
    device: MiraModeDevice


def get_name(device: MiraModeDevice) -> str:
    """Generate name with identifier for device."""
    return f"{device.name}"         


class MiraModeDeviceUpdateError(Exception):
    """Custom error class for device updates."""


class MiraModeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MiraMode BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_device: Discovery | None = None
        self._discovered_devices: dict[str, Discovery] = {}
        self._pending_entry_title: str | None = None
        self._pending_entry_data: dict | None = None

    async def _get_device_data(
        self, discovery_info: BluetoothServiceInfo
    ) -> MiraModeDevice:
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, discovery_info.address
        )
        if ble_device is None:
            _LOGGER.debug("no ble_device in _get_device_data")
            raise MiraModeDeviceUpdateError("No ble_device")

        miramode = MiraModeBluetoothDeviceData(_LOGGER)

        try:
            data = await miramode.update_device(ble_device)
        except BleakError as err:
            _LOGGER.error(
                "Error connecting to and getting data from %s: %s",
                discovery_info.address,
                err,
            )
            raise MiraModeDeviceUpdateError("Failed getting device data") from err
        except Exception as err:
            _LOGGER.error(
                "Unknown error occurred from %s: %s", discovery_info.address, err
            )
            raise err
        return data

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        _LOGGER.debug("Discovered BT device: %s", discovery_info)
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        try:
            device = await self._get_device_data(discovery_info)
        except MiraModeDeviceUpdateError:
            return self.async_abort(reason="cannot_connect")
        except Exception:  # pylint: disable=broad-except
            return self.async_abort(reason="unknown")

        name = get_name(device)
        self.context["title_placeholders"] = {"name": name}
        self._discovered_device = Discovery(name, discovery_info, device)

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        if user_input is not None:
            self._pending_entry_title = self.context["title_placeholders"]["name"]
            self._pending_entry_data = {
                CONF_ADDRESS: self._discovered_device.discovery_info.address,
            }
            return await self.async_step_device_details()

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders=self.context["title_placeholders"],
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            discovery = self._discovered_devices[address]

            self._discovered_device = discovery
            self._pending_entry_title = discovery.name
            self._pending_entry_data = {CONF_ADDRESS: address}

            return await self.async_step_device_details()

        # Discover devices...
        current_addresses = self._async_current_ids()
        for discovery_info in async_discovered_service_info(self.hass):
            address = discovery_info.address
            if address in current_addresses or address in self._discovered_devices:
                continue
            if discovery_info.advertisement.local_name is None:
                continue
            if not discovery_info.advertisement.local_name.startswith("Mira"):
                continue

            try:
                device = await self._get_device_data(discovery_info)
            except MiraModeDeviceUpdateError:
                return self.async_abort(reason="cannot_connect")
            except Exception:
                return self.async_abort(reason="unknown")

            name = get_name(device)
            self._discovered_devices[address] = Discovery(name, discovery_info, device)

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        titles = {
            address: get_name(discovery.device)
            for (address, discovery) in self._discovered_devices.items()
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(titles)}),
        )

    async def async_step_device_details(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask user for device_id and client_id."""
        if user_input is not None:
            # Merge pending data with entered values
            data = {**self._pending_entry_data, **user_input}
            return self.async_create_entry(title=self._pending_entry_title, data=data)

        schema = vol.Schema(
            {
                vol.Required("device_id"): int,
                vol.Required("client_id"): int,
            }
        )
        return self.async_show_form(step_id="device_details", data_schema=schema)

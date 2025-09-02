"""Parser for MiraMode BLE devices"""

from __future__ import annotations

import asyncio
import dataclasses
import struct
from collections import namedtuple
from datetime import datetime
import logging

# from logging import Logger
from math import exp
from typing import Any, Callable, Tuple, TypeVar, cast

from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection

from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.components import bluetooth

WrapFuncType = TypeVar("WrapFuncType", bound=Callable[..., Any])

class BleakCharacteristicMissing(BleakError):
    """Raised when a characteristic is missing from a service."""


class BleakServiceMissing(BleakError):
    """Raised when a service is missing."""

    
class BleakNoResponse(BleakError):
    """Raised when an incorrect device id has been input and no response was heard."""

    
class BleakIncompatibleProduct(BleakError):
    """Raised when packets of the wrong length are being received."""

MIRA_CHARACTERISTIC_UUID_READ = "bccb0003-ca66-11e5-88a4-0002a5d5c51b"
MIRA_CHARACTERISTIC_UUID_WRITE = "bccb0002-ca66-11e5-88a4-0002a5d5c51b"

# Format - device_id + uuid_command + temperature + shower + bath = 01|87050101|e0|64|00 for shower
MIRA_COMMAND = "87050101"
# Format - device_id + uuid_trigger_notif = 01|0700458A send to UUID_WRITE to trigger a notif on UUID_READ
MIRA_TRIGGER_NOTIF = "0700458A"

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class MiraModeState:
    """Response data with information about the MiraMode device"""

    name: str = ""
    address: str = ""
    device_id: int = -1
    client_id: int = -1
    temperature: float = 0.0
    shower: bool = False
    bath: bool = False

# pylint: disable=too-many-locals
# pylint: disable=too-many-branches
class MiraModeBluetoothAPI:

    _event: asyncio.Event | None
    _command_data: bytearray | None

    def __init__(
        self,
        logger: Logger,
        hass,
        address: str,
        client_id: int = 0, # only need to be set for control commands
        device_id: int = 0, # leave as optional for config flow so we can check connection to device before IDs are set
    ):
        super().__init__()
        self.logger = logger
        self.hass = hass
        
        self._command_data = None
        self._event = None
        self._lock = asyncio.Lock()  # <-- ensure sequential execution

        self.state = MiraModeState()
        self.state.address = address
        self.state.client_id = client_id
        self.state.device_id = device_id
        
        ble_device = bluetooth.async_ble_device_from_address(self.hass, self.state.address)

        if not ble_device:
            raise UpdateFailed(f"Could not find MiraMode device at {self.state.address}")
        
        if ble_device.name.startswith("Mira N86Sd: "):
            self.state.name = ble_device.name.split(": ", 1)[1]
        else:
            self.state.name = ble_device.name


    def notification_handler(self, _: Any, data: bytearray) -> None:
        """Helper for command events"""
        self._command_data = data

        if self._event is None:
            return
        self._event.set()

    def disconnect_on_missing_services(func: WrapFuncType) -> WrapFuncType:
        """Define a wrapper to disconnect on missing services and characteristics.

        This must be placed after the retry_bluetooth_connection_error
        decorator.
        """

        async def _async_disconnect_on_missing_services_wrap(
            self, *args: Any, **kwargs: Any
        ) -> None:
            try:
                return await func(self, *args, **kwargs)
            except (BleakServiceMissing, BleakCharacteristicMissing) as ex:
                logger.warning(
                    "%s: Missing service or characteristic, disconnecting to force refetch of GATT services: %s",
                    self.name,
                    ex,
                )
                if self.client:
                    await self.client.clear_cache()
                    await self.client.disconnect()
                raise

        return cast(WrapFuncType, _async_disconnect_on_missing_services_wrap)

    def _get_device(self) -> BLEDevice:
        ble_device = bluetooth.async_ble_device_from_address(self.hass, self.state.address)

        if not ble_device:
            raise UpdateFailed(f"Could not find MiraMode device at {self.state.address}")
        
        return ble_device

    @disconnect_on_missing_services
    async def _get_state(self, client: BleakClient):
        self._event = asyncio.Event()
        try:
            await client.start_notify(
                MIRA_CHARACTERISTIC_UUID_READ, self.notification_handler
            )
        except:
            self.logger.warn("_get_state Bleak error 1")

        await client.write_gatt_char(MIRA_CHARACTERISTIC_UUID_WRITE, bytes([self.state.device_id]) + bytes.fromhex(MIRA_TRIGGER_NOTIF))

        # Wait for up to 5 seconds to see if a
        # callback comes in.
        try:
            await asyncio.wait_for(self._event.wait(), 5)
        except asyncio.TimeoutError:
            self.logger.warn("Timeout getting command data.")
        except:
            self.logger.warn("_get_state Bleak error 2")

        await client.stop_notify(MIRA_CHARACTERISTIC_UUID_READ)

        if self._command_data is None:
            self.logger.warn("Command data is None")
            raise BleakNoResponse("No response from device - is the Device ID correct?")
        elif len(self._command_data) != 13 and len(self._command_data) != 14:
            self.logger.warn("Unexpected data length %d", len(self._command_data))
            raise BleakIncompatibleProduct("Packets of the wrong length are being received - is this a MiraMode device?")
        else:
            # Missing first byte but still contains data so pad to length
            if len(self._command_data) == 13:
                b = bytearray(b'\x00')
                self._command_data[0:0] = b
            
            self.state.temperature = round((self._command_data[6] + 268) / 10.4, 2)
            self.state.shower = self._command_data[9] == 0x64
            self.state.bath = self._command_data[10] == 0x64
            self.logger.debug("Temperature: %s, Shower: %s, Bath: %s", self.state.temperature, self.state.shower, self.state.bath)
            
        self._command_data = None
    
    @disconnect_on_missing_services
    async def _push_state(self, client: BleakClient):
        # Extract from sensors dict
        temperature = int(max(0, min(255, round(self.state.temperature * 10.4 - 268))))
        shower = 0x64 if self.state.shower else 0
        bath = 0x64 if self.state.bath else 0
        
        # Create payload
        payload = bytes([self.state.device_id]) + bytes.fromhex(MIRA_COMMAND) + bytes([temperature, shower, bath])

        # Calculate CRC
        data = payload + struct.pack(">I", self.state.client_id)

        i = 0
        i2 = 0xFFFF
        while i < len(data):
            b = data[i]
            i3 = i2
            for i2 in range(8):
                i4 = 1
                i5 = 1 if ((b >> (7 - i2)) & 1) == 1 else 0
                if ((i3 >> 15) & 1) != 1:
                    i4 = 0
                i3 = i3 << 1
                if (i5 ^ i4) != 0:
                    i3 = i3 ^ 0x1021
            i += 1
            i2 = i3
        crc = i2 & 0xFFFF

        payload = payload + struct.pack(">H", crc)

        await client.write_gatt_char(MIRA_CHARACTERISTIC_UUID_WRITE, payload)

    async def update_state(self) -> MiraModeState:
        """Connects to the device through BLE and retrieves relevant data"""
        async with self._lock:  # <-- lock here
            ble_device = self._get_device()
            client = await establish_connection(BleakClient, ble_device, ble_device.address)

            await self._get_state(client)

            await client.disconnect()

            return self.state

    async def push_state(self) -> MiraModeState:
        """Connects to the device through BLE and sends relevant data"""
        async with self._lock:  # <-- lock here
            ble_device = self._get_device()
            client = await establish_connection(BleakClient, ble_device, ble_device.address)

            await self._push_state(client)

            await client.disconnect()

            return self.state

    async def set_temperature(self, temperature: float) -> MiraModeState:
        """Connects to the device through BLE and sets the temperature"""
        async with self._lock:  # <-- lock here
            ble_device = self._get_device()
            client = await establish_connection(BleakClient, ble_device, ble_device.address)

            await self._get_state(client)

            self.state.temperature = temperature

            await self._push_state(client)

            await self._get_state(client)

            await client.disconnect()

            return self.state

    async def set_shower(self, shower: bool) -> MiraModeState:
        """Connects to the device through BLE and sets shower mode"""
        async with self._lock:  # <-- lock here
            ble_device = self._get_device()
            client = await establish_connection(BleakClient, ble_device, ble_device.address)

            await self._get_state(client)

            self.state.shower = shower

            await self._push_state(client)

            await self._get_state(client)

            await client.disconnect()

            return self.state

    async def set_bath(self, bath: bool) -> MiraModeState:
        """Connects to the device through BLE and sets bath mode"""
        async with self._lock:  # <-- lock here
            ble_device = self._get_device()
            client = await establish_connection(BleakClient, ble_device, ble_device.address)

            await self._get_state(client)

            self.state.bath = bath

            await self._push_state(client)

            await self._get_state(client)

            await client.disconnect()

            return self.state

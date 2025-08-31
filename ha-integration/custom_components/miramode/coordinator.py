import logging
from datetime import timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.components import bluetooth
from bleak_retry_connector import close_stale_connections_by_address

from .miramode import MiraModeBluetoothAPI, MiraModeDevice
from .const import DOMAIN, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class MiraModeCoordinator(DataUpdateCoordinator[MiraModeDevice]):
    """DataUpdateCoordinator for Mira Mode device."""

    def __init__(self, hass, address: str, client_id: str, device_id: str) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.address = address
        self.client_id = client_id
        self.device_id = device_id
        self._client = MiraModeBluetoothAPI(_LOGGER, client_id, device_id)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    @property
    def client(self) -> MiraModeBluetoothAPI:
        """Expose the underlying client for sending commands."""
        return self._client

    async def _async_update_data(self) -> MiraModeDevice:
        """Fetch latest data from Mira Mode device."""
        await close_stale_connections_by_address(self.address)
        ble_device = bluetooth.async_ble_device_from_address(self.hass, self.address)

        if not ble_device:
            raise UpdateFailed(f"Could not find MiraMode device at {self.address}")

        try:
            return await self._client.update_device(ble_device)
        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err

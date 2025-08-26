import asyncio
from bleak import BleakClient, BleakScanner
import struct

# This is the MAC address of the shower
# mac_address = "FD:93:5A:A8:EC:93"
mac_address = "3A2ECD87-2E4C-2585-E078-5BB0559B74DD" # UUID of shower on Apple devices (rather than using MAC address)

# See below for how to obtain the device_id and client_id
device_id = 2
client_id = 32683

UUID_MODEL_NUMBER = "00002a24-0000-1000-8000-00805f9b34fb"
UUID_SERIAL_NUMBER = "00002a25-0000-1000-8000-00805f9b34fb"
UUID_FIRMWARE = "00002a26-0000-1000-8000-00805f9b34fb"
UUID_HARDWARE_REVISION = "00002a27-0000-1000-8000-00805f9b34fb"
UUID_MANUFACTURER = "00002a29-0000-1000-8000-00805f9b34fb"

UUID_READ = "bccb0003-ca66-11e5-88a4-0002a5d5c51b"
UUID_WRITE = "bccb0002-ca66-11e5-88a4-0002a5d5c51b"

# Format - device_id + uuid_command + temperature + shower + bath = 01|87050101|e0|64|00 for shower
UUID_COMMAND = "87050101"
# Format - device_id + uuid_trigger_notif = 01|0700458A send to UUID_WRITE to trigger a notif on UUID_READ
UUID_TRIGGER_NOTIF = "0700458A"

def _convert_temperature(celsius):
    return int(max(0, min(255, round(celsius * 10.4 - 268))))

def _convert_temperature_reverse(mira_temp):
    return round((mira_temp + 268) / 10.4, 2)

async def discover():
    """Discover Bluetooth LE devices."""
    devices = await BleakScanner.discover()
    print("Discovered devices: %s", [{"address": device.address, "name": device.name} for device in devices])

    matching = [device for device in devices if device.name != None and device.name[0:4] == "Mira"]
    print("Matching devices: %s", [{"address": device.address, "name": device.name} for device in matching])

    return matching

class MiraInstance:
    def __init__(self, mac: str, device_id: int, client_id: int) -> None:
        self._mac = mac
        self._device_id = device_id
        self._client_id = client_id

        self._shower = None
        self._bath = None
        self._temperature = 35

        self._connected = None

        # future used for notify callback
        self._notification_future = None

        self._device = BleakClient(self._mac)

    # Use CRC-16-CCITT to validate payload, using the sniffed client id
    def _encode_crc(self, payload):
        data = payload + struct.pack(">I", self._client_id)

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

        return payload + struct.pack(">H", crc)

    async def _send(self, data: bytearray):
        print('data to send: ', ''.join(format(x, ' 03x') for x in data))
        
        if (not self._connected):
            await self.connect()
        
        payload = self._encode_crc(data)

        print('payload with crc: ', ''.join(format(x, ' 03x') for x in payload))
        await self._device.write_gatt_char(UUID_WRITE, payload)

    def _notification_handler(self, sender, data):
        if self._notification_future and not self._notification_future.done():
            self._notification_future.set_result(data)

    async def _poll_state(self):
        if (not self._connected):
            await self.connect()

        # Create a new future for this notification
        self._notification_future = asyncio.get_event_loop().create_future()

        await self._device.start_notify(UUID_READ, self._notification_handler)

        # Write data to trigger a notification
        await self._device.write_gatt_char(UUID_WRITE, bytes([device_id]) + bytes.fromhex(UUID_TRIGGER_NOTIF))

        # Wait for notification (this will block until notification_handler is called)
        data = await self._notification_future

        await self._device.stop_notify(UUID_READ)

        print('polled data: ', ''.join(format(x, ' 03x') for x in data))

        # -- extract data from binary --

        # Ignore as doesnt include information about outlet valves
        if len(data) == 19:
            return
        
        # Missing first byte but still contains data
        if len(data) == 13:
            b = bytearray(b'\x00')
            data[0:0] = b

        if len(data) != 14:
            raise Exception("Unexpected data length")

        self._temperature = _convert_temperature_reverse(data[6])
        self._shower = data[9] == 0x64
        self._bath = data[10] == 0x64

        print(self._shower, self._bath, self._temperature)
        return (self._shower, self._bath, self._temperature)

    async def _read(self, uuid):
        if (not self._connected):
            await self.connect()
        
        return await self._device.read_gatt_char(uuid)

    @property
    def mac(self):
        return self._mac

    @property
    def temperature(self):
        return self._temperature

    @property
    def shower(self):
        return self._shower

    @property
    def bath(self):
        return self._bath

    async def get_device_info(self):
        model_number = (await self._read(UUID_MODEL_NUMBER)).decode('UTF-8')
        serial_number = await self._read(UUID_SERIAL_NUMBER)
        firmware = await self._read(UUID_FIRMWARE)
        hardware_revision = await self._read(UUID_HARDWARE_REVISION)
        manufacturer = (await self._read(UUID_MANUFACTURER)).decode('UTF-8')

        print([model_number, serial_number, firmware, hardware_revision, manufacturer])

    async def set_temperature(self, temp):
        # set the temperature in degrees and push to shower
        self._temperature = temp
        await self.push_state()

    async def shower_off(self):
        self._shower = False
        await self.push_state()

    async def shower_on(self):
        self._shower = True
        await self.push_state()

    async def bath_off(self):
        self._bath = False
        await self.push_state()

    async def bath_on(self):
        self._bath = True
        await self.push_state()

    async def push_state(self):
        # construct and send message to set temperateu and outlet states as determined by class
        temperature = _convert_temperature(self.temperature)
        shower = 0x64 if self._shower else 0
        bath = 0x64 if self._bath else 0
        await self._send(bytes([device_id]) + bytes.fromhex(UUID_COMMAND) + bytes([temperature, shower, bath]))

        await self.update_state()

    async def update_state(self):
        await self._poll_state()

    async def connect(self):
        await self._device.connect(timeout=20)
        await asyncio.sleep(1)
        self._connected = True

        # get current state of connected shower
        await self.update_state()

    async def disconnect(self):
        if self._device.is_connected:
            await self._device.disconnect()


async def main():
    shower = MiraInstance(mac_address, device_id, client_id)

    print("connecting")
    await shower.connect()
    print("connected")
    print("shower:", shower.shower, "bath:", shower.bath, "temp:", shower.temperature)

    await shower.shower_on()
    await shower.set_temperature(100)

    await asyncio.sleep(10)

    await shower.set_temperature(0)

    await asyncio.sleep(20)
    await shower.shower_off()
    
    await shower.update_state()
    print("shower:", shower.shower, "bath:", shower.bath, "temp:", shower.temperature)

# Call this function to discover the address of your device
# await discover()

# Run example program
asyncio.run(main())
# Mira Mode Shower Home Assistant Integration

Mira Mode is a line of digital showers and bathfills from Mira Showers. They
work great in my experience, but having only a Bluetooth Low Energy (BLE)
interface, they can only be controlled locally via smartphone and not via
Alexa, Google Home and the likes, which makes the whole experience
significantly less useful.

This repo contains scripts to connect to and control these devices as well as a
custom integration for home assistant so that they can be directly integrated 
into smart home automation systems. Both of these implementations use the `bleak` 
library to interface with the showers over BLE.

To operate thse implementations require the following:
- Shower MAC address - the unique bluetooth identifier for connecting to the device, code for scanning nearby devices to find the shower is included
- device id - unique number specific to the shower, all communication with the shower requires this
- client id - unique number specific to the paired phone, used to generate a CRC checksum that verifies all commands that modify shower settings

## How to obtain the device and client ids

At the moment the way in which those ids are obtained is by using a BLE
sniffer, like the *Bluefruit LE Sniffer* from Adafruit, to get packets
exchanged between your phone Mira Mode app and the Mira Shower when an
outlet is turned on, using e.g. Wireshark. This complication can be
avoided by finding out how the device pairing protocol works,
something on the TODO list.

What we are looking for are binary payloads written to the BLE
characterist 0x11 which look for example like this:

*XX:87:05:01:01:90:64:00:YY:YY*

XX is your device id and YYYY is a CRC code obtained from the rest of
the payload plus the client id. Being the client id a 16 bit adapter,
it can be quickly computed with a brute force loop.

## Brute Force Loop
Using crc16_loop.py - at the top of the python script are 2 byte arrays, you need to copy your value into these. data excludes the CRC and payl is the entire value.

Split the value into hex pairs so they look the same as below.

data = bytearray([
        0x01,
        0x87, 0x05,
        0x03,
        0x01,
        0x9a,
        0x00,
        0x00])
payl = bytearray([
        0x01,
        0x87, 0x05,
        0x03,
        0x01,
        0x9a,
        0x00,
        0x00,
        0xd5,0x28])

## Acknowledgements

This work would not have been possible without the following work:
- https://github.com/alexpilotti/python-miramode - for the original reverse engineering of the protocol
- https://github.com/nhannam/shower-controller-documentation - documentation on the protocol (which I only discovered after writing this integration :/)
- https://github.com/jdeath/rd200v2 - used as a template BLE device integration that I could adapt and build upon

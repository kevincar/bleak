
"""
Example for a BLE 4.0 Server
"""

import logging
import asyncio

from typing import Any

from bleak.backends.characteristic import GattCharacteristicsFlags
from bleak import BleakServer, BleakGATTCharacteristic

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(name=__name__)

my_service_name = "ECoGLink"
my_service_uuid = "A07498CA-AD5B-474E-940D-16F1FBE7E8CD"


def read_request(
        characteristic: BleakGATTCharacteristic,
        **kwargs
        ) -> bytearray:
    logger.debug(f"DANG {characteristic.value}")
    return characteristic.value


def write_request(
        characteristic: BleakGATTCharacteristic,
        value: Any,
        **kwargs
        ):
    characteristic.set_value(value)
    logger.debug(f"Char value set to {characteristic.value}")


async def run(loop):
    server = BleakServer(name=my_service_name, loop=loop)
    await server.add_new_service(my_service_uuid)
    await server.add_new_characteristic(
            my_service_uuid,
            "51FF12BB-3ED8-46E5-B4F9-D64E2FEC021B",
            GattCharacteristicsFlags.read.value |
            GattCharacteristicsFlags.write.value |
            GattCharacteristicsFlags.indicate.value,
            None,
            0x1 | 0x2)


    server.read_request_func = read_request
    server.write_request_func = write_request

    await server.start()
    logger.debug("Advertising")
    logger.debug(f"Services: {server.services.services[my_service_uuid].get_characteristic('51FF12BB-3ED8-46E5-B4F9-D64E2FEC021B')}")
    await asyncio.sleep(20)
    logger.debug("Updating")
    server.updateValue(my_service_uuid, "51FF12BB-3ED8-46E5-B4F9-D64E2FEC021B")
    await asyncio.sleep(20)
    await server.stop()

loop = asyncio.get_event_loop()
loop.run_until_complete(run(loop))

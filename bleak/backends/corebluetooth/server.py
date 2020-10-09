"""
BleakServer for CoreBluetooth

Created on 2019-07-03 by kevincar <kevincarrolldavis@gmail.com>
"""

import logging

from typing import (
        Callable,
        Dict,
        Any,
        Optional
        )
from asyncio.exceptions import TimeoutError
from asyncio.events import AbstractEventLoop

from Foundation import CBUUID, CBMutableService, CBMutableCharacteristic

from bleak.exc import BleakError
from bleak.backends.server import BaseBleakServer
from bleak.backends.characteristic import GattCharacteristicsFlags
from bleak.backends.corebluetooth.service import (
        BleakGATTServiceCoreBluetooth,
        BleakGATTServiceCollectionCoreBluetooth
        )
from bleak.backends.corebluetooth.characteristic import (
        BleakGATTCharacteristicCoreBluetooth
        )

from .PeripheralManagerDelegate import (
        PeripheralManagerDelegate
        )

logger = logging.getLogger(name=__name__)


class BleakServerCoreBluetooth(BaseBleakServer):
    """CoreBluetooth Implementation of BleakServer"""

    def __init__(self, name: str, loop: AbstractEventLoop = None, **kwargs):
        super(BleakServerCoreBluetooth, self).__init__(loop=loop, **kwargs)

        self.name = name
        self.services: BleakGATTServiceCollectionCoreBluetooth = (
                BleakGATTServiceCollectionCoreBluetooth()
                )

        self.callbacks: Dict[str, Callable] = {}

        self.peripheral_manager_delegate: PeripheralManagerDelegate = (
                PeripheralManagerDelegate.alloc().init()
                )
        self.peripheral_manager_delegate.readRequestFunc = self.read_request
        self.peripheral_manager_delegate.writeRequestsFunc = self.write_request

    async def start(self):
        await self.peripheral_manager_delegate.wait_for_powered_on(10)

        for service_uuid in self.services.services:
            bleak_service = self.services.get_service(service_uuid)
            service_obj = bleak_service.obj
            print(f"Adding service: {bleak_service.uuid}")
            await self.peripheral_manager_delegate.addService_(service_obj)

        if not self.read_request_func or not self.write_request_func:
            raise BleakError("Callback functions must be initialized first")

        advertisement_data = {
            "kCBAdvDataServiceUUIDs": list(map(lambda x: x.obj.UUID(), self.services)),
            "kCBAdvDataLocalName": self.name
            }
        logger.debug("Advertisement Data: {}".format(advertisement_data))
        try:
            await self.peripheral_manager_delegate.startAdvertising_(advertisement_data)
        except TimeoutError:
            await self.start()

        logger.debug("Advertising...")

    async def stop(self):
        await self.peripheral_manager_delegate.stopAdvertising()

    def is_connected(self) -> bool:
        """
        Determine whether there are any connected peripheral devices
        """
        n_subscriptions = len(self.peripheral_manager_delegate._central_subscriptions)
        return n_subscriptions > 0

    def is_advertising(self) -> bool:
        """
        Determine whether the service is advertising
        """
        return self.peripheral_manager_delegate.is_advertising() == 1

    async def add_new_service(self, _uuid: str):
        """
        Add a service and all it's characteristics to be advertised
        """
        logger.debug("Creating a new service with uuid: {}".format(_uuid))

        service_uuid: CBUUID = CBUUID.alloc().initWithString_(_uuid)
        cb_service: CBMutableService = CBMutableService.alloc().initWithType_primary_(service_uuid, True)
        bleak_service: BleakGATTServiceCoreBluetooth = BleakGATTServiceCoreBluetooth(obj=cb_service)

        self.services.add_service(bleak_service)

    async def add_new_characteristic(self, service_uuid: str, char_uuid: str, properties: GattCharacteristicsFlags, value: bytearray, permissions: int):
        """
        Generate a new characteristic to be associated with the server
        """
        logger.debug("Craeting a new characteristic with uuid: {}".format(char_uuid))
        cb_uuid: CBUUID = CBUUID.alloc().initWithString_(char_uuid)
        cb_characteristic: CBMutableCharacteristic = CBMutableCharacteristic.alloc().initWithType_properties_value_permissions_(cb_uuid, properties, value, permissions)
        bleak_characteristic = BleakGATTCharacteristicCoreBluetooth(obj=cb_characteristic)
        self.services.get_service(service_uuid).add_characteristic(bleak_characteristic)

        self.services.add_characteristic(bleak_characteristic)

    def updateValue(self, service_uuid: str, char_uuid: str) -> bool:
        """
        Update the characteristic value. This is different than using
        characteristic.set_value. This send notifications to subscribed
        central devices.
        """
        characteristic: BleakGATTCharacteristicCoreBluetooth = (
                self.services.characteristics[char_uuid.lower()]
                )

        value: bytes = characteristic.value
        value = value if value is not None else b'\x00'
        result: bool = (
                self.peripheral_manager_delegate
                    .peripheral_manager
                    .updateValue_forCharacteristic_onSubscribedCentrals_(
                        value,
                        characteristic.obj,
                        None
                        )
                    )

        return result

    @property
    def read_request_func(self) -> Callable:
        """
        Return an instance of the function to handle incoming read requests
        """
        func: Optional[Callable[[Any], Any]] = self.callbacks.get('read')
        if func is not None:
            return func
        else:
            raise BleakError("Server: Read Callback is undefined")

    @read_request_func.setter
    def read_request_func(self, func: Callable):
        """
        Set the function to handle incoming read requests
        """
        self.callbacks['read'] = func

    @property
    def write_request_func(self) -> Callable:
        """
        Return an instance of the function to handle incoming write requests
        """
        func: Optional[Callable[[Any], Any]] = self.callbacks.get('write')
        if func is not None:
            return func
        else:
            raise BleakError("Server: Write Callback is undefined")

    @write_request_func.setter
    def write_request_func(self, func: Callable):
        """
        Set the function to handle incoming write requests
        """
        self.callbacks['write'] = func



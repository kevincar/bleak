"""
PeripheralManagerDelegate file. This class will function as the delegate
NSObject for the CBPeripheralManager object used by CoreBluetooth advertising
servers

Created on 2019-07-03 by kevincar <kevincarrolldavis@gmail.com>
"""

import objc
import logging
import asyncio

from typing import (
        Any,
        Dict,
        List,
        Optional,
        Callable
        )

from bleak.exc import BleakError
from bleak.backends.corebluetooth.error import CBATTError

from CoreBluetooth import (
        CBManagerStateUnknown,
        CBManagerStateResetting,
        CBManagerStateUnsupported,
        CBManagerStateUnauthorized,
        CBManagerStatePoweredOff,
        CBManagerStatePoweredOn
        )
from Foundation import (
        NSObject,
        CBPeripheralManager,
        CBCentral,
        CBMutableService,
        CBService,
        CBCharacteristic,
        CBATTRequest,
        NSError
        )

from libdispatch import dispatch_queue_create, DISPATCH_QUEUE_SERIAL


CBPeripheralManagerDelegate = objc.protocolNamed("CBPeripheralManagerDelegate")

logger = logging.getLogger(name=__name__)


class PeripheralManagerDelegate(NSObject):
    """
    This class will conform to the CBPeripheralManagerDelegate protocol to
    manage messages passed from the owning PeripheralManager class
    """
    ___pyobjc_protocols__ = [CBPeripheralManagerDelegate]

    def init(self):
        """macOS init function for NSObjects"""
        self = objc.super(PeripheralManagerDelegate, self).init()

        self.event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

        self.peripheral_manager: CBPeripheralManager = (
                CBPeripheralManager.alloc().initWithDelegate_queue_(
                    self,
                    dispatch_queue_create(
                        b"bleak.corebluetooth",
                        DISPATCH_QUEUE_SERIAL
                        )
                    )
                )

        self.callbacks: Dict[str, Callable] = {}

        self.powered_on_event = asyncio.Event()

        self._services_added_events = {}
        self._services_added_result = {}
        self.advertisement_started_event = asyncio.Event()

        self._central_subscriptions = {}

        if not self.compliant():
            logger.warning("PeripheralManagerDelegate is not compliant")

        return self

    # User defined functions

    def compliant(self):
        """
        Determines whether the class adheres to the CBPeripheralManagerDelegate
        protocol
        """
        return (
                PeripheralManagerDelegate
                .pyobjc_classMethods.conformsToProtocol_(
                    CBPeripheralManagerDelegate
                    )
                )

    @objc.python_method
    async def wait_for_powered_on(self, timeout: float):
        """
        Wait for ready state of the peripheralManager

        Parameters
        ----------
        timeout : float
            How long to wait for the powered on event
        """
        await asyncio.wait_for(self.powered_on_event.wait(), timeout)

    def is_connected(self) -> bool:
        """Determin whether any peripherals have subscribed"""

        n_subscriptions = len(self._central_subscriptions)
        return n_subscriptions > 0

    def is_advertising(self) -> bool:
        """Determin whether the server is advertising"""
        return self.peripheral_manager.isAdvertising()

    @objc.python_method
    async def addService_(self, service: CBMutableService) -> bool:
        """Add service to the peripheral"""
        UUID = service.UUID().UUIDString()
        self._services_added_events[UUID] = asyncio.Event()

        self.peripheral_manager.addService_(service)

        await self._services_added_events[UUID].wait()

        return self._services_added_result[UUID]

    async def startAdvertising_(self, advertisement_data: Dict[str, Any]):

        self.peripheral_manager.startAdvertising_(advertisement_data)

        await asyncio.wait_for(self.advertisement_started_event.wait(), 2)

        logger.debug(
            "Advertising started with the following data: {}"
            .format(advertisement_data)
                )

    async def stopAdvertising(self):

        self.peripheral_manager.stopAdvertising()
        await asyncio.sleep(0.01)

    @property
    def readRequstFunc(self) -> Callable:
        """
        Returns an instance to the function for handing read requests
        """
        func: Optional[Callable[[Any], Any]] = self.callbacks.get('read')
        if func is not None:
            return func
        else:
            raise BleakError("read request function undefined")

    @readRequstFunc.setter
    def readRequestFunc(self, func: Callable):
        """
        Sets the callback to handle read requests
        """
        self.callbacks['read'] = func

    @property
    def writeRequestFunc(self) -> Callable:
        """
        Returns an instance to the function for handling write requests
        """
        func: Optional[Callable[[Any], Any]] = self.callbacks.get('write')
        if func is not None:
            return func
        else:
            raise BleakError("write request func is undefined")

    @writeRequestFunc.setter
    def writeRequestFunc(self, func: Callable):
        """
        Sets the callback to handle write requests
        """
        self.callbacks['write'] = func

    # Protocol functions

    @objc.python_method
    def did_update_state(
            self,
            peripheralManager: CBPeripheralManager
            ):
        if peripheralManager.state() == CBManagerStateUnknown:
            logger.debug("Cannot detect bluetooth device")
        elif peripheralManager.state() == CBManagerStateResetting:
            logger.debug("Bluetooth is resetting")
        elif peripheralManager.state() == CBManagerStateUnsupported:
            logger.debug("Bluetooth is unsupported")
        elif peripheralManager.state() == CBManagerStateUnauthorized:
            logger.debug("Bluetooth is unauthorized")
        elif peripheralManager.state() == CBManagerStatePoweredOff:
            logger.debug("Bluetooth powered off")
        elif peripheralManager.state() == CBManagerStatePoweredOn:
            logger.debug("Bluetooth powered on")

        if peripheralManager.state() == CBManagerStatePoweredOn:
            self.powered_on_event.set()
        else:
            self.powered_on_event.clear()
            self.advertisement_started_event.clear()

    def peripheralManagerDidUpdateState_(
            self,
            peripheralManager: CBPeripheralManager
            ):
        self.event_loop.call_soon_threadsafe(
                self.did_update_state,
                peripheralManager
                )

    def peripheralManager_willRestoreState_(
            self, peripheral: CBPeripheralManager, d: dict
            ):
        logger.debug("PeripheralManager restoring state: {}".format(d))

    @objc.python_method
    def peripheralManager_didAddService_error(
            self,
            peripheralManager: CBPeripheralManager,
            service: CBService,
            error: NSError
            ):
        UUID = service.UUID().UUIDString()
        if error:
            self._services_added_result[UUID] = False
            raise BleakError("Failed to add service {}: {}"
                             .format(UUID, error))

        logger.debug("Peripheral manager did add service: {}".format(UUID))
        logger.debug(
                "service added had characteristics: {}"
                .format(service.characteristics())
                )
        self._services_added_result[UUID] = True
        self._services_added_events[UUID].set()

    def peripheralManager_didAddService_error_(
            self,
            peripheralManager: CBPeripheralManager,
            service: CBService,
            error: NSError
            ):
        self.event_loop.call_soon_threadsafe(
                self.peripheralManager_didAddService_error,
                peripheralManager,
                service,
                error
                )

    @objc.python_method
    def peripheralManagerDidStartAdvertising_error(
            self,
            peripheral: CBPeripheralManager,
            error: NSError
            ):
        if error:
            raise BleakError("Failed to start advertising: {}".format(error))

        logger.debug("Peripheral manager did start advertising")
        self.advertisement_started_event.set()

    def peripheralManagerDidStartAdvertising_error_(
            self,
            peripheral: CBPeripheralManager,
            error: NSError
            ):
        self.event_loop.call_soon_threadsafe(
                self.peripheralManagerDidStartAdvertising_error,
                peripheral,
                error
                )

    def peripheralManager_central_didSubscribeToCharacteristic_(
            self,
            peripheral: CBPeripheralManager,
            central: CBCentral,
            characteristic: CBCharacteristic
            ):
        central_uuid = central.identifier().UUIDString()
        char_uuid = characteristic.UUID().UUIDString()
        logger.debug(
                "Central Device: {} is subscribing to characteristic {}"
                .format(central_uuid, char_uuid)
                )
        if central_uuid in self._central_subscriptions:
            subscriptions = self._central_subscriptions[central_uuid]
            if char_uuid not in subscriptions:
                self._central_subscriptions[central_uuid].append(char_uuid)
            else:
                logger.debug(
                        (
                            "Central Device {} is already " +
                            "subscribed to characteristic {}"
                            )
                        .format(central_uuid, char_uuid)
                        )
        else:
            self._central_subscriptions[central_uuid] = [char_uuid]

    def peripheralManager_central_didUnsubscribeFromCharacteristic_(
            self,
            peripheral: CBPeripheralManager,
            central: CBCentral,
            characteristic: CBCharacteristic
            ):
        central_uuid = central.identifier().UUIDString()
        char_uuid = characteristic.UUID().UUIDString()
        logger.debug(
                "Central device {} is unsubscribing from characteristic {}"
                .format(central_uuid, char_uuid)
                )
        self._central_subscriptions[central_uuid].remove(char_uuid)

    def peripheralManagerIsReadyToUpdateSubscribers_(
            self,
            peripheral: CBPeripheralManager
            ):
        logger.debug("Peripheral is ready to update subscribers")

    def peripheralManager_didReceiveReadRequest_(
            self,
            peripheral: CBPeripheralManager,
            request: CBATTRequest
            ):
        # This should probably be a callback to be handled by the user, to be
        # implemented or given to the BleakServer
        logger.debug(
                "Received read request from {} for characteristic {}"
                .format(
                    request.central().identifier().UUIDString(),
                    request.characteristic().UUID().UUIDString()
                    )
                )
        request.setValue_(
                self.readRequestFunc(
                    request.characteristic().UUID().UUIDString()
                    )
                )
        peripheral.respondToRequest_withResult_(
                request,
                CBATTError.Success.value
                )

    def peripheralManager_didReceiveWriteRequests_(
            self,
            peripheral: CBPeripheralManager,
            requests: List[CBATTRequest]
            ):
        # Again, this should likely be moved to a callback
        logger.debug("Receving write requests...")
        for request in requests:
            central = request.central()
            char = request.characteristic()
            value = request.value()
            logger.debug(
                    "Write request from {} to {} with value {}"
                    .format(
                        central.identifier().UUIDString(),
                        char.UUID().UUIDString(), value
                        )
                    )
            self.writeRequestsFunc(char.UUID().UUIDString(), value)

        peripheral.respondToRequest_withResult_(
                requests[0],
                CBATTError.Success.value
                )

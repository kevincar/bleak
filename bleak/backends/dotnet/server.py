"""
BleakServer for DotNet

Created on Mon Jul  8 11:16:27 2019 @author: by Charliealver <charliealver@gmail.com>

"""

import logging
import asyncio
from threading import Thread, Lock, Condition

from asyncio.events import AbstractEventLoop
from typing import Union

from bleak.backends.dotnet.utils import wrap_IAsyncOperation
from bleak.backends.dotnet.service import (
        BleakGATTServiceDotNet,
        BleakGATTServiceCollectionDotNet
        )
from bleak.backends.dotnet.characteristic import BleakGATTCharacteristicDotNet
from bleak.backends.server import BaseBleakServer
from bleak.backends.characteristic import GattCharacteristicsFlags

# CLR imports
# Import of Bleak CLR->UWP Bridge.
# from BleakBridge import Bridge

# Import of other CLR components needed.
from Windows.Foundation import IAsyncOperation
from Windows.Storage.Streams import DataReader, DataWriter

from Windows.Devices.Bluetooth.GenericAttributeProfile import (
    GattWriteOption,
    GattServiceProviderResult,
    GattServiceProvider,
    GattLocalCharacteristicResult,
    GattLocalCharacteristic,
    GattLocalCharacteristicParameters,
    GattServiceProviderAdvertisingParameters,
    # GattServiceProviderAdvertisementStatus,
    GattReadRequestedEventArgs,
    GattReadRequest,
    GattWriteRequestedEventArgs,
    GattWriteRequest
)

from System import Guid

logger = logging.getLogger(__name__)


class Request():
    def __init__(self):
        self._lock = Lock()
        self._cv = Condition(self._lock)
        self._obj = None


class BleakServerDotNet(BaseBleakServer):
    """CoreBluetooth Implementation of BleakServer"""

    def __init__(self, name: str, loop: AbstractEventLoop = None, **kwargs):
        super(BleakServerDotNet, self).__init__(loop=loop, **kwargs)

        self.name = name
        self.services = BleakGATTServiceCollectionDotNet()
        self.service_provider = None

    async def start(self, **kwargs) -> bool:
        """
        Start the server

        Returns:
            Boolean - Whether server started successfully
        """

        advParameters = GattServiceProviderAdvertisingParameters()
        advParameters.IsDiscoverable = True
        advParameters.IsConnectable = True
        self.service_provider.StartAdvertising(advParameters)

    async def stop(self) -> bool:
        """
        Stop the server

        Returns:
            Boolean - Whether the server stopped successfully
        """
        self.service_provider.StopAdvertising()

    def is_connected(self) -> bool:
        """
        Determine whether there are any connected peripheral devices
        """
        pass

    def is_advertising(self) -> bool:
        """
        Determine whether the server is advertising
        """
        return self.service_provider.AdvertisementStatus == 2

    async def add_new_service(self, _uuid: str):
        """
        Generate a new service to be associated with the server
        """
        guid = Guid.Parse(_uuid)
        loop = asyncio.get_event_loop()
        spr = await wrap_IAsyncOperation(
                IAsyncOperation[GattServiceProviderResult](
                        GattServiceProvider.CreateAsync(guid)
                    ),
                return_type=GattServiceProviderResult,
                loop=loop)
        self.service_provider = spr.ServiceProvider
        newService = self.service_provider.Service
        bleak_service = BleakGATTServiceDotNet(obj=newService)
        logger.debug("Adding service to server with uuid {}".format(_uuid))
        self.services.add_service(bleak_service)

    async def add_new_characteristic(self, service_uuid: str, char_uuid: str,
                                     properties: GattCharacteristicsFlags,
                                     value: bytearray,
                                     permissions: int):
        """
        Generate a new characteristic to be associated with the server
        """
        charguid = Guid.Parse(char_uuid)
        serverguid = Guid.Parse(service_uuid)

        ReadParameters = GattLocalCharacteristicParameters()
        ReadParameters.CharacteristicProperties = properties
        ReadParameters.ReadProtectionLevel = permissions

        loop = asyncio.get_event_loop()
        characteristicResult = await wrap_IAsyncOperation(
                IAsyncOperation[GattLocalCharacteristicResult](
                        self.services.get_service(str(serverguid))
                        .obj.CreateCharacteristicAsync(
                            charguid, ReadParameters)
                    ),
                return_type=GattLocalCharacteristicResult,
                loop=loop)
        newChar = characteristicResult.Characteristic
        newChar.ReadRequested += self._read_characteristic
        newChar.WriteRequested += self._write_characteristic
        bleak_characteristic = BleakGATTCharacteristicDotNet(obj=newChar)
        self.services.get_service(str(serverguid)).add_characteristic(
                bleak_characteristic)

        self.services.add_characteristic(bleak_characteristic)

    # @staticmethod
    def _read_characteristic(self,
                             sender: GattLocalCharacteristic,
                             args: GattReadRequestedEventArgs):
        """
        This method, and the _write_characteristic method, both utilize the _get_request method.
        The _get_request method, utilizes native thread modeling. The reason for this is that
        the methods used to obtain the GattCharacteristics require the use of coroutines. 
        But the service requires functions. We cannot give back coroutines, else these functions
        will never run. Thus, we start up a thread to temporarily get or set the characteristic
        in question.
        """

        logger.debug("Reading Characteristic")
        deferral = args.GetDeferral()
        writer = DataWriter()
        # value = self.services.get_characteristic(str(sender.Uuid)).value
        value = self.read_request(str(sender.Uuid))
        value = value if value is not None else b'\x00'
        logger.debug(f"Current Characteristic value {value}")
        writer.WriteBytes(value)
        logger.debug("Getting request object {}".format(self))
        request = self._get_request(args)
        logger.debug("Got request object {}".format(request))
        request.RespondWithValue(writer.DetachBuffer())
        deferral.Complete()

    # @staticmethod
    def _write_characteristic(self,
                              sender: GattLocalCharacteristic,
                              args: GattWriteRequestedEventArgs):

        deferral = args.GetDeferral()
        request = self._get_request(args)
        logger.debug("Request value: {}".format(request.Value))
        reader = DataReader.FromBuffer(request.Value)
        logger.debug("Reader")
        n_bytes = reader.UnconsumedBufferLength
        logger.debug("n_bytes = {}".format(n_bytes))
        value = bytearray()
        for n in range(0, n_bytes):
            next_byte = reader.ReadByte()
            value.append(next_byte)
        logger.debug("Written Value: {}".format(value))
        logger.debug("senderuuid : {}".format(
            self.services.get_characteristic(str(sender.Uuid)).value))
        # self.services.get_characteristic(str(sender.Uuid)).value = value
        self.write_request(str(sender.Uuid), value)
        if request.Option == GattWriteOption.WriteWithResponse:
            request.Respond()

        logger.debug("Write Complete")
        deferral.Complete()


    def _get_request(self,
                     args: Union[
                         GattReadRequestedEventArgs,
                         GattWriteRequestedEventArgs
                         ]):

        request = Request()
        logger.debug("Attempting to obtain request: {}".format(request._obj))

        logger.debug("Starting Thread")
        fun_thread = Thread(
                target=self._run_request_thread, args=[args, request])
        fun_thread.start()

        logger.debug("Waiting for thread to stop")
        request._cv.acquire()
        while request._obj is None:
            request._cv.wait()

        request._cv.release()
        logger.debug("Waiting for thread to join")
        fun_thread.join()
        logger.debug("Thread finished. Request result: {}".format(
            request._obj))
        return request._obj

    def _run_request_thread(self,
                            args: Union[
                                        GattReadRequestedEventArgs,
                                        GattWriteRequestedEventArgs
                                        ],
                            request: Request):
        logger.debug("THREAD: Starting threaded event loop")
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self._request_thread_loop(args, request))
        logger.debug("THREAD: Completed request loop")

    async def _request_thread_loop(self,
                                   args: Union[
                                       GattReadRequestedEventArgs,
                                       GattWriteRequestedEventArgs],
                                   request: Request):

        logger.debug("THREAD: Attempting to acquire the request variable")
        request._cv.acquire()

        loop = asyncio.get_event_loop()
        if isinstance(args, GattReadRequestedEventArgs):
            request._obj = await wrap_IAsyncOperation(
                        IAsyncOperation[GattReadRequest](
                            args.GetRequestAsync()),
                        return_type=GattReadRequest,
                        loop=loop)
        elif isinstance(args, GattWriteRequestedEventArgs):
            request._obj = await wrap_IAsyncOperation(
                        IAsyncOperation[GattWriteRequest](
                            args.GetRequestAsync()),
                        return_type=GattWriteRequest,
                        loop=loop)

        logger.debug("THREAD: Obtained request: {}".format(request._obj))
        request._cv.notify()
        request._cv.release()

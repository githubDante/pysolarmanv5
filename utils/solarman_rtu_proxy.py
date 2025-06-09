"""Modbus RTU over TCP to Solarman proxy

Can be used with Home Assistant's native Modbus integration using config below:

- name: "solarman-modbus-proxy"
  type: rtuovertcp
  host: 192.168.1.20
  port: 1502
  delay: 3
  retry_on_empty: true
  sensors:
    [...]

"""

import argparse
import asyncio
from functools import partial
from typing import Optional

from pysolarmanv5 import PySolarmanV5Async
from threading import Lock

__solarman__: Optional[PySolarmanV5Async] = None
__slock__: Lock = Lock()
__connected__ = False


def _solarman_init(address: str, serial: int):
    global __solarman__
    if __solarman__ is None:
        __solarman__ = PySolarmanV5Async(address, serial, verbose=True, auto_reconnect=True, socket_timeout=3)

async def _solarman_disconnect():
    global __solarman__
    global __connected__
    if __connected__:
        __connected__ = False
        await __solarman__.disconnect()

async def _solarman_connect():
    global __solarman__
    global __connected__
    if not __connected__ or __solarman__.reader_task is None:
        if __solarman__.reader_task is None and __connected__:
            print("Not connected to a logger! Forced reconnect...")
        try:
            await __solarman__.connect()
            __connected__ = True
        except Exception as e:
            print(f"Cannot connect to logger: {e}")


async def handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    logger_address: str,
    logger_serial: int,
):

    global __solarman__
    global __slock__
    global __connected__

    addr = writer.get_extra_info("peername")
    print(f"{addr}: New connection")
    _solarman_init(logger_address, logger_serial)
    await _solarman_connect()

    if not __connected__:
        print("logger unavailable")
        writer.close()
        return


    try:
        while True:
            modbus_request = await reader.read(1024)
            if not modbus_request:
                break
            try:
                __slock__.acquire(blocking=True)
                reply = await __solarman__.send_raw_modbus_frame(bytearray(modbus_request))
                writer.write(reply)
                await writer.drain()
            except Exception as e:
                print(f'Proxy read error: {e}')
                writer.write(b'')
                await writer.drain()
            finally:
                __slock__.release()
    except OSError:
        # https://github.com/python/cpython/issues/83037
        pass

    print(f"{addr}: Connection closed")
    # await solarmanv5.disconnect()  # Should we disconnect the server from the logger at all ?!?
    # await _solarman_disconnect()  # If so uncomment this one


async def run_proxy(
    bind_address: str, port: int, logger_address: str, logger_serial: int
):
    server = await asyncio.start_server(
        partial(
            handle_client, logger_address=logger_address, logger_serial=logger_serial
        ),
        bind_address,
        port,
    )
    async with server:
        print(f"Listening on {bind_address}:{port}")
        await server.serve_forever()


def main():
    parser = argparse.ArgumentParser(
        prog="solarman rtu proxy",
        description="A Modbus RTU over TCP Proxy for Solarman loggers",
    )
    parser.add_argument(
        "-b", "--bind", default="0.0.0.0", help="The address to listen on"
    )
    parser.add_argument(
        "-p", "--port", default=1502, type=int, help="The TCP port to listen on"
    )
    parser.add_argument(
        "-l", "--logger", required=True, help="The IP address of the logger"
    )
    parser.add_argument(
        "-s",
        "--serial",
        required=True,
        type=int,
        help="The serial number of the logger",
    )
    args = parser.parse_args()

    asyncio.run(run_proxy(args.bind, args.port, args.logger, args.serial))


if __name__ == "__main__":
    main()

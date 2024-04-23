import time
import logging
from setup_test import SolarmanServer, AioSolarmanServer
from pysolarmanv5 import PySolarmanV5, NoSocketAvailableError
import pytest

log = logging.getLogger()
# server = SolarmanServer('127.0.0.1', 8899)
server = AioSolarmanServer("127.0.0.1", 8899)


def test_sync():
    solarman = PySolarmanV5(
        "127.0.0.1", 2612749371, auto_reconnect=True, verbose=True, socket_timeout=2
    )
    res = solarman.read_holding_registers(20, 4)
    log.debug(f"[Sync-HOLDING] Logger response: {res}")
    assert len(res) == 4
    # time.sleep(1)
    res = solarman.read_coils(30, 1)
    log.debug(f"[Sync-COILS] Logger response: {res}")
    assert len(res) > 0
    time.sleep(1)  # wait for auto-reconnect if enabled (see SolarmanServer)
    try:
        res = solarman.read_input_registers(40, 10)
        res = solarman.read_input_registers(50, 10)
        res = solarman.read_input_registers(60, 10)
    except NoSocketAvailableError:
        time.sleep(1)
        res = solarman.read_input_registers(40, 10)
        res = solarman.read_input_registers(50, 10)
        res = solarman.read_input_registers(60, 10)
    log.debug(f"[Sync-INPUT] Logger response: {res}")
    assert len(res) == 10
    solarman.disconnect()
    time.sleep(0.6)
    assert solarman._reader_thr.is_alive() is False
    with pytest.raises(NoSocketAvailableError):
        solarman.read_input_registers(40, 10)
    log.debug("[Sync] Disconnected!!!")

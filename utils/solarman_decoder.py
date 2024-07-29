import datetime
import enum
import sys

from umodbus.client.serial.redundancy_check import add_crc


class V5Definitions:

    Start = 0xa5
    End   = 0x15

    ReqFrameLen = 15
    RespFrameLen = 14


class V5CtrlCode(int, enum.Enum):
    V5Request = 0x4510
    V5Response = 0x1510
    LoggerPing = 0x4710
    LoggerResponse = 0x4210

    Unknown = 0xdeadc0de

    @classmethod
    def _missing_(cls, value):
        return V5CtrlCode.Unknown


class V5FrameType(int, enum.Enum):

    KeepAlive = 0
    Logger = 1
    Inverter = 2
    Unknown = -1

    @classmethod
    def _missing_(cls, value):
        return V5FrameType.Unknown


def unsigned_int(x: bytes) -> int:
    return int.from_bytes(x, byteorder='little', signed=False)


def rtu_unsigned_int(x: bytes) -> int:
    return int.from_bytes(x, byteorder='big', signed=False)


class V5Frame:

    def __init__(self, hex_frame: str):
        self._frame = bytes.fromhex(hex_frame)

    @property
    def frame_start(self) -> int:
        return self._frame[0]

    @property
    def frame_start_valid(self) -> bool:
        return self.frame_start == V5Definitions.Start

    @property
    def v5_checksum(self) -> int:
        flen = len(self._frame) - 2
        check = 0
        for i in range(1, flen):
            check = (check + self._frame[i]) & 0xff
        return check

    @property
    def v5_checksum_valid(self) -> bool:
        return self._frame[-2] == self.v5_checksum

    @property
    def v5_length(self) -> int:
        return unsigned_int(self._frame[1:3])

    @property
    def control_code(self) -> V5CtrlCode:
        return V5CtrlCode(unsigned_int(self._frame[3:5]))

    @property
    def sequence_numbers(self) -> (int, int):
        return self._frame[5], self._frame[6]

    @property
    def serial(self) -> int:
        return unsigned_int(self._frame[7:11])

    @property
    def frame_type(self) -> V5FrameType:
        return V5FrameType(self._frame[11])

    @property
    def frame_status(self) -> int:
        return self._frame[12]

    @property
    def total_work_time(self) -> int:
        if self.frame_type == V5FrameType.KeepAlive:
            return 0
        return unsigned_int(self._frame[13:17])

    @property
    def power_on_time(self) -> int:
        if self.frame_type == V5FrameType.KeepAlive:
            return 0
        return unsigned_int(self._frame[17:21])

    @property
    def offset_time(self) -> int:
        if self.frame_type == V5FrameType.KeepAlive:
            return 0
        return unsigned_int(self._frame[21:25])

    @property
    def frame_crc(self) -> int:
        return rtu_unsigned_int(self._frame[-4:-2])

    @property
    def calculated_crc(self) -> int:
        rtu_frame = self._frame[self.rtu_start_at:-4]
        rtu_crc = add_crc(rtu_frame)[-2:]
        return rtu_unsigned_int(rtu_crc)

    @property
    def rtu_crc_valid(self) -> bool:
        return self.frame_crc == self.calculated_crc

    @property
    def rtu_start_at(self) -> int:
        """
        RTU start position.

        A bit clunky, but it works (for now)

        :return:
        """
        if self.control_code == V5CtrlCode.V5Request or \
                self.control_code == V5CtrlCode.LoggerResponse:
            return 26
        return 25

    @property
    def rtu_head(self) -> str:
        head = self.rtu_start_at
        return self._frame[head:head+5].hex()

    def payload_string(self) -> str:
        start = self.rtu_start_at
        if self.control_code == V5CtrlCode.V5Request:
            payload_t = 'Request'
        elif self.control_code == V5CtrlCode.V5Response:
            payload_t = 'Response'
        else:
            payload_t = 'Unknown'

        msg = '=' * 10 + f' RTU Payload - [{payload_t}] ' + '=' * 10 + '\n\t'
        msg += f'Slave address: {self._frame[start]}\n\t'
        msg += f'Function code: {self._frame[start+1]}\n\t'
        msg += f'CRC: {self.calculated_crc:02x} (valid: {self.rtu_crc_valid})\n\t'

        if self.control_code == V5CtrlCode.V5Response:
            reported_size = self.v5_length - V5Definitions.RespFrameLen
            msg += f'Quantity: {reported_size}\n\t'
            msg += f'Data: {self._frame[start:-2].hex()}\n\t'
        elif self.control_code == V5CtrlCode.V5Request:
            addr = rtu_unsigned_int(self._frame[start+2:start+4])
            qty = rtu_unsigned_int(self._frame[start+4:start+6])
            msg += f'Request Start Addr: {addr} ({addr:02x})\n\t'
            msg += f'Request Quantity: {qty} ({qty:02x})\n\t'

        return msg


if __name__ == '__main__':
    frame = sys.argv[1:]
    solarman = V5Frame(''.join(frame))

    print(f'Frame start: {solarman.frame_start:02x} (valid: {solarman.frame_start_valid})')
    print(f'V5 Checksum: {solarman.v5_checksum:02x} (valid: {solarman.v5_checksum_valid})')
    print(f'Length: {solarman.v5_length}')
    print(f'Control Code: {solarman.control_code} (hex: {solarman.control_code:02x})')
    seq_no = solarman.sequence_numbers
    print(f'Sequence numbers: {seq_no} (hex: {seq_no[0]:02x} {seq_no[1]:02x})')
    print(f'Serial Hex: {solarman.serial:02x}')
    print(f'Serial: {solarman.serial}')
    ftype = solarman.frame_type
    print(f'Frame Type ({ftype.name}): {ftype.value}')
    print(f'Frame Status: {solarman.frame_status}')
    print(f'Total Time: {solarman.total_work_time}')
    print(f'PowerOn Time: {solarman.power_on_time}')
    print(f'Offset Time: {solarman.offset_time}')

    frame_time = solarman.total_work_time + solarman.power_on_time + solarman.offset_time
    print(f'Frame Time: {datetime.datetime.utcfromtimestamp(frame_time)}')
    if not solarman.frame_type == V5FrameType.KeepAlive:
        print(f'Checksum: {solarman.frame_crc} hex: {solarman.frame_crc:02x} - RTU start at: {solarman.rtu_head}')
        print(solarman.payload_string())

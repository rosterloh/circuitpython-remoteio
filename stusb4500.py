import time
from micropython import const

from adafruit_register.i2c_bit import RWBit
from adafruit_bus_device.i2c_device import I2CDevice

DEVICE_ID_REG = const(0x2F)
DEVICE_ID = const(0x21)

FTP_CUST_PASSWORD_REG = const(0x95)
FTP_CUST_PASSWORD = const(0x47)

FTP_CTRL_0 = const(0x96)
FTP_CUST_PWR = const(0x80) 
FTP_CUST_RST_N = const(0x40)
FTP_CUST_REQ = const(0x10)
FTP_CUST_SECT = const(0x07)
FTP_CTRL_1 = const(0x97)
FTP_CUST_OPCODE = const(0x07)
RW_BUFFER = const(0x53)

READ = const(0x00)


class STUSB4500:
    
    _ftp_cust_req = RWBit(FTP_CTRL_0, 4)
    _ftp_cust_rst_n = RWBit(FTP_CTRL_0, 6)
    _ftp_cust_pwr = RWBit(FTP_CTRL_0, 7)

    def __init__(
        self, i2c, *, interrupt_pin=None, address=0x28
    ):
        self.buf2 = bytearray(2)
        self.sectors = [bytearray(8), bytearray(8), bytearray(8), bytearray(8), bytearray(8)]

        self.i2c_device = I2CDevice(i2c, address)

        self._read_pd(DEVICE_ID_REG, self.buf2, 1)
        if self.buf2[0] != DEVICE_ID:
            raise RuntimeError()

        self._read_nvm()
        for i in range(5):
            print('{0}: {1}'.format(i, str(self.sectors[i])))

    def _read_pd(self, register, buffer, length):
        buf = self.buf2
        buf[0] = register
        with self.i2c_device as i2c:
            i2c.write(buf, end=1, stop=False)
            i2c.readinto(buffer, end=length)

    def _write_pd(self, register, abyte, length):
        buf = self.buf2
        buf[0] = register
        buf[1] = abyte
        with self.i2c_device as i2c:
            i2c.write(buf, end=length)

    def _enter_read_mode(self):
        # Set Password
        self._write_pd(FTP_CUST_PASSWORD_REG, FTP_CUST_PASSWORD, 1)
        
        # NVM Power-up Sequence
		# After STUSB start-up sequence, the NVM is powered off.

        # NVM internal controller reset
        self._write_pd(FTP_CTRL_0, 0, 1)
        self._read_pd(FTP_CTRL_0, self.buf2, 1)
        print('FTP_CTRL_0: {}'.format(hex(self.buf2[0])))
        # Set PWR and RST_N bits
        self._write_pd(FTP_CTRL_0, FTP_CUST_PWR | FTP_CUST_RST_N, 1)
        # self._ftp_cust_pwr = True
        # self._ftp_cust_rst_n = True
        self._read_pd(FTP_CTRL_0, self.buf2, 1)
        print('FTP_CTRL_0: {}'.format(hex(self.buf2[0])))

    def _exit_test_mode(self):
        self._ftp_cust_rst_n = True
        # self._write_pd(FTP_CTRL_0, FTP_CUST_RST_N, 1)
        # Clear Password 
        self._write_pd(FTP_CUST_PASSWORD_REG, 0, 1)

    def _read_nvm(self):
        self._enter_read_mode()

        for i in range(5):
            # Set PWR and RST_N bits
            self._write_pd(FTP_CTRL_0, FTP_CUST_PWR | FTP_CUST_RST_N, 1)
            # Set Read Sectors Opcode
            self._write_pd(FTP_CTRL_1, READ & FTP_CUST_OPCODE, 1)
            # Load Read Sectors Opcode
            self._write_pd(FTP_CTRL_0, (i & FTP_CUST_SECT) |FTP_CUST_PWR |FTP_CUST_RST_N | FTP_CUST_REQ, 1)
            
            # for j in range(10):
            # while True:
                # if not self._ftp_cust_req:
                    # break
                # print('Waiting for FTP_CUST_REQ to clear')
                # self._read_pd(FTP_CTRL_0, self.buf2, 1)
                # print('{0}: {1}'.format(j, hex(self.buf2[0])))
                # time.sleep(0.01)

            self._read_pd(RW_BUFFER, self.sectors[i], 8)

        self._exit_test_mode()
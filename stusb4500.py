import time
from micropython import const

from adafruit_register.i2c_bit import RWBit
from adafruit_bus_device.i2c_device import I2CDevice

_STUSB4500_DEFAULT_ADDRESS = const(0x28)

_DEVICE_ID_REG = const(0x2F)
_DEVICE_ID = const(0x21)

_FTP_CUST_PASSWORD_REG = const(0x95)
_FTP_CUST_PASSWORD = const(0x47)

_FTP_CTRL_0 = const(0x96)
_FTP_CUST_PWR = const(0x80) 
_FTP_CUST_RST_N = const(0x40)
_FTP_CUST_REQ = const(0x10)
_FTP_CUST_SECT = const(0x07)
_FTP_CTRL_1 = const(0x97)
_FTP_CUST_SER = const(0xF8)
_FTP_CUST_OPCODE = const(0x07)
_RW_BUFFER = const(0x53)

_READ = const(0x00)
_WRITE_PL = const(0x01)
_WRITE_SER = const(0x02)
_ERASE_SECTOR = const(0x05)
_PROG_SECTOR = const(0x06)
_SOFT_PROG_SECTOR = const(0x07)

_SECTOR_0 = const(0x01)
_SECTOR_1 = const(0x02)
_SECTOR_2 = const(0x03)
_SECTOR_3 = const(0x04)
_SECTOR_4 = const(0x05)


class STUSB4500:
    """Driver for the STUSB4500 USB-PD controller.

    :param busio.I2C i2c_bus: The I2C bus the STUSB4500 is connected to.
    :param int interrupt_pin: The gpio pin the hardware INT. Defaults to None.
    :param int address: The I2C address of the STUSB4500. Defaults to 0x28.

    """
    def __init__(self, i2c, interrupt_pin=None, address=_STUSB4500_DEFAULT_ADDRESS, debug=False):
        self.debug = debug

        self.i2c_device = I2CDevice(i2c, address)
        self.config = None

        if self._read_register(_DEVICE_ID_REG, 1)[0] is not _DEVICE_ID:
            raise RuntimeError()

    def _read_register(self, register, length):
        """Read `length` bytes from the specifed register"""
        with self.i2c_device as i2c:
            i2c.write(bytes([register & 0xFF]))
            result = bytearray(length)
            i2c.readinto(result)
            if self.debug:
                print("$%02X => %s" % (register, [hex(i) for i in result]))
            return result

    def _write_register(self, register, value):
        """Write a value to the specified register"""
        with self.i2c_device as i2c:
            i2c.write(bytes([register & 0xFF, value & 0xFF]))
            if self.debug:
                print("$%02X <= 0x%02X" % (register, value))

    def _wait_for_exec(self):
        """Wait for a command to execute"""
        status = _FTP_CUST_REQ
        while status & _FTP_CUST_REQ:
            status = self._read_register(_FTP_CTRL_0, 1)[0]

    def _enter_write_mode(self, erased_sector):
        # Set password
        self._write_register(_FTP_CUST_PASSWORD_REG, _FTP_CUST_PASSWORD)

        # Set RW_BUFFER to NULL for partial erase
        self._write_register(_RW_BUFFER, 0)

        # NVM Power-Up Sequence
        self._write_register(_FTP_CTRL_0, 0)
        self._write_register(_FTP_CTRL_0, _FTP_CUST_PWR | _FTP_CUST_RST_N)

        # Set Write SER opcode
        self._write_register(_FTP_CTRL_1, ((erased_sector << 3) & _FTP_CUST_SER) | (_WRITE_SER & _FTP_CUST_OPCODE))
        # Load Write SER opcode
        self._write_register(_FTP_CTRL_0, _FTP_CUST_PWR | _FTP_CUST_RST_N | _FTP_CUST_REQ)

        self._wait_for_exec()

        # Set Soft Prog Opcode
        self._write_register(_FTP_CTRL_1, _SOFT_PROG_SECTOR | _FTP_CUST_OPCODE)
        # Load Soft Prog Opcode
        self._write_register(_FTP_CTRL_0, _FTP_CUST_PWR | _FTP_CUST_RST_N | _FTP_CUST_REQ)

        self._wait_for_exec()

        # Set erase sectors opcode
        self._write_register(_FTP_CTRL_1, _ERASE_SECTOR | _FTP_CUST_OPCODE)
        # Load erase sectors opcode
        self._write_register(_FTP_CTRL_0, _FTP_CUST_PWR | _FTP_CUST_RST_N | _FTP_CUST_REQ)

        self._wait_for_exec()

    def _exit_test_mode(self):
        self._write_register(_FTP_CTRL_0, _FTP_CUST_RST_N)
        self._write_register(_FTP_CUST_PASSWORD_REG, 0)

    def _write_sector(self, sector_num, data):
        """
        Write a sector to NVM

        :param sector_num: Sector to write
        :type sector_num: int
        :param data: Data to write to sector
        :type data: list
        """

        # Write the data to the RW buffer
        for byte in data:
            self._write_register(_RW_BUFFER, byte)

        # Set PWR and RST_N bits
        self._write_register(_FTP_CTRL_0, _FTP_CUST_PWR | _FTP_CUST_RST_N)

        # NVM Program Load Register to write with the 64-bit data written to the buffer
        self._write_register(_FTP_CTRL_1, _FTP_CUST_PWR | _FTP_CUST_RST_N | _FTP_CUST_REQ)

        # Load write to PL sectors opcode
        self._write_register(_FTP_CTRL_0, _FTP_CUST_PWR | _FTP_CUST_RST_N | _FTP_CUST_REQ)

        self._wait_for_exec()

        # Set Prog sectors opcode
        self._write_register(_FTP_CTRL_1, _PROG_SECTOR | _FTP_CUST_OPCODE)

        # Load Prog Sectors opcode
        self._write_register(
            _FTP_CTRL_0,
            (sector_num & _FTP_CUST_SECT) | _FTP_CUST_PWR | _FTP_CUST_RST_N | _FTP_CUST_REQ
        )

        self._wait_for_exec()

    def read(self):
        """Read the NVM memory from the STUSB4500"""

        # Parameters
        sector = []

        # Enter read mode
        self._write_register(_FTP_CUST_PASSWORD_REG, _FTP_CUST_PASSWORD)

        # Reset internal NVM controller
        self._write_register(_FTP_CTRL_0, 0)

        for i in range(5):
            # Set PWR and RST_N bits
            self._write_register(_FTP_CTRL_0, _FTP_CUST_PWR | _FTP_CUST_RST_N)

            # Set read sectors opcode
            self._write_register(_FTP_CTRL_1, _READ & _FTP_CUST_OPCODE)

            # Load read sectors opcode
            self._write_register(_FTP_CTRL_0, (i & _FTP_CUST_SECT) | _FTP_CUST_PWR | _FTP_CUST_RST_N | _FTP_CUST_REQ)
            self._wait_for_exec()

            sector.append(self._read_register(_RW_BUFFER, 8))

        self._exit_test_mode()

        self.config = sector

    def write(self, default_values=False):
        """
        Write NVM settings to the STUSB4500

        Writes the current settings in the `self.config` variable to the
        STUSB4500. If `default_values` is set, the default values are then
        written.

        :param default_values: Write default values to NVM
        :type default_values:True
        """
        if not default_values:
            config = self.config
        else:
            config = [
                [0x00, 0x00, 0xB0, 0xAA, 0x00, 0x45, 0x00, 0x00],
                [0x10, 0x40, 0x9C, 0x1C, 0xFF, 0x01, 0x3C, 0xDF],
                [0x02, 0x40, 0x0F, 0x00, 0x32, 0x00, 0xFC, 0xF1],
                [0x00, 0x19, 0x56, 0xAF, 0xF5, 0x35, 0x5F, 0x00],
                [0x00, 0x4B, 0x90, 0x21, 0x43, 0x00, 0x40, 0xFB]
            ]

        self._enter_write_mode(_SECTOR_0 | _SECTOR_1 | _SECTOR_2 | _SECTOR_3 | _SECTOR_4)
        for sector, data in enumerate(config):
            self._write_sector(sector, data)
        self._exit_test_mode()

    def get_voltage(self, pdo):
        """
        Get output voltage for the specified PDO channel

        :param pdo: PDO Channel to retrieve voltage for
        :type pdo: int
        :return: Voltage in V
        :rtype: float
        """
        assert 1 <= pdo <= 3, "pdo channel not supported"

        # Read the configuration if it is empty
        if self.config is None:
            self.read()

        if pdo == 1:
            return 5
        elif pdo == 2:
            return self.config[4][1] * 0.2
        else:
            return (((self.config[4][3] & 0x03) << 8) + self.config[4][2]) * 0.05

    def get_current(self, pdo):
        """
        Get output current for the specified PDO channel

        :param pdo: PDO Channel to retrieve voltage for
        :type pdo: int
        :return: Current in A
        :rtype: float
        """
        assert 1 <= pdo <= 3, "pdo channel not supported"

        # Read the configuration if it is empty
        if self.config is None:
            self.read()

        if pdo == 1:
            cur_setting = (self.config[3][2] & 0xF0) >> 4
        elif pdo == 2:
            cur_setting = self.config[3][4] & 0x0F
        else:
            cur_setting = (self.config[3][5] & 0xF0) >> 4

        if cur_setting == 0:
            return 0
        elif cur_setting < 11:
            return cur_setting * 0.25 + 0.25
        else:
            return cur_setting * 0.50 - 2.50

    def get_lower_voltage_limit(self, pdo):
        """
        Get lower voltage lockout limit (5-20%)

        :param pdo: PDO Channel to retrieve voltage for
        :type pdo: int
        :return: Lower voltage limit in V
        :rtype: float
        """
        assert 1 <= pdo <= 3, "pdo channel not supported"

        # Read the configuration if it is empty
        if self.config is None:
            self.read()

        if pdo == 1:
            return 0
        elif pdo == 2:
            return (self.config[3][4] >> 4) + 5
        else:
            return (self.config[3][6] & 0x0F) + 5

    def get_upper_voltage_limit(self, pdo):
        """
        Get over voltage lockout limit (5-20%)

        :param pdo: PDO Channel to retrieve voltage for
        :type pdo: int
        :return: Upper voltage limit in V
        :rtype: float
        """
        assert 1 <= pdo <= 3, "pdo channel not supported"

        # Read the configuration if it is empty
        if self.config is None:
            self.read()

        if pdo == 1:
            return (self.config[3][3] >> 4) + 5
        elif pdo == 2:
            return (self.config[3][5] & 0x0F) + 5
        else:
            return (self.config[3][6] >> 4) + 5

    def get_flex_current(self):
        """
        Get the global current value common to all PDO numbers

        :return: Flex current in A
        :rtype: float
        """
        # Read the configuration if it is empty
        if self.config is None:
            self.read()

        return (((self.config[4][4] & 0x0F) << 6) + ((self.config[4][3] & 0xFC) >> 2)) / 100.0

    def get_pdo_number(self):
        """
        Get current PDO number in use

        :return: PDO channel in use
        :rtype: int
        """
        # Read the configuration if it is empty
        if self.config is None:
            self.read()

        return (self.config[3][2] & 0x06) >> 1

    def get_external_power(self):
        """
        Return the SNK_UNCONS_POWER parameter value

        0 - No external source of power
        1 - An external power source is available and is sufficient to power
            the system.
        :return: External power available
        :rtype: int
        """
        # Read the configuration if it is empty
        if self.config is None:
            self.read()

        return (self.config[3][2] & 0x08) >> 3

    def get_usb_comm_capable(self):
        """
        Returns the USB_COMM_CAPABLE parameter value.

        0 - Sink does not support data communication
        1 - Sink does support data communication

        :return USB_COMM_CAPABLE parameter value
        :rtype: int
        """
        # Read the configuration if it is empty
        if self.config is None:
            self.read()

        return self.config[3][2] & 0x01

    def get_config_ok_gpio(self):
        """
        Return the POWER_OK_CFG parameter value

        0 - Configuration 1
        1 - N/A
        2 - Configuration 2 (default)
        3 - Configuration 3

        Configuration 1:
        - VBUS_EN_SNK: Hi-Z - No source attached
                          0 - Source attached
        - POWER_OK2:   Hi-Z - No functionality
        - POWER_OK3:   Hi-Z - No functionality

        Configuration 2 (defualt):
        - VBUS_EN_SNK: Hi-Z - No source attached
                          0 - Source attached
        - POWER_OK2:   Hi-Z - No PD explicit contract
                          0 - PD explicit contract with PDO2
        - POWER_OK3:   Hi-Z - No PD explicit contract
                          0 - PD explicit contract with PDO3

        Configuration 3:
        - VBUS_EN_SNK: Hi-Z - No source attached
                          0 - source attached
        - POWER_OK2:   Hi-Z - No source attached or source supplies default
                              USB Type-C current at 5V when source attached.
                          0 - Source supplies 3.0A USB Type-C current at 5V
                              when source is attached.
        - POWER_OK3:   Hi-Z - No source attached or source supplies default
                              USB Type-C current at 5V when source attached.
                          0 - Source supplies 1.5A USB Type-C current at 5V
                              when source is attached.

        :return: POWER_OK_CFG value
        :rtype: int
        """
        # Read the configuration if it is empty
        if self.config is None:
            self.read()

        return (self.config[4][4] & 0x60) >> 5

    def get_gpio_ctrl(self):
        """
        Returns the GPIO pin configuration.

        0 - SW_CTRL_GPIO
        1 - ERROR_RECOVERY
        2 - DEBUG
        3 - SINK_POWER

        SW_CTRL_GPIO:
        - Software controlled GPIO. The output state is defined by the value
          of I2C register bit-0 at address 0x2D.

          Hi-Z - When bit-0 value is 0 (at start-up)
             0 - When bit-0 value is 1

        ERROR_RECOVERY:
        - Hardware fault detection (i.e. overtemperature is detected, overvoltage is
          detected on the CC pins, or after a hard reset the power delivery communication
          with the source is broken).

          Hi-Z - No hardware fault detected
             0 - Hardware fault detected

        DEBUG:
        - Debug accessory detection

          Hi-Z - No debug accessory detected
             0 - debug accessory detected

        SINK_POWER:
        - Indicates USB Type-C current capability advertised by the source.

          Hi-Z - Source supplies defualt or 1.5A USB Type-C current at 5V
             0 - Source supplies 3.0A USB Type-C current at 5V

        :return: GPIO pin configuration
        :rtype: int
        """
        # Read the configuration if it is empty
        if self.config is None:
            self.read()

        return (self.config[1][0] & 0x30) >> 4

    def get_power_above_5v_only(self):
        """
        Returns the POWER_ONLY_ABOVE_5V parameter configuration.

        0 - VBUS_EN_SNK pin enabled when source is attached whatever VBUS_EN_SNK
            voltage (5V or any PDO voltage)
        1 - VBUS_EN_SNK pin enabled only when source attached and VBUS voltage
            negotiated to PDO2 or PDO3 voltage

        :return: POWER_ONLY_ABOVE_5V configuration
        :rtype: int
        """
        # Read the configuration if it is empty
        if self.config is None:
            self.read()

        return (self.config[4][6] & 0x08) >> 3

    def get_req_src_current(self):
        """
        Return the REQ_SRC_CURRENT parameter configuration. In case of match, selects
        which operation current from the sink or the source is to be requested in the
        RDO message.

        0 - Request I(SNK_PDO) as operating current in RDO message
        1 - Request I(SRC_PDO) as operating current in RDO message

        :return: REQ_SRC_CURRENT parameter configuration
        :rtype: int
        """
        # Read the configuration if it is empty
        if self.config is None:
            self.read()

        return (self.config[4][6] & 0x10) >> 4

    def set_voltage(self, pdo, voltage):
        """
        Set the voltage for the given PDO channel

        Note: PDO1 - Fixed at 5V
              PDO2 - 5-20V, 20mV resolution
              PDO3 - 5-20V, 20mV resolution

        :param pdo: PDO channel to set voltage for
        :type pdo: int
        :param voltage: Voltage to set
        :type voltage: float
        """
        # Voltage can only be in range of 5-20V
        if voltage < 5:
            voltage = 5
        elif voltage > 20:
            voltage = 20

        # Read the configuration if it is empty
        if self.config is None:
            self.read()

        if pdo == 1:
            # PDO1 is fixed at 5V, no change needed
            return
        elif pdo == 2:
            self.config[4][1] = int(voltage / 0.2)
        else:
            set_voltage = int(voltage / 0.05)
            self.config[4][2] = 0xFF & set_voltage
            self.config[4][3] &= 0xFC
            self.config[4][3] |= set_voltage << 8

    def set_current(self, pdo, current):
        """
        Set the current limit for the given PDO channel

        Note: Valid current values are:
        0.00*, 0.50, 0.75, 1.00, 1.25, 1.50, 1.75, 2.00,
        2.25, 2.50, 2.75, 3.00, 3.50, 4.00, 4.50, 5.00

        :param pdo: PDO channel to set current for
        :type pdo: int
        :param current: Current limit to set in A
        :type current: float
        """
        # Current from 0.5A-3.0A set in 0.25A steps
        # Current from 3.0A-5.0A set in 0.50A steps
        if current < 0.5:
            current = 0
        elif current <= 3:
            current = (4 * current) - 1
        else:
            current = (2 * current) + 5

        # Read the configuration if it is empty
        if self.config is None:
            self.read()

        if pdo == 1:
            self.config[3][2] &= 0x0F
            self.config[3][2] |= int(current) << 4
        elif pdo == 2:
            self.config[3][4] &= 0xF0
            self.config[3][4] |= int(current)
        else:
            self.config[3][5] &= 0x0F
            self.config[3][5] |= int(current) << 4

    def set_lower_voltage_limit(self, pdo, value):
        """
        Sets the under voltage lock out parameter for the PDO channels

        :param pdo: PDO channel to set
        :type pdo: int
        :param value: Under voltage coefficient (5-20%)
        :type value: int
        """
        if value < 5:
            value = 5
        elif value > 20:
            value = 20

        # Read the configuration if it is empty
        if self.config is None:
            self.read()

        if pdo == 1:
            # UVLO1 fixed
            return
        elif pdo == 2:
            self.config[3][4] &= 0x0F
            self.config[3][4] |= (value - 5) << 4
        else:
            self.config[3][4] &= 0xF0
            self.config[3][4] |= value - 5

    def set_upper_voltage_limit(self, pdo, value):
        """
        Sets the over voltage lock out parameter for each of the PDO channels

        :param pdo: PDO channel to set
        :type pdo: int
        :param value: Over voltage coefficient (5-20%)
        ":type value: int
        """
        if value < 5:
            value = 5
        elif value > 20:
            value = 20

        # Read the configuration if it is empty
        if self.config is None:
            self.read()

        if pdo == 1:
            self.config[3][3] &= 0x0F
            self.config[3][3] |= (value - 5) << 4
        elif pdo == 2:
            self.config[3][5] &= 0xF0
            self.config[3][5] |= (value - 5)
        elif pdo == 3:
            self.config[3][6] &= 0x0F
            self.config[3][6] |= (value - 5) << 4

    def set_flex_current(self, value):
        """
        Set the flexible current value common to all PDO channels

        :param value: Current value to set the FLEX_I parameter (0-5A)
        :type value: float
        """
        if value < 0:
            value = 0
        elif value > 5:
            value = 5

        # Read the configuration if it is empty
        if self.config is None:
            self.read()

        flex_value = value * 100

        self.config[4][3] &= 0x03
        self.config[4][3] |= ((flex_value & 0x3F) << 2)

        self.config[4][4] &= 0xF0
        self.config[4][4] |= ((flex_value & 0x3C0) >> 6)

    def set_pdo_number(self, value):
        """
        Set the number of sink PDOs

        0 - 1 PDO (5V only)
        1 - 1 PDO (5V only)
        2 - 2 PDOs (PDO2 has the highest priority, followed by PDO1)
        3 - 3 PDOs (PDO3 has the highest priority, followed by PDO2, and then PDO1).

        :param value: Number of sink PDOs
        :type value: int
        """
        assert 1 <= value <= 3

        # Read the configuration if it is empty
        if self.config is None:
            self.read()

        self.config[3][2] &= 0xF9
        self.config[3][2] |= value << 1

    def set_external_power(self, value):
        """
        Sets the SNK_UNCONS_POWER parameter value

        0 - No external source of power
        1 - An external power source is available and is sufficient to

        :param value: Value to set to SNK_UNCONS_POWER
        :type value: int
        """
        if value != 0:
            value = 1

        # Read the configuration if it is empty
        if self.config is None:
            self.read()

        self.config[3][2] &= 0xF7
        self.config[3][2] |= value

    def set_usb_comm_capable(self, value):
        """
        Sets the USB_COMM_CAPABLE parameter value

        0 - Sink does not support data communication
        1 - Sink does support data communication

        :param value: Value to set USB_COMM_CAPABLE
        :type value: int
        """
        if value != 0:
            value = 1

        # Read the configuration if it is empty
        if self.config is None:
            self.read()

        self.config[3][2] &= 0xFE
        self.config[3][2] |= value

    def set_config_ok_gpio(self, value):
        """
        Sets the POWER_OK_CFG parameter value.

        Parameter: value - Value to set to POWER_OK_CFG
        0 - Configuration 1
        1 - No applicable
        2 - Configuration 2 (default)
        3 - Configuration 3

        Configuration 1:
        - VBUS_EN_SNK: Hi-Z - No source attached
                          0 - Source attached
        - POWER_OK2:   Hi-Z - No functionality
        - POWER_OK3:   Hi-Z - No functionality

        Configuration 2 (defualt):
        - VBUS_EN_SNK: Hi-Z - No source attached
                          0 - Source attached
        - POWER_OK2:   Hi-Z - No PD explicit contract
                          0 - PD explicit contract with PDO2
        - POWER_OK3:   Hi-Z - No PD explicit contract
                          0 - PD explicit contract with PDO3

        Configuration 3:
        - VBUS_EN_SNK: Hi-Z - No source attached
                          0 - source attached
        - POWER_OK2:   Hi-Z - No source attached or source supplies default
                              USB Type-C current at 5V when source attached.
                          0 - Source supplies 3.0A USB Type-C current at 5V
                              when source is attached.
        - POWER_OK3:   Hi-Z - No source attached or source supplies default
                              USB Type-C current at 5V when source attached.
                          0 - Source supplies 1.5A USB Type-C current at 5V
                              when source is attached.
        :param value: Configuration to set
        :type value: int
        """
        if value < 2:
            value = 0
        elif value > 3:
            value = 3

        # Read the configuration if it is empty
        if self.config is None:
            self.read()

        self.config[4][4] &= 0xCF
        self.config[4][4] |= value << 5

    def set_gpio_ctrl(self, value):
        """
        Sets the GPIO pin configuration.

        Paramter: value - Value to set to GPIO_CFG
        0 - SW_CTRL_GPIO
        1 - ERROR_RECOVERY
        2 - DEBUG
        3 - SINK_POWER

        SW_CTRL_GPIO:
        - Software controlled GPIO. The output state is defined by the value
          of I2C register bit-0 at address 0x2D.

          Hi-Z - When bit-0 value is 0 (at start-up)
             0 - When bit-0 value is 1

        ERROR_RECOVERY:
        - Hardware fault detection (i.e. overtemperature is detected, overvoltage is
          detected on the CC pins, or after a hard reset the power delivery communication
          with the source is broken).

          Hi-Z - No hardware fault detected
             0 - Hardware fault detected

        DEBUG:
        - Debug accessory detection

          Hi-Z - No debug accessory detected
             0 - debug accessory detected

        SINK_POWER:
        - Indicates USB Type-C current capability advertised by the source.

          Hi-Z - Source supplies defualt or 1.5A USB Type-C current at 5V
             0 - Source supplies 3.0A USB Type-C current at 5V

        :param value: GPIO configuration to set
        :type value: int
        """
        assert 0 <= value <= 3, "configuration not supported"

        # Read the configuration if it is empty
        if self.config is None:
            self.read()

        self.config[1][0] &= 0xCF
        self.config[1][0] |= value << 4

    def set_power_above_5v_only(self, value):
        """
        Sets the POWER_ONLY_ABOVE_5V parameter configuration.

        0 - VBUS_EN_SNK pin enabled when source is attached whatever VBUS_EN_SNK
            voltage (5V or any PDO voltage)
        1 - VBUS_EN_SNK pin enabled only when source attached and VBUS voltage
            negotiated to PDO2 or PDO3 voltage

        :param value: Value to select VBUS_EN_SNK pin configuration
        :type value: int
        """
        if value != 0:
            value = 1

        # Read the configuration if it is empty
        if self.config is None:
            self.read()

        self.config[4][6] &= 0xF7
        self.config[4][6] |= value << 3

    def set_req_src_current(self, value):
        """
        Sets the REQ_SRC_CURRENT parameter configuration. In case of match, selects
        which operation current from the sink or the source is to be requested in the
        RDO message.

        0 - Request I(SNK_PDO) as operating current in RDO message
        1 - Request I(SRC_PDO) as operating current in RDO message

        :param value: Value to set to REQ_SRC_CURRENT
        :type value: int
        """
        if value != 0:
            value = 1

        # Read the configuration if it is empty
        if self.config is None:
            self.read()

        self.config[4][6] &= 0xEF
        self.config[4][6] |= value << 4

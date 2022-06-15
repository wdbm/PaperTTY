#     Copyright (c) 2018 Jouko Strömmer
#     Copyright (c) 2017 Waveshare
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <https://www.gnu.org/licenses/>.
from papertty.drivers.drivers_base import WaveshareEPD


class WavesharePartial(WaveshareEPD):
    """Displays that support partial refresh (*monochrome*): 1.54", 2.13", 2.9". 
    The code is almost entirely identical with these, just small differences in the 2.13"."""

    BOOSTER_SOFT_START_CONTROL = 0x0C
    BORDER_WAVEFORM_CONTROL = 0x3C
    DATA_ENTRY_MODE_SETTING = 0x11
    DEEP_SLEEP_MODE = 0x10
    DISPLAY_UPDATE_CONTROL_1 = 0x21
    DISPLAY_UPDATE_CONTROL_2 = 0x22
    DRIVER_OUTPUT_CONTROL = 0x01
    GATE_SCAN_START_POSITION = 0x0F
    MASTER_ACTIVATION = 0x20
    SET_DUMMY_LINE_PERIOD = 0x3A
    SET_GATE_TIME = 0x3B
    SET_RAM_X_ADDRESS_COUNTER = 0x4E
    SET_RAM_X_ADDRESS_START_END_POSITION = 0x44
    SET_RAM_Y_ADDRESS_COUNTER = 0x4F
    SET_RAM_Y_ADDRESS_START_END_POSITION = 0x45
    SW_RESET = 0x12
    TEMPERATURE_SENSOR_CONTROL = 0x1A
    TERMINATE_FRAME_READ_WRITE = 0xFF
    WRITE_LUT_REGISTER = 0x32
    WRITE_RAM = 0x24
    WRITE_VCOM_REGISTER = 0x2C

    # these LUTs are used by 1.54" and 2.9" - 2.13" overrides them
    lut_full_update = [
        0x02, 0x02, 0x01, 0x11, 0x12, 0x12, 0x22, 0x22,
        0x66, 0x69, 0x69, 0x59, 0x58, 0x99, 0x99, 0x88,
        0x00, 0x00, 0x00, 0x00, 0xF8, 0xB4, 0x13, 0x51,
        0x35, 0x51, 0x51, 0x19, 0x01, 0x00
    ]

    lut_partial_update = [
        0x10, 0x18, 0x18, 0x08, 0x18, 0x18, 0x08, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x13, 0x14, 0x44, 0x12,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.supports_partial = True
        self.colors = 2
        self.lut = None

    def init(self, partial=True):
        self.partial_refresh = partial
        if self.epd_init() != 0:
            return -1
        # EPD hardware init start
        self.lut = self.lut_partial_update if partial else self.lut_full_update
        self.reset()
        self.send_command(self.DRIVER_OUTPUT_CONTROL)
        self.send_data((self.height - 1) & 0xFF)
        self.send_data(((self.height - 1) >> 8) & 0xFF)
        self.send_data(0x00)  # GD = 0 SM = 0 TB = 0
        self.send_command(self.BOOSTER_SOFT_START_CONTROL)
        self.send_data(0xD7)
        self.send_data(0xD6)
        self.send_data(0x9D)
        self.send_command(self.WRITE_VCOM_REGISTER)
        self.send_data(0xA8)  # VCOM 7C
        self.send_command(self.SET_DUMMY_LINE_PERIOD)
        self.send_data(0x1A)  # 4 dummy lines per gate
        self.send_command(self.SET_GATE_TIME)
        self.send_data(0x08)  # 2us per line
        self.send_command(self.DATA_ENTRY_MODE_SETTING)
        self.send_data(0x03)  # X increment Y increment
        self.set_lut(self.lut)
        # EPD hardware init end
        return 0

    def wait_until_idle(self):
        while self.digital_read(self.BUSY_PIN) == 1:  # 0: idle, 1: busy
            self.delay_ms(100)

    def set_lut(self, lut):
        self.lut = lut
        self.send_command(self.WRITE_LUT_REGISTER)
        # the length of look-up table is 30 bytes
        for i in range(0, len(lut)):
            self.send_data(self.lut[i])

    def get_frame_buffer(self, image):
        buf = [0x00] * int(self.width * self.height / 8)
        # Set buffer to value of Python Imaging Library image.
        # Image must be in mode 1.
        image_monocolor = image.convert('1')
        imwidth, imheight = image_monocolor.size
        if imwidth != self.width or imheight != self.height:
            raise ValueError('Image must be same dimensions as display \
                ({0}x{1}).'.format(self.width, self.height))

        pixels = image_monocolor.load()
        for y in range(self.height):
            for x in range(self.width):
                # Set the bits for the column of pixels at the current position.
                if pixels[x, y] != 0:
                    buf[int((x + y * self.width) / 8)] |= 0x80 >> (x % 8)
        return buf

    # this differs with 2.13" but is the same for 1.54" and 2.9"
    def set_frame_memory(self, image, x, y):
        if image is None or x < 0 or y < 0:
            return
        image_monocolor = image.convert('1')
        image_width, image_height = image_monocolor.size
        # x point must be the multiple of 8 or the last 3 bits will be ignored
        x = x & 0xF8
        image_width = image_width & 0xF8
        if x + image_width >= self.width:
            x_end = self.width - 1
        else:
            x_end = x + image_width - 1
        if y + image_height >= self.height:
            y_end = self.height - 1
        else:
            y_end = y + image_height - 1
        self.set_memory_area(x, y, x_end, y_end)
        self.set_memory_pointer(x, y)
        self.send_command(self.WRITE_RAM)
        # send the image data
        pixels = image_monocolor.load()
        byte_to_send = 0x00
        for j in range(0, y_end - y + 1):
            # 1 byte = 8 pixels, steps of i = 8
            for i in range(0, x_end - x + 1):
                # Set the bits for the column of pixels at the current position.
                if pixels[i, j] != 0:
                    byte_to_send |= 0x80 >> (i % 8)
                if i % 8 == 7:
                    self.send_data(byte_to_send)
                    byte_to_send = 0x00

    def clear_frame_memory(self, color):
        self.set_memory_area(0, 0, self.width - 1, self.height - 1)
        self.set_memory_pointer(0, 0)
        self.send_command(self.WRITE_RAM)
        # send the color data
        for i in range(0, int(self.width / 8 * self.height)):
            self.send_data(color)

    def display_frame(self):
        self.send_command(self.DISPLAY_UPDATE_CONTROL_2)
        self.send_data(0xC4)
        self.send_command(self.MASTER_ACTIVATION)
        self.send_command(self.TERMINATE_FRAME_READ_WRITE)
        self.wait_until_idle()

    def set_memory_area(self, x_start, y_start, x_end, y_end):
        self.send_command(self.SET_RAM_X_ADDRESS_START_END_POSITION)
        # x point must be the multiple of 8 or the last 3 bits will be ignored
        self.send_data((x_start >> 3) & 0xFF)
        self.send_data((x_end >> 3) & 0xFF)
        self.send_command(self.SET_RAM_Y_ADDRESS_START_END_POSITION)
        self.send_data(y_start & 0xFF)
        self.send_data((y_start >> 8) & 0xFF)
        self.send_data(y_end & 0xFF)
        self.send_data((y_end >> 8) & 0xFF)

    def set_memory_pointer(self, x, y):
        self.send_command(self.SET_RAM_X_ADDRESS_COUNTER)
        # x point must be the multiple of 8 or the last 3 bits will be ignored
        self.send_data((x >> 3) & 0xFF)
        self.send_command(self.SET_RAM_Y_ADDRESS_COUNTER)
        self.send_data(y & 0xFF)
        self.send_data((y >> 8) & 0xFF)
        self.wait_until_idle()

    def sleep(self):
        self.send_command(self.DEEP_SLEEP_MODE)
        self.wait_until_idle()

    def draw(self, x, y, image):
        """Replace a particular area on the display with an image"""
        self.set_frame_memory(image, x, y)
        self.display_frame()
        if self.partial_refresh:
            # set the memory again if partial refresh LUT is used
            self.set_frame_memory(image, x, y)
            self.display_frame()


class EPD1in54(WavesharePartial):
    """Waveshare 1.54" - monochrome"""

    def __init__(self):
        super().__init__(name='1.54" BW', width=200, height=200)


class EPD2in13(WavesharePartial):
    """Waveshare 2.13" - monochrome"""

    lut_full_update = [
        0x22, 0x55, 0xAA, 0x55, 0xAA, 0x55, 0xAA, 0x11,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x1E, 0x1E, 0x1E, 0x1E, 0x1E, 0x1E, 0x1E, 0x1E,
        0x01, 0x00, 0x00, 0x00, 0x00, 0x00
    ]

    lut_partial_update = [
        0x18, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x0F, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00
    ]

    def __init__(self):
        # the actual pixel width is 122, but 128 is the 'logical' width
        super().__init__(name='2.13" BW', width=128, height=250)

    def set_frame_memory(self, image, x, y):
        if image is None or x < 0 or y < 0:
            return
        image_monocolor = image.convert('1')
        image_width, image_height = image_monocolor.size
        # x point must be the multiple of 8 or the last 3 bits will be ignored
        x = x & 0xF8
        image_width = image_width & 0xF8
        if x + image_width >= self.width:
            x_end = self.width - 1
        else:
            x_end = x + image_width - 1
        if y + image_height >= self.height:
            y_end = self.height - 1
        else:
            y_end = y + image_height - 1
        self.set_memory_area(x, y, x_end, y_end)
        # send the image data
        pixels = image_monocolor.load()
        byte_to_send = 0x00
        for j in range(y, y_end + 1):
            self.set_memory_pointer(x, j)
            self.send_command(self.WRITE_RAM)
            # 1 byte = 8 pixels, steps of i = 8
            for i in range(x, x_end + 1):
                # Set the bits for the column of pixels at the current position.
                if pixels[i - x, j - y] != 0:
                    byte_to_send |= 0x80 >> (i % 8)
                if i % 8 == 7:
                    self.send_data(byte_to_send)
                    byte_to_send = 0x00


class EPD2in13v2(WavesharePartial):
    """Waveshare 2.13" V2 - monochrome"""

    lut_full_update = [
        0x80,0x60,0x40,0x00,0x00,0x00,0x00,             #LUT0: BB:     VS 0 ~7
        0x10,0x60,0x20,0x00,0x00,0x00,0x00,             #LUT1: BW:     VS 0 ~7
        0x80,0x60,0x40,0x00,0x00,0x00,0x00,             #LUT2: WB:     VS 0 ~7
        0x10,0x60,0x20,0x00,0x00,0x00,0x00,             #LUT3: WW:     VS 0 ~7
        0x00,0x00,0x00,0x00,0x00,0x00,0x00,             #LUT4: VCOM:   VS 0 ~7

        0x03,0x03,0x00,0x00,0x02,                       # TP0 A~D RP0
        0x09,0x09,0x00,0x00,0x02,                       # TP1 A~D RP1
        0x03,0x03,0x00,0x00,0x02,                       # TP2 A~D RP2
        0x00,0x00,0x00,0x00,0x00,                       # TP3 A~D RP3
        0x00,0x00,0x00,0x00,0x00,                       # TP4 A~D RP4
        0x00,0x00,0x00,0x00,0x00,                       # TP5 A~D RP5
        0x00,0x00,0x00,0x00,0x00,                       # TP6 A~D RP6

        0x15,0x41,0xA8,0x32,0x30,0x0A
    ]

    lut_partial_update = [
        0x00,0x00,0x00,0x00,0x00,0x00,0x00,             #LUT0: BB:     VS 0 ~7
        0x80,0x00,0x00,0x00,0x00,0x00,0x00,             #LUT1: BW:     VS 0 ~7
        0x40,0x00,0x00,0x00,0x00,0x00,0x00,             #LUT2: WB:     VS 0 ~7
        0x00,0x00,0x00,0x00,0x00,0x00,0x00,             #LUT3: WW:     VS 0 ~7
        0x00,0x00,0x00,0x00,0x00,0x00,0x00,             #LUT4: VCOM:   VS 0 ~7

        0x0A,0x00,0x00,0x00,0x00,                       # TP0 A~D RP0
        0x00,0x00,0x00,0x00,0x00,                       # TP1 A~D RP1
        0x00,0x00,0x00,0x00,0x00,                       # TP2 A~D RP2
        0x00,0x00,0x00,0x00,0x00,                       # TP3 A~D RP3
        0x00,0x00,0x00,0x00,0x00,                       # TP4 A~D RP4
        0x00,0x00,0x00,0x00,0x00,                       # TP5 A~D RP5
        0x00,0x00,0x00,0x00,0x00,                       # TP6 A~D RP6

        0x15,0x41,0xA8,0x32,0x30,0x0A,
    ]

    def __init__(self):
        # the actual pixel width is 122, but 128 is the 'logical' width
        super().__init__(name='2.13" BW V2 (full refresh only)', width=128, height=250)


class EPD2in9(WavesharePartial):
    """Waveshare 2.9" - monochrome"""

    def __init__(self):
        super().__init__(name='2.9" BW', width=128, height=296)


class EPD2in13d(WavesharePartial):
    """Waveshare 2.13" D - monochrome (flexible)"""

    # Note: the original code for this display was pretty broken and seemed
    # to have been written by some other person than the rest of the drivers.

    def __init__(self):
        super().__init__(name='2.13" D', width=104, height=212)

    lut_vcomDC = [
        0x00, 0x08, 0x00, 0x00, 0x00, 0x02,
        0x60, 0x28, 0x28, 0x00, 0x00, 0x01,
        0x00, 0x14, 0x00, 0x00, 0x00, 0x01,
        0x00, 0x12, 0x12, 0x00, 0x00, 0x01,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00,
    ]

    lut_ww = [
        0x40, 0x08, 0x00, 0x00, 0x00, 0x02,
        0x90, 0x28, 0x28, 0x00, 0x00, 0x01,
        0x40, 0x14, 0x00, 0x00, 0x00, 0x01,
        0xA0, 0x12, 0x12, 0x00, 0x00, 0x01,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    ]

    lut_bw = [
        0x40, 0x17, 0x00, 0x00, 0x00, 0x02,
        0x90, 0x0F, 0x0F, 0x00, 0x00, 0x03,
        0x40, 0x0A, 0x01, 0x00, 0x00, 0x01,
        0xA0, 0x0E, 0x0E, 0x00, 0x00, 0x02,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    ]

    lut_wb = [
        0x80, 0x08, 0x00, 0x00, 0x00, 0x02,
        0x90, 0x28, 0x28, 0x00, 0x00, 0x01,
        0x80, 0x14, 0x00, 0x00, 0x00, 0x01,
        0x50, 0x12, 0x12, 0x00, 0x00, 0x01,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    ]

    lut_bb = [
        0x80, 0x08, 0x00, 0x00, 0x00, 0x02,
        0x90, 0x28, 0x28, 0x00, 0x00, 0x01,
        0x80, 0x14, 0x00, 0x00, 0x00, 0x01,
        0x50, 0x12, 0x12, 0x00, 0x00, 0x01,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    ]

    lut_vcom1 = [
        0x00, 0x19, 0x01, 0x00, 0x00, 0x01,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00,
    ]

    lut_ww1 = [
        0x00, 0x19, 0x01, 0x00, 0x00, 0x01,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    ]

    lut_bw1 = [
        0x80, 0x19, 0x01, 0x00, 0x00, 0x01,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    ]

    lut_wb1 = [
        0x40, 0x19, 0x01, 0x00, 0x00, 0x01,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    ]

    lut_bb1 = [
        0x00, 0x19, 0x01, 0x00, 0x00, 0x01,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    ]

    def wait_until_idle(self):
        """This particular model's code sends the GET_STATUS command while waiting - dunno why."""
        while self.digital_read(self.BUSY_PIN) == 0:  # 0: idle, 1: busy
            self.send_command(self.GET_STATUS)
            self.delay_ms(100)

    def init(self, **kwargs):
        if self.epd_init() != 0:
            return -1
        self.reset()

        self.send_command(0x01)  # POWER SETTING
        self.send_data(0x03)
        self.send_data(0x00)
        self.send_data(0x2b)
        self.send_data(0x2b)
        self.send_data(0x03)

        self.send_command(0x06)  # boost soft start
        self.send_data(0x17)  # A
        self.send_data(0x17)  # B
        self.send_data(0x17)  # C

        self.send_command(0x04)
        self.wait_until_idle()

        self.send_command(0x00)  # panel setting
        self.send_data(0xbf)  # LUT from OTP,128x296
        self.send_data(0x0d)  # VCOM to 0V fast

        self.send_command(0x30)  # PLL setting
        self.send_data(0x3a)  # 3a 100HZ   29 150Hz 39 200HZ	31 171HZ

        self.send_command(0x61)  # resolution setting
        self.send_data(self.width)
        self.send_data((self.height >> 8) & 0xff)
        self.send_data(self.height & 0xff)

        self.send_command(0x82)  # vcom_DC setting
        self.send_data(0x28)

        # self.send_command(0X50)			#VCOM AND DATA INTERVAL SETTING
        # self.send_data(0xb7)		#WBmode:VBDF 17|D7 VBDW 97 VBDB 57		WBRmode:VBDF F7 VBDW 77 VBDB 37  VBDR B7
        return 0

    def set_full_reg(self):
        self.send_command(0x82)
        self.send_data(0x00)
        self.send_command(0X50)
        self.send_data(0xb7)

        self.send_command(0x20)  # vcom
        for count in range(0, 44):
            self.send_data(self.lut_vcomDC[count])
        self.send_command(0x21)  # ww --
        for count in range(0, 42):
            self.send_data(self.lut_ww[count])
        self.send_command(0x22)  # bw r
        for count in range(0, 42):
            self.send_data(self.lut_bw[count])
        self.send_command(0x23)  # wb w
        for count in range(0, 42):
            self.send_data(self.lut_wb[count])
        self.send_command(0x24)  # bb b
        for count in range(0, 42):
            self.send_data(self.lut_bb[count])

    def set_part_reg(self):
        self.send_command(0x82)
        self.send_data(0x03)
        self.send_command(0X50)
        self.send_data(0x47)

        self.send_command(0x20)  # vcom
        for count in range(0, 44):
            self.send_data(self.lut_vcom1[count])
        self.send_command(0x21)  # ww --
        for count in range(0, 42):
            self.send_data(self.lut_ww1[count])
        self.send_command(0x22)  # bw r
        for count in range(0, 42):
            self.send_data(self.lut_bw1[count])
        self.send_command(0x23)  # wb w
        for count in range(0, 42):
            self.send_data(self.lut_wb1[count])
        self.send_command(0x24)  # bb b
        for count in range(0, 42):
            self.send_data(self.lut_bb1[count])

    def turn_on_display(self):
        self.send_command(0x12)
        self.delay_ms(10)
        self.wait_until_idle()

    def clear(self):
        self.send_command(0x10)
        for i in range(0, int(self.width * self.height / 8)):
            self.send_data(0x00)
        self.delay_ms(10)

        self.send_command(0x13)
        for i in range(0, int(self.width * self.height / 8)):
            self.send_data(0xFF)
        self.delay_ms(10)

        self.set_full_reg()
        self.turn_on_display()

    def display_full(self, frame_buffer):
        if not frame_buffer:
            return

        self.send_command(0x10)
        for i in range(0, int(self.width * self.height / 8)):
            self.send_data(0x00)
        self.delay_ms(10)

        self.send_command(0x13)
        for i in range(0, int(self.width * self.height / 8)):
            self.send_data(frame_buffer[i])
        self.delay_ms(10)

        self.set_full_reg()
        self.turn_on_display()

    def display_partial(self, frame_buffer, x_start, y_start, x_end, y_end):
        if not frame_buffer:
            return

        self.set_part_reg()
        self.send_command(0x91)
        self.send_command(0x90)
        self.send_data(x_start)
        self.send_data(x_end - 1)

        self.send_data(y_start / 256)
        self.send_data(y_start % 256)
        self.send_data(y_end / 256)
        self.send_data(y_end % 256 - 1)
        self.send_data(0x28)

        self.send_command(0x10)
        for i in range(0, int(self.width * self.height / 8)):
            # print(frame_buffer[i],'%d','0x10')
            self.send_data(frame_buffer[i])
        self.delay_ms(10)

        self.send_command(0x13)
        for i in range(0, int(self.width * self.height / 8)):
            # print(~frame_buffer[i],'%d','0x13')
            self.send_data(~frame_buffer[i])
        self.delay_ms(10)

        # self.set_full_reg()
        self.turn_on_display()

    # after this, call epd.init() to awaken the module
    def sleep(self):
        self.send_command(0x50)
        self.send_data(0xf7)
        self.send_command(0x02)  # power off
        self.send_command(0x07)  # deep sleep
        self.send_data(0xA5)

    def draw(self, x, y, image):
        """Replace a particular area on the display with an image"""
        if self.partial_refresh:
            self.display_partial(self.get_frame_buffer(image), x, y, x + image.width, x + image.height)
        else:
            self.display_full(self.get_frame_buffer(image))

class EPD7in5v2partial(WavesharePartial):
    """WaveShare 7.5" GDEW075T7 - monochrome
    https://github.com/joukos/PaperTTY/issues/65#issue-681003449"""

    PANEL_SETTING = 0x00
    POWER_SETTING = 0x01
    POWER_OFF = 0x02
    POWER_OFF_SEQUENCE_SETTING = 0x03
    POWER_ON = 0x04
    POWER_ON_MEASURE = 0x05
    BOOSTER_SOFT_START = 0x06
    DEEP_SLEEP = 0x07
    DATA_START_TRANSMISSION_1 = 0x10
    DATA_STOP = 0x11
    DISPLAY_REFRESH = 0x12
    DATA_START_TRANSMISSION_2 = 0x13
    LUT_FOR_VCOM = 0x20
    LUT_WHITE_TO_WHITE = 0x21
    LUT_BLACK_TO_WHITE = 0x22
    LUT_WHITE_TO_BLACK = 0x23
    LUT_BLACK_TO_BLACK = 0x24
    PLL_CONTROL = 0x30
    TEMPERATURE_SENSOR_COMMAND = 0x40
    TEMPERATURE_SENSOR_SELECTION = 0x41
    TEMPERATURE_SENSOR_WRITE = 0x42
    TEMPERATURE_SENSOR_READ = 0x43
    VCOM_AND_DATA_INTERVAL_SETTING = 0x50
    LOW_POWER_DETECTION = 0x51
    TCON_SETTING = 0x60
    RESOLUTION_SETTING = 0x61
    GSST_SETTING = 0x65
    GET_STATUS = 0x71
    AUTO_MEASUREMENT_VCOM = 0x80
    READ_VCOM_VALUE = 0x81
    VCM_DC_SETTING = 0x82
    PARTIAL_WINDOW = 0x90
    PARTIAL_IN = 0x91
    PARTIAL_OUT = 0x92
    PROGRAM_MODE = 0xA0
    ACTIVE_PROGRAMMING = 0xA1
    READ_OTP = 0xA2
    POWER_SAVING = 0xE3

    # LUTs

    T1 = 0x1e # 30, charge balance pre-phase
    T2 = 0x05 # 5, optional extension
    T3 = 0x1e # 30, colour change phase (b/w)
    T4 = 0x05 # optional extension for one colour

    lut_vcom1 = [
        0x00, T1, T2, T3, T4, 0x01,
    ] + ([0x00] * 36) # total size: 42

    lut_ww1 = [
        0x00, T1, T2, T3, T4, 0x01,
    ] + ([0x00] * 36)

    lut_bw1 = [
        0x5A, T1, T2, T3, T4, 0x01, # 0x5A: more white
    ] + ([0x00] * 36)


    lut_wb1 = [
        0x84, T1, T2, T3, T4, 0x01,
    ] + ([0x00] * 36)

    lut_bb1 = [
        0x00, T1, T2, T3, T4, 0x01,
    ] + ([0x00] * 36)

    lut_bd1 = [
        0x00, T1, T2, T3, T4, 0x01
    ] + ([0x00] * 36)

    def __init__(self):
        super().__init__(name='7.5" new version (with partial)', width=800, height=480)

    def init(self, partial=False):
        '''
        Initialise the ePaper screen

        - partial: whether to support partial refresh or not
        '''

        self.partial_refresh = partial
        self.in_partial = False
        print('Partial support: {}'.format(partial))

        # EPD hardware init start
        # self.lut = self.lut_partial_update if partial else self.lut_full_update
        if self.epd_init() != 0:
            return -1

        # if self.is_hibernating: self.reset()
        self.reset()

        self.send_command(self.BOOSTER_SOFT_START)  # boost soft start
        self.send_data(0x17)  # A
        self.send_data(0x17)  # B
        self.send_data(0x27)
        self.send_data(0x17)  # C

        self.send_command(self.POWER_SETTING)
        self.send_data(0x07) # VDS_EN, VDG_EN
        self.send_data(0x17) # VCOM_HV, VGHL_LV[1], VGHL_LV[0]
        self.send_data(0x3f) # VDH
        self.send_data(0x3f) # VDL

        self.send_command(self.RESOLUTION_SETTING)
        self.send_data(0x03)
        self.send_data(0x20)
        self.send_data(0x01)
        self.send_data(0xe0)

        self.send_command(0x15) # Dual SPI mode
        self.send_data(0x00)

        self.send_command(self.TCON_SETTING)
        self.send_data(0x22)

        # self.send_command(self.VCOM_AND_DATA_INTERVAL_SETTING)
        # self.send_data(0x10)
        # self.send_data(0x07)

        # from GxEPD2
        self.send_command(self.VCOM_AND_DATA_INTERVAL_SETTING)
        self.send_data(0x29) # LUTKW, N2OCP: copy new to old
        self.send_data(0x07)

        print('Main init finished.')

        if partial:
            self.send_command(self.PANEL_SETTING)
            self.send_data(0x1f) # KW-3f  KWR-2F  BWROTP 0f  BWOTP 1f

            self.send_command(self.PLL_CONTROL)
            self.send_data(0x06) # 3C 50Hz
        else:
            self.send_command(self.PANEL_SETTING)
            self.send_data(0x1f) # full update LUT from OTP

        # All done, let's power on!
        print('Power on.')
        self.send_command(self.POWER_ON)
        self.wait_until_idle()
        print('Init complete.')
        # EPD hardware init end
        return 0

    def set_lut(self):
        raise NotImplementedError

    def set_frame_memory(self, image, x, y):
        raise NotImplementedError

    def clear_frame_memory(self, color):
        raise NotImplementedError

    def set_part_reg(self):
        '''
        Set ¿registers? for partial refresh
        '''

        print('Panel setting.')

        self.send_command(self.PANEL_SETTING)
        self.send_data(0x3f) # partial update LUT from registers

        print('Setting VCM_DC')

        self.send_command(self.VCM_DC_SETTING)
        # self.send_data(0x2C) # -2.3V same value as in OTP
        self.send_data(0x26) # -2.0V
        # self.send_data(0x1C) # -1.5V

        self.send_command(self.VCOM_AND_DATA_INTERVAL_SETTING)
        # self.send_data(0x39) # LUTBD, N2OCP: copy new to old
        # self.send_data(0x47)
        self.send_data(0x21) # 0x11: white border, 0x21: black border
        self.send_data(0x07)

        # Update LUTs

        print('LUT upload...', end='')

        self.send_command(0x20)  # vcom
        for count in range(0, 42):
            self.send_data(self.lut_vcom1[count])
        self.send_command(0x21)  # ww --
        for count in range(0, 42):
            self.send_data(self.lut_ww1[count])
        self.send_command(0x22)  # bw r
        for count in range(0, 42):
            self.send_data(self.lut_bw1[count])
        self.send_command(0x23)  # wb w
        for count in range(0, 42):
            self.send_data(self.lut_wb1[count])
        self.send_command(0x24)  # bb b
        for count in range(0, 42):
            self.send_data(self.lut_bb1[count])
        self.send_command(0x25) # bd, apparently
        for count in range(0, 42):
            self.send_data(self.lut_bd1[count])

        print('done')

    def display_full(self, frame_buffer):
        '''
        Displays the given frame buffer onto the e-paper screen
        '''

        if not frame_buffer:
            return

        if self.in_partial:
            print('Partial out.')
            self.send_command(self.PARTIAL_OUT)
            self.in_partial = False

        self.send_command(self.DATA_START_TRANSMISSION_1)
        for i in range(0, int(self.width * self.height / 8)):
            self.send_data(0x00)
        self.delay_ms(10)

        self.send_command(self.DATA_START_TRANSMISSION_2)
        for i in range(0, int(self.width * self.height / 8)):
            self.send_data(frame_buffer[i])
        self.delay_ms(10)

        self.send_command(self.DISPLAY_REFRESH)
        self.delay_ms(100)
        self.wait_until_idle()

    def set_memory_area(self, x_start, y_start, x_end, y_end):
        if not self.in_partial:

            print('Partial in.')
            self.set_part_reg()
            self.send_command(self.PARTIAL_IN)
            self.in_partial = True

        print('Partial Window: ({0}, {2}) to ({1}, {3})'
            .format(x_start, x_end, y_start, y_end))
        self.send_command(self.PARTIAL_WINDOW)

        print(x_start / 256)
        print(x_start % 256)
        print(x_end / 256)
        print(x_end % 256)

        print(y_start / 256)
        print(y_start % 256)
        print(y_end / 256)
        print(y_end % 256)

        self.send_data(int(x_start / 256))
        self.send_data(int(x_start % 256))
        self.send_data(int(x_end / 256))
        self.send_data(int(x_end % 256))

        self.send_data(int(y_start / 256))
        self.send_data(int(y_start % 256))
        self.send_data(int(y_end / 256))
        self.send_data(int(y_end % 256))

        # 01 - gates scan both inside and outside of partial window (default)
        self.send_data(0x01)

        self.delay_ms(10)
        print('Partial window set.')

    def set_frame_memory(self, image, x, y):
        print('Setting Frame Memory')
        if image is None or x < 0 or y < 0:
            return
        image_monocolor = image.convert('1')
        image_width, image_height = image_monocolor.size
        # x point must be the multiple of 8 or the last 3 bits will be ignored
        # x = x & 0xF8
        # image_width = image_width & 0xF8
        if x + image_width >= self.width:
            x_end = self.width - 1
        else:
            x_end = x + image_width - 1
        if y + image_height >= self.height:
            y_end = self.height - 1
        else:
            y_end = y + image_height - 1

        self.set_memory_area(x, y, x_end, y_end)

        print('Generating data...', end='')

        bytes_to_send = []

        # send the image data
        pixels = image_monocolor.load()
        byte_to_send = 0x00
        for j in range(0, y_end - y + 1):
            # 1 byte = 8 pixels, steps of i = 8
            for i in range(0, x_end - x + 1):
                # Set the bits for the column of pixels at the current position.
                if pixels[i, j] != 0:
                    byte_to_send |= 0x80 >> (i % 8)
                if i % 8 == 7:
                    # print('Send data: {}'.format(byte_to_send))
                    bytes_to_send.append(byte_to_send)
                    byte_to_send = 0x00
        print('done.')

        print('Sending data...', end='')
        self.send_command(self.DATA_START_TRANSMISSION_1)
        for b in bytes_to_send:
            self.send_data(~b)
        self.delay_ms(10)

        self.send_command(self.DATA_START_TRANSMISSION_2)
        for b in bytes_to_send:
            self.send_data(b)
        self.delay_ms(10)

        print('done.')

        print('Frame memory set')

    def display_frame(self):

        print('Refreshing screen.')

        # self.set_full_reg()
        self.send_command(self.DISPLAY_REFRESH)
        self.delay_ms(300)
        print('Waiting till idle.')
        self.wait_until_idle()

        print('Screen refreshed.')

    def display_partial(self, frame_buffer, x_start, y_start, x_end, y_end):
        '''
        Refresh a particular area on the screen
        '''

        if not frame_buffer:
            return

        if not self.in_partial:

            print('Partial in.')
            self.set_part_reg()
            self.send_command(self.PARTIAL_IN)
            self.in_partial = True

        print('Partial Window: ({0}, {2}) to ({1}, {3})'
            .format(x_start, x_end, y_start, y_end))
        self.send_command(self.PARTIAL_WINDOW)

        print(x_start / 256)
        print(x_start % 256)
        print(x_end / 256)
        print(x_end % 256 - 1)

        print(y_start / 256)
        print(y_start % 256)
        print(y_end / 256)
        print(y_end % 256 - 1)

        self.send_data(int(x_start / 256))
        self.send_data(int(x_start % 256))
        self.send_data(int(x_end / 256))
        self.send_data(int(x_end % 256 - 1))

        self.send_data(int(y_start / 256))
        self.send_data(int(y_start % 256))
        self.send_data(int(y_end / 256))
        self.send_data(int(y_end % 256 - 1))

        # 01 - gates scan both inside and outside of partial window (default)
        self.send_data(0x01)

        self.delay_ms(10)

        print('Sending data...', end='')

        self.send_command(self.DATA_START_TRANSMISSION_1)
        # for i in range(0, int(self.width * self.height / 8)):
            # # print(frame_buffer[i],'%d','0x10')
            # self.send_data(~frame_buffer[i])
        for i in frame_buffer:
            self.send_data(~i)
        self.delay_ms(10)

        self.send_command(self.DATA_START_TRANSMISSION_2)
        # for i in range(0, int(self.width * self.height / 8)):
            # # print(~frame_buffer[i],'%d','0x13')
            # self.send_data(frame_buffer[i])
        for i in frame_buffer:
            self.send_data(i)
        self.delay_ms(10)

        print('done.')

        # print('Exit partial mode')
        # self.send_command(self.PARTIAL_OUT)
        # self.in_partial = False

        print('Refresh screen.')

        # self.set_full_reg()
        self.send_command(self.DISPLAY_REFRESH)
        self.delay_ms(300)
        self.wait_until_idle()

        print('All done.')

    def draw(self, x, y, image):
        """Replace a particular area on the display with an image"""
        if self.partial_refresh:
            print('Drawing partial: ({}, {}).'.format(x, y))
            # self.display_partial(self.get_frame_buffer(image, allow_partial=True), x, y, x + image.width, x + image.height)
            self.set_frame_memory(image, x, y)
            self.display_frame()
        else:
            print('Drawing full via partial')
            self.set_frame_memory(image, x, y)
            #self.display_full(self.get_frame_buffer(image))
            self.display_frame()
        print('Drawing finished.')

    def sleep(self):
        '''
        Puts the panel into deep sleep mode
        '''

        print('Going to sleep.')

        self.send_command(self.POWER_OFF)
        self.wait_until_idle()

        self.send_command(self.DEEP_SLEEP)
        self.send_data(0xa5)

        print('Good night!')

    def reset(self):
        """
        Mirroring behaviour in reference implementation:
        https://github.com/waveshare/e-Paper/blob/702def06bcb75983c98b0f9d25d43c552c248eb0/RaspberryPi%26JetsonNano/python/lib/waveshare_epd/epd7in5_V2.py#L48-L54

        The earlier implementation of `reset` inherited from `WaveshareFull` did not work with some units
        (`init` hanged at `wait_until_idle` after the `POWER_ON` command was sent).

        A quick scan of the other implementations indicates that the reset varies across devices (it's unclear
        whether there is good reason for device specific differences or if the developer was just being inconsistent...)
        e.g. significantly different delay times:
        https://github.com/waveshare/e-Paper/blob/702def06bcb75983c98b0f9d25d43c552c248eb0/RaspberryPi%26JetsonNano/python/lib/waveshare_epd/epd1in54c.py#L46-L52
        """
        # Deliberately importing here to achieve same fail-on-use import behaviour as in `drivers_base.py`
        import RPi.GPIO as GPIO

        self.digital_write(self.RST_PIN, GPIO.HIGH)
        self.delay_ms(200)
        self.digital_write(self.RST_PIN, GPIO.LOW)
        self.delay_ms(2)
        self.digital_write(self.RST_PIN, GPIO.HIGH)
        self.delay_ms(200)

    def wait_until_idle(self):
        """
        Mirroring behaviour in reference implementation (i.e. differently to other implementations, we send command 0x71
        and poll without sleep):
        https://github.com/waveshare/e-Paper/blob/702def06bcb75983c98b0f9d25d43c552c248eb0/RaspberryPi%26JetsonNano/python/lib/waveshare_epd/epd7in5_V2.py#L68-L75
        """
        self.send_command(0x71)
        while self.digital_read(self.BUSY_PIN) == 0:  # 0: busy, 1: idle
            self.delay_ms(20)
            self.send_command(0x71)

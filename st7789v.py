# st7789v.py - MicroPython driver for ST7789V 240x320 LCD
# Compatible with DNESP32S3 (uses SPI + XL9555 for RST/BL control)

from machine import SPI, Pin
import framebuf
import time

# ST7789V Commands
ST7789_NOP        = 0x00
ST7789_SWRESET    = 0x01
ST7789_RDDID      = 0x04
ST7789_RDDST      = 0x09
ST7789_SLPIN      = 0x10
ST7789_SLPOUT     = 0x11
ST7789_PTLON      = 0x12
ST7789_NORON      = 0x13
ST7789_INVOFF     = 0x20
ST7789_INVON      = 0x21
ST7789_DISPOFF    = 0x28
ST7789_DISPON     = 0x29
ST7789_CASET      = 0x2A
ST7789_RASET      = 0x2B
ST7789_RAMWR      = 0x2C
ST7789_RAMRD      = 0x2E
ST7789_PTLAR      = 0x30
ST7789_VSCRDEF    = 0x33
ST7789_COLMOD     = 0x3A
ST7789_MADCTL     = 0x36
ST7789_VSCSAD     = 0x37
ST7789_WRDISBV    = 0x51
ST7789_WRCACE     = 0x55
ST7789_WRCABCMB   = 0x5E
ST7789_RDABC      = 0x68
ST7789_RDID1      = 0xDA
ST7789_RDID2      = 0xDB
ST7789_RDID3      = 0xDC

# Color definitions (RGB565)
COLOR_BLACK       = 0x0000
COLOR_WHITE       = 0xFFFF
COLOR_RED         = 0xF800
COLOR_GREEN       = 0x07E0
COLOR_BLUE        = 0x001F
COLOR_CYAN        = 0x07FF
COLOR_MAGENTA     = 0xF81F
COLOR_YELLOW      = 0xFFE0
COLOR_GRAY        = 0x8410

class ST7789V(framebuf.FrameBuffer):
    """ST7789V LCD driver for DNESP32S3 (240x320)"""

    def __init__(self, spi, dc, cs=None, width=240, height=320, rotation=0, xl9555=None):
        """
        Initialize ST7789V display.
        
        Args:
            spi: machine.SPI object (e.g., SPI(1))
            dc: Data/Command pin (machine.Pin)
            cs: Chip Select pin (optional, can be controlled by SPI)
            width: Display width (default 240)
            height: Display height (default 320)
            rotation: Display rotation (0, 1, 2, 3)
            xl9555: Optional XL9555 instance for RST/BL control (see note below)
        """
        self.width = width
        self.height = height
        self.spi = spi
        self.dc = dc
        self.cs = cs
        if self.cs:
            self.cs.init(self.cs.OUT, value=1)
        self.dc.init(self.dc.OUT, value=0)

        # Framebuffer setup
        self.buffer = bytearray(self.width * self.height * 2)
        super().__init__(self.buffer, self.width, self.height, framebuf.RGB565)

        # Hardware reset via XL9555 if provided
        if xl9555:
            # According to DNESP32S3 schematic:
            # SLCD_RST -> XL9555 IO1_2 (pin 10)
            # SLCD_PWR (backlight) -> XL9555 IO1_3 (pin 11)
            self._xl9555 = xl9555
            self._pin_rst = 10  # IO1_2
            self._pin_bl = 11   # IO1_3
            self._use_xl9555 = True
        else:
            self._use_xl9555 = False

        self.init_display(rotation)

    def _write_cmd(self, cmd):
        """Write command byte to display"""
        if self.cs:
            self.cs(0)
        self.dc(0)
        self.spi.write(bytes([cmd]))
        if self.cs:
            self.cs(1)

    def _write_data(self, data):
        """Write data bytes to display"""
        if self.cs:
            self.cs(0)
        self.dc(1)
        self.spi.write(data)
        if self.cs:
            self.cs(1)

    def _write_reg(self, reg, *data):
        """Write command followed by data"""
        self._write_cmd(reg)
        if data:
            self._write_data(bytes(data))

    def reset(self):
        """Hardware reset using XL9555 or external pin"""
        if self._use_xl9555:
            self._xl9555.write_pin(self._pin_rst, 0)
            time.sleep_ms(100)
            self._xl9555.write_pin(self._pin_rst, 1)
            time.sleep_ms(100)
        else:
            # If you have a direct RST pin, handle it here
            raise RuntimeError("RST control requires XL9555 on DNESP32S3")

    def set_backlight(self, on=True):
        """Control backlight via XL9555"""
        if self._use_xl9555:
            self._xl9555.write_pin(self._pin_bl, int(on))
        else:
            print("Warning: Backlight control not available without XL9555")

    def init_display(self, rotation=0):
        # 硬件复位（通过 XL9555）
        if self._use_xl9555:
            self._xl9555.write_pin(self._pin_rst, 0)
            time.sleep_ms(10)
            self._xl9555.write_pin(self._pin_rst, 1)
            time.sleep_ms(120)

        # 硬件复位...
        self._write_cmd(ST7789_SLPOUT); time.sleep_ms(120)
        self._write_reg(ST7789_COLMOD, 0x05)  # 16-bit RGB565
        self._write_cmd(ST7789_INVON)         # 需要 INVON
        time.sleep_ms(10)
        self.set_rotation(rotation)           # 此处 MADCTL=0x60（无BGR）
        self._write_cmd(ST7789_DISPON); time.sleep_ms(100)
        self.set_backlight(True)
        self.fill(COLOR_BLACK); self.show()

    def set_rotation(self, r):
        self.rotation = r % 4
        if self.rotation == 0:   
            madctl = 0x00  
            self.w = self.width
            self.h = self.height
        elif self.rotation == 1:   
            madctl = 0x60  
            self.w = self.height
            self.h = self.width
        elif self.rotation == 2:
            madctl = 0xC0
            self.w = self.width
            self.h = self.height
        elif self.rotation == 3:
            madctl = 0xA0
            self.w = self.height
            self.h = self.width
        self._write_reg(ST7789_MADCTL, madctl)

    def set_window(self, x, y, w, h):
        """Set GRAM writing window"""
        x_start = x
        x_end = x + w - 1
        y_start = y
        y_end = y + h - 1

        self._write_reg(ST7789_CASET, (x_start >> 8) & 0xFF, x_start & 0xFF,
                                      (x_end >> 8) & 0xFF, x_end & 0xFF)
        self._write_reg(ST7789_RASET, (y_start >> 8) & 0xFF, y_start & 0xFF,
                                      (y_end >> 8) & 0xFF, y_end & 0xFF)
        self._write_cmd(ST7789_RAMWR)


    def show(self):
        """
        刷新屏幕（关键：小端序 → 大端序转换）
        使用高效原地转换，零额外内存开销
        """
        buf = self.buffer
        n = len(buf)
        
        # 1. 设置窗口
        self.set_window(0, 0, self.width, self.height)
        
        # 2. 高效字节序转换 + 发送（单次遍历）
        self.cs(0)
        self.dc(1)
        
        # 分块发送提升SPI效率（每块512字节 = 256像素）
        CHUNK = 512
        for i in range(0, n, CHUNK):
            end = min(i + CHUNK, n)
            # 创建临时块（避免频繁SPI调用）
            chunk = bytearray(end - i)
            # 转换字节序：小端 → 大端
            for j in range(0, end - i, 2):
                chunk[j] = buf[i + j + 1]   # 高字节
                chunk[j + 1] = buf[i + j]   # 低字节
            self.spi.write(chunk)
        
        self.cs(1)

    def pixel(self, x, y, color):
        """Draw single pixel (override for clipping)"""
        if 0 <= x < self.width and 0 <= y < self.height:
            super().pixel(x, y, color)

    def fill_rect(self, x, y, w, h, color):
        """Fast fill rectangle"""
        if w <= 0 or h <= 0:
            return
        end_x = x + w
        end_y = y + h
        if x < 0:
            x = 0
        if y < 0:
            y = 0
        if end_x > self.width:
            end_x = self.width
        if end_y > self.height:
            end_y = self.height
        super().fill_rect(x, y, end_x - x, end_y - y, color)

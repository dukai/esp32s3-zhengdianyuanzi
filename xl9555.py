from machine import I2C

class XL9555:
    """XL9555 16位I2C GPIO扩展芯片驱动"""
    
    # 寄存器地址
    REG_INPUT_PORT0 = 0x00
    REG_INPUT_PORT1 = 0x01
    REG_OUTPUT_PORT0 = 0x02
    REG_OUTPUT_PORT1 = 0x03
    REG_POLARITY_INV0 = 0x04
    REG_POLARITY_INV1 = 0x05
    REG_CONFIG_PORT0 = 0x06
    REG_CONFIG_PORT1 = 0x07
    
    # 设备默认地址 (A0-A2接地)
    DEFAULT_ADDRESS = 0x20
    
    # 引脚定义 (基于正点原子DNESP32S3开发板)
    # P0端口 (0-7)
    P00 = 0   # AP  INT 
    P01 = 1   # QMA INT 
    P02 = 2   # SPK EN 
    P03 = 3   # BEEP 
    P04 = 4   # OV PWDN 
    P05 = 5   # OV RESET 
    P06 = 6   # GBC LED 
    P07 = 7   # GBC KEY 
    
    # P1端口 (8-15)
    P10 = 8   # LCD BL
    P11 = 9   # CT RST 
    P12 = 10  # SLCD RST 
    P13 = 11  # SLCD PWR
    P14 = 12  # KEY3 
    P15 = 13  # KEY2 
    P16 = 14  # KEY1 
    P17 = 15  # KEY0 
    
    def __init__(self, i2c, address=DEFAULT_ADDRESS):
        """
        初始化XL9555芯片
        
        Args:
            i2c: machine.I2C对象
            address: I2C设备地址 (默认0x20)
        """
        self.i2c = i2c
        self.address = address
        self._output_cache = [0x00, 0x00]  # 缓存输出状态
        self._config_cache = [0xFF, 0xFF]  # 缓存配置状态
        
        # 根据硬件设计配置IO方向:
        # P00、P01、P14-P17 为输入 (1)
        # 其他引脚为输出 (0)
        # 配置值: P0=0x03 (0b00000011), P1=0xF0 (0b11110000)
        self.config(0x03, 0xF0)
        
        # 初始化输出引脚为高电平 (关闭蜂鸣器、喇叭等)
        self.set_output(0xFFFF)
    
    def _read_reg(self, reg):
        """读取单个寄存器"""
        self.i2c.writeto(self.address, bytes([reg]))
        return self.i2c.readfrom(self.address, 1)[0]
    
    def _write_reg(self, reg, value):
        """写入单个寄存器"""
        self.i2c.writeto(self.address, bytes([reg, value]))
    
    def config(self, config0, config1):
        """
        配置IO方向寄存器
        
        Args:
            config0: Port0配置 (0=输出, 1=输入)
            config1: Port1配置 (0=输出, 1=输入)
        """
        self._config_cache[0] = config0
        self._config_cache[1] = config1
        self._write_reg(self.REG_CONFIG_PORT0, config0)
        self._write_reg(self.REG_CONFIG_PORT1, config1)
    
    def get_input(self):
        """
        读取所有输入引脚状态
        
        Returns:
            16位整数，低8位为P0，高8位为P1
        """
        port0 = self._read_reg(self.REG_INPUT_PORT0)
        port1 = self._read_reg(self.REG_INPUT_PORT1)
        return (port1 << 8) | port0
    
    def get_input_port(self, port):
        """
        读取指定端口的输入状态
        
        Args:
            port: 0 (P0) 或 1 (P1)
            
        Returns:
            8位整数
        """
        if port not in (0, 1):
            raise ValueError("Port must be 0 or 1")
        return self._read_reg(self.REG_INPUT_PORT0 + port)
    
    def set_output(self, value):
        """
        设置所有输出引脚状态
        
        Args:
            value: 16位整数，低8位控制P0，高8位控制P1
                   1=高电平，0=低电平
        """
        port0 = value & 0xFF
        port1 = (value >> 8) & 0xFF
        self._output_cache[0] = port0
        self._output_cache[1] = port1
        self._write_reg(self.REG_OUTPUT_PORT0, port0)
        self._write_reg(self.REG_OUTPUT_PORT1, port1)
    
    def set_output_port(self, port, value):
        """
        设置指定端口的输出状态
        
        Args:
            port: 0 (P0) 或 1 (P1)
            value: 8位整数
        """
        if port not in (0, 1):
            raise ValueError("Port must be 0 or 1")
        self._output_cache[port] = value
        self._write_reg(self.REG_OUTPUT_PORT0 + port, value)
    
    def get_output(self):
        """
        获取当前输出缓存值
        
        Returns:
            16位整数
        """
        return (self._output_cache[1] << 8) | self._output_cache[0]
    
    def write_pin(self, pin, value):
        """
        设置单个引脚输出电平
        
        Args:
            pin: 引脚号 0-15 (P00=0, P01=1, ..., P07=7, P10=8, ..., P17=15)
            value: 0=低电平，1=高电平
        """
        if not 0 <= pin <= 15:
            raise ValueError("Pin must be between 0 and 15")
        
        port = pin // 8
        bit = pin % 8
        
        if value:
            self._output_cache[port] |= (1 << bit)
        else:
            self._output_cache[port] &= ~(1 << bit)
        
        self._write_reg(self.REG_OUTPUT_PORT0 + port, self._output_cache[port])
    
    def read_pin(self, pin):
        """
        读取单个引脚状态
        
        Args:
            pin: 引脚号 0-15
            
        Returns:
            0 或 1
        """
        if not 0 <= pin <= 15:
            raise ValueError("Pin must be between 0 and 15")
        
        port = pin // 8
        bit = pin % 8
        
        # 检查该引脚是否配置为输入
        if self._config_cache[port] & (1 << bit):
            # 从输入寄存器读取
            value = self._read_reg(self.REG_INPUT_PORT0 + port)
        else:
            # 从输出缓存读取
            value = self._output_cache[port]
        
        return (value >> bit) & 1
    
    def toggle_pin(self, pin):
        """
        翻转单个引脚输出电平
        
        Args:
            pin: 引脚号 0-15
        """
        current = self.read_pin(pin)
        self.write_pin(pin, not current)
    
    def set_backlight(self, value):
        """
        控制SPI LCD背光 (P02)
        
        Args:
            value: True=开启背光, False=关闭背光
        """
        self.write_pin(self.P02, value)
    
    def set_lcd_power(self, value):
        """
        控制SPI LCD电源 (P03)
        
        Args:
            value: True=上电, False=断电
        """
        self.write_pin(self.P03, value)
    
    def beep(self, enable):
        """
        控制蜂鸣器 (P04)
        
        Args:
            enable: True=开启蜂鸣器, False=关闭蜂鸣器
        """
        self.write_pin(self.P04, enable)
    
    def key_scan(self):
        """
        扫描按键状态 (KEY0-KEY3)
        
        Returns:
            按下的按键编号: 
                0 = KEY0 (P11)
                1 = KEY1 (P10)
                2 = KEY2 (P01)
                3 = KEY3 (P00)
                -1 = 无按键按下
        """
        # 读取所有输入
        inputs = self.get_input()
        
        # 检查按键 (低电平有效)
        if not (inputs & (1 << self.P11)):  # KEY0
            return 0
        elif not (inputs & (1 << self.P10)):  # KEY1
            return 1
        elif not (inputs & (1 << self.P01)):  # KEY2
            return 2
        elif not (inputs & (1 << self.P00)):  # KEY3
            return 3
        else:
            return -1

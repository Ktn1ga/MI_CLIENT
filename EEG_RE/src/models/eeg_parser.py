import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal
import logging

class EEGParser(QObject):
    """脑电数据解析器，用于解析接收到的数据"""
    
    # 信号定义
    data_parsed = pyqtSignal(dict)  # 数据解析完成信号
    
    def __init__(self):
        super().__init__()
        self.buffer = bytearray()  # 数据缓冲区
        self.frame_header = bytes([0xA0, 0xFF])  # 帧头 A0 FF
        self.frame_footer = bytes([0xC0])  # 帧尾 C0
        self.channel_count = 8  # 脑电通道数
        self.label_count = 2  # 标签通道数
        self.bytes_per_value = 3  # 每个值占用的字节数
        
        # 添加调试标志
        self.debug_mode = False
        
    def process_data(self, data):
        """处理接收到的数据"""
        # 将接收到的数据添加到缓冲区
        self.buffer.extend(data)
        
        # 处理缓冲区中的所有完整帧
        frames_processed = 0
        while True:
            # 查找帧头
            header_index = self.buffer.find(self.frame_header)
            if header_index == -1:
                # 没有找到帧头，但不应该清空缓冲区，因为可能只是部分帧
                # 只保留最后几个字节，以防帧头被分割
                if len(self.buffer) > 10:
                    self.buffer = self.buffer[-10:]
                break
            
            # 如果帧头不在开始位置，删除帧头之前的数据
            if header_index > 0:
                if self.debug_mode:
                    logging.debug(f"删除帧头前的 {header_index} 字节数据")
                del self.buffer[:header_index]
                header_index = 0
            
            # 检查缓冲区是否足够长，包含至少一个完整帧
            expected_length = len(self.frame_header) + (self.channel_count + self.label_count) * self.bytes_per_value + len(self.frame_footer)
            if len(self.buffer) < expected_length:
                # 缓冲区不够长，等待更多数据
                if self.debug_mode:
                    logging.debug(f"缓冲区长度不足: {len(self.buffer)} < {expected_length}，等待更多数据")
                break
            
            # 查找帧尾
            footer_index = self.buffer.find(self.frame_footer, header_index + len(self.frame_header))
            if footer_index == -1:
                # 没有找到帧尾，保留缓冲区等待更多数据
                # 但如果缓冲区过长，可能是数据错误，应该清理
                if len(self.buffer) > expected_length * 2:
                    if self.debug_mode:
                        logging.debug(f"缓冲区过长且未找到帧尾，清理缓冲区")
                    # 保留最后一个预期帧长度的数据
                    self.buffer = self.buffer[-expected_length:]
                break
            
            # 检查帧长度是否合理
            frame_length = footer_index + len(self.frame_footer) - header_index
            if frame_length != expected_length:
                logging.warning(f"帧长度不正确: {frame_length} != {expected_length}，跳过此帧")
                # 删除到帧头的数据，继续查找下一帧
                del self.buffer[:header_index + len(self.frame_header)]
                continue
            
            # 提取完整的帧
            frame = self.buffer[header_index:footer_index + len(self.frame_footer)]
            
            # 解析帧
            parsed_data = self._parse_frame(frame)
            if parsed_data:
                self.data_parsed.emit(parsed_data)
                frames_processed += 1
                if self.debug_mode:
                    logging.debug(f"成功解析第 {frames_processed} 帧数据")
            
            # 从缓冲区中删除已处理的帧
            del self.buffer[:footer_index + len(self.frame_footer)]
        
        return frames_processed
    
    def _parse_frame(self, frame):
        """解析单个数据帧"""
        # 检查帧长度是否正确
        expected_length = len(self.frame_header) + (self.channel_count + self.label_count) * self.bytes_per_value + len(self.frame_footer)
        if len(frame) != expected_length:
            logging.warning(f"帧长度不正确: {len(frame)} != {expected_length}")
            return None
        
        # 检查帧头和帧尾
        if frame[:len(self.frame_header)] != self.frame_header or frame[-len(self.frame_footer):] != self.frame_footer:
            logging.warning("帧头或帧尾不正确")
            return None
        
        # 解析数据部分
        data_part = frame[len(self.frame_header):-len(self.frame_footer)]
        
        # 解析通道数据
        channels = []
        labels = []
        
        for i in range(self.channel_count):
            start_idx = i * self.bytes_per_value
            channel_bytes = data_part[start_idx:start_idx + self.bytes_per_value]
            channel_value = self._bytes_to_int(channel_bytes)
            channels.append(channel_value)
            
            if self.debug_mode and i == 0:  # 只打印第一个通道的调试信息
                hex_bytes = ' '.join([f'{b:02X}' for b in channel_bytes])
                logging.debug(f"通道 {i+1} 原始字节: {hex_bytes}, 解析值: {channel_value}")
        
        # 解析标签数据
        for i in range(self.label_count):
            start_idx = (self.channel_count + i) * self.bytes_per_value
            label_bytes = data_part[start_idx:start_idx + self.bytes_per_value]
            label_value = self._bytes_to_int(label_bytes)
            labels.append(label_value)
        
        return {
            'channels': channels,
            'labels': labels,
            'timestamp': np.datetime64('now')
        }
    
    def _bytes_to_int(self, byte_data):
        """将字节数据转换为整数值"""
        # 确保数据是24位有符号整数，小端序
        if len(byte_data) != 3:
            logging.warning(f"字节数据长度不正确: {len(byte_data)} != 3")
            return 0
        
        try:
            # 从小端序字节中提取值
            # 发送端使用的是小端序: [低位, 中位, 高位]
            value = byte_data[0] | (byte_data[1] << 8) | (byte_data[2] << 16)
            
            # 处理符号位（检查最高位是否为1）
            if value & 0x800000:  # 检查第24位（最高位）是否为1
                # 负数，进行符号扩展
                value = value - 0x1000000  # 减去2^24
            
            # 检查数值是否在合理范围内
            if abs(value) > 8388607:  # 2^23 - 1，24位有符号整数的最大值
                logging.warning(f"解析到异常大的值: {value}，可能是数据错误")

            ref_voltage = 1000.0
            value = value * ref_voltage /8388607
            return value
        except Exception as e:
            logging.error(f"字节转整数出错: {str(e)}")
            return 0
    
    def set_debug_mode(self, enabled):
        """设置调试模式"""
        self.debug_mode = enabled
        if enabled:
            logging.info("EEG解析器已启用调试模式")
        else:
            logging.info("EEG解析器已禁用调试模式")
    
    def clear_buffer(self):
        """清空数据缓冲区"""
        self.buffer.clear() 
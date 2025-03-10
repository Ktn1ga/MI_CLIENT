import numpy as np
from collections import deque
from PyQt5.QtCore import QObject, pyqtSignal
import logging

class DataBuffer(QObject):
    """数据缓冲器，用于存储和管理脑电数据"""
    
    # 信号定义
    data_updated = pyqtSignal(dict)  # 数据更新信号
    
    def __init__(self, max_points=1000):
        super().__init__()
        self.max_points = max_points
        self.channel_count = 8
        self.label_count = 2
        
        # 为每个通道创建数据缓冲区
        self.channel_buffers = [deque(maxlen=max_points) for _ in range(self.channel_count)]
        self.label_buffers = [deque(maxlen=max_points) for _ in range(self.label_count)]
        self.time_buffer = deque(maxlen=max_points)
        
        # 当前采样率
        self.sampling_rate = 250  # 默认采样率
        
        # 当前时间点
        self.current_time = 0.0
        
    def add_data(self, data):
        """添加新的数据点"""
        if 'channels' not in data or 'labels' not in data:
            return
            
        channels = data['channels']
        labels = data['labels']
        
        # 检查数据长度是否正确
        if len(channels) != self.channel_count or len(labels) != self.label_count:
            logging.warning(f"数据长度不匹配: 通道={len(channels)}/{self.channel_count}, 标签={len(labels)}/{self.label_count}")
            # 填充或截断数据以匹配预期长度
            channels = channels[:self.channel_count] + [0] * max(0, self.channel_count - len(channels))
            labels = labels[:self.label_count] + [0] * max(0, self.label_count - len(labels))
        
        # 检查数据是否包含异常值
        for i, value in enumerate(channels):
            if abs(value) > 1000000:  # 设置一个合理的阈值
                logging.warning(f"通道 {i+1} 检测到异常值: {value}，将被替换为0")
                channels[i] = 0
                
        for i, value in enumerate(labels):
            if abs(value) > 1000:  # 标签值通常较小
                logging.warning(f"标签 {i+1} 检测到异常值: {value}，将被替换为0")
                labels[i] = 0
        
        # 更新时间
        time_step = 1.0 / self.sampling_rate
        self.current_time += time_step
        self.time_buffer.append(self.current_time)
        
        # 添加通道数据
        for i, value in enumerate(channels):
            if i < self.channel_count:
                self.channel_buffers[i].append(value)
                
        # 添加标签数据
        for i, value in enumerate(labels):
            if i < self.label_count:
                self.label_buffers[i].append(value)
                
        # 发送数据更新信号
        self.data_updated.emit(self.get_data())
        
    def get_data(self):
        """获取当前缓冲区中的所有数据"""
        # 转换为numpy数组以便绘图
        channels_data = [np.array(buffer) for buffer in self.channel_buffers]
        labels_data = [np.array(buffer) for buffer in self.label_buffers]
        time_data = np.array(self.time_buffer)
        
        return {
            'channels': channels_data,
            'labels': labels_data,
            'time': time_data
        }
        
    def get_channel_data(self, channel_index):
        """获取指定通道的数据"""
        if 0 <= channel_index < self.channel_count:
            return np.array(self.channel_buffers[channel_index])
        return np.array([])
        
    def get_label_data(self, label_index):
        """获取指定标签的数据"""
        if 0 <= label_index < self.label_count:
            return np.array(self.label_buffers[label_index])
        return np.array([])
        
    def get_time_data(self):
        """获取时间数据"""
        return np.array(self.time_buffer)
        
    def clear(self):
        """清空所有缓冲区"""
        for buffer in self.channel_buffers:
            buffer.clear()
        for buffer in self.label_buffers:
            buffer.clear()
        self.time_buffer.clear()
        self.current_time = 0.0
        
    def set_sampling_rate(self, rate):
        """设置采样率"""
        if rate > 0:
            self.sampling_rate = rate
            
    def set_max_points(self, max_points):
        """设置最大点数"""
        if max_points > 0 and max_points != self.max_points:
            self.max_points = max_points
            
            # 更新所有缓冲区的最大长度
            new_channel_buffers = []
            for buffer in self.channel_buffers:
                buffer_list = list(buffer)
                new_buffer = deque(buffer_list[-max_points:] if len(buffer_list) > max_points else buffer_list, maxlen=max_points)
                new_channel_buffers.append(new_buffer)
            self.channel_buffers = new_channel_buffers
                
            new_label_buffers = []
            for buffer in self.label_buffers:
                buffer_list = list(buffer)
                new_buffer = deque(buffer_list[-max_points:] if len(buffer_list) > max_points else buffer_list, maxlen=max_points)
                new_label_buffers.append(new_buffer)
            self.label_buffers = new_label_buffers
                
            time_list = list(self.time_buffer)
            self.time_buffer = deque(time_list[-max_points:] if len(time_list) > max_points else time_list, maxlen=max_points) 
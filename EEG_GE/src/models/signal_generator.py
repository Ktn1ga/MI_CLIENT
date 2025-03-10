#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
信号生成模型 - 负责生成脑电信号数据
"""

import numpy as np
import pandas as pd
import time
from PyQt5.QtCore import QObject, pyqtSignal, QThread
import threading

class SignalGenerator(QObject):
    """信号生成器基类"""
    
    # 信号定义
    data_generated = pyqtSignal(np.ndarray)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, sampling_rate=250):
        super().__init__()
        self.sampling_rate = sampling_rate  # 采样率（Hz）
        self.is_running = False
        self.thread = None
        self._generate_thread = None  # 实际生成数据的线程
    
    def start(self):
        """启动信号生成"""
        if self.is_running:
            return
        
        self.is_running = True
        
        # 确保之前的线程已经完全停止
        if self.thread is not None:
            if self.thread.isRunning():
                self.thread.quit()
                self.thread.wait()
            self.thread.deleteLater()
        
        # 创建新的生成线程
        self._generate_thread = threading.Thread(target=self._generate_loop)
        self._generate_thread.daemon = True
        self._generate_thread.start()
    
    def stop(self):
        """停止信号生成"""
        self.is_running = False
        
        # 等待生成线程结束
        if self._generate_thread and self._generate_thread.is_alive():
            self._generate_thread.join(2.0)
    
    def _generate_loop(self):
        """信号生成循环，由子类实现"""
        raise NotImplementedError("子类必须实现此方法")


class SineWaveGenerator(SignalGenerator):
    """正弦波信号生成器"""
    
    def __init__(self, sampling_rate=250):
        super().__init__(sampling_rate)
        # 初始化8个通道的参数
        self.channels = 8
        self.frequencies = [10.0] * self.channels  # 默认频率（Hz）
        self.amplitudes = [100.0] * self.channels  # 默认幅值（μV）
        self.time_counter = 0
    
    def set_channel_params(self, channel, frequency, amplitude):
        """设置通道参数
        
        Args:
            channel: 通道索引（0-7）
            frequency: 频率（Hz）
            amplitude: 幅值（μV）
        """
        if 0 <= channel < self.channels:
            self.frequencies[channel] = max(0.1, min(100.0, frequency))
            self.amplitudes[channel] = max(0, min(1000.0, amplitude))
    
    def _generate_loop(self):
        """生成复合正弦波信号"""
        interval = 1.0 / self.sampling_rate
        
        while self.is_running:
            start_time = time.time()
            
            try:
                # 生成时间点
                t = self.time_counter / self.sampling_rate
                
                # 生成8通道数据
                data = np.zeros(self.channels)
                for ch in range(self.channels):
                    f = self.frequencies[ch]
                    A = self.amplitudes[ch]
                    
                    # 复合正弦波: y(t) = A*sin(2πft) + A/3*sin(6πft) + A/5*sin(10πft)
                    data[ch] = (A * np.sin(2 * np.pi * f * t) + 
                               A/3 * np.sin(6 * np.pi * f * t) + 
                               A/5 * np.sin(10 * np.pi * f * t))
                
                # 发送生成的数据
                self.data_generated.emit(data)
                
                # 更新计数器
                self.time_counter += 1
            except Exception as e:
                self.error_occurred.emit(f"生成信号错误: {str(e)}")
                time.sleep(interval)
                continue
            
            # 控制生成速率
            elapsed = time.time() - start_time
            sleep_time = max(0, interval - elapsed)
            time.sleep(sleep_time)


class FileReplayGenerator(SignalGenerator):
    """文件回放信号生成器"""
    
    def __init__(self, sampling_rate=250):
        super().__init__(sampling_rate)
        self.file_path = None
        self.data = None
        self.current_index = 0
        self.playback_speed = 1.0  # 回放速度倍率
        self.channels = 8  # 输出通道数
    
    def load_file(self, file_path):
        """加载CSV文件
        
        Args:
            file_path: CSV文件路径
        
        Returns:
            bool: 是否加载成功
        """
        try:
            # 读取CSV文件
            self.data = pd.read_csv(file_path)
            
            # 验证数据格式
            if self.data.shape[1] < 8:  # 至少需要8个通道
                self.error_occurred.emit(f"CSV文件格式错误：通道数不足，需要至少8个通道，当前只有{self.data.shape[1]}个")
                return False
            
            # 检查数据是否为空
            if len(self.data) == 0:
                self.error_occurred.emit("CSV文件不包含任何数据")
                return False
            
            self.file_path = file_path
            self.current_index = 0
            return True
        except Exception as e:
            self.error_occurred.emit(f"加载文件失败：{str(e)}")
            return False
    
    def set_playback_speed(self, speed):
        """设置回放速度
        
        Args:
            speed: 回放速度倍率（0.5-5.0）
        """
        self.playback_speed = max(0.5, min(5.0, speed))
    
    def _generate_loop(self):
        """从文件回放数据"""
        if self.data is None or len(self.data) == 0:
            self.error_occurred.emit("没有加载数据文件或文件为空")
            self.is_running = False
            return
        
        interval = 1.0 / (self.sampling_rate * self.playback_speed)
        
        while self.is_running:
            start_time = time.time()
            
            try:
                if self.current_index >= len(self.data):
                    self.current_index = 0  # 循环播放
                
                # 获取当前行数据（取前8个通道）
                row_data = self.data.iloc[self.current_index].values[:self.channels]
                
                # 如果通道数不足8个，补零
                if len(row_data) < self.channels:
                    row_data = np.pad(row_data, (0, self.channels - len(row_data)))
                
                # 检查数据是否包含NaN值
                if np.isnan(row_data).any():
                    # 将NaN值替换为0
                    row_data = np.nan_to_num(row_data)
                
                # 发送生成的数据
                self.data_generated.emit(row_data)
                
                # 更新索引
                self.current_index += 1
            except Exception as e:
                self.error_occurred.emit(f"数据回放错误：{str(e)}")
                time.sleep(interval)  # 出错时也要保持循环频率
                continue
            
            # 控制生成速率
            elapsed = time.time() - start_time
            sleep_time = max(0, interval - elapsed)
            time.sleep(sleep_time) 
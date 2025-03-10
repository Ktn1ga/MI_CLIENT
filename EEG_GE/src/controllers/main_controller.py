#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
主控制器 - 负责协调模型和视图
"""

import os
import time
import datetime
import pandas as pd
from PyQt5.QtCore import QObject, QTimer
import numpy as np

from src.models.signal_generator import SineWaveGenerator, FileReplayGenerator
from src.models.tcp_server import TcpServer
from src.views.main_window import MainWindow

class MainController(QObject):
    """主控制器类"""
    
    def __init__(self):
        super().__init__()
        
        # 创建模型
        self.sine_generator = SineWaveGenerator()
        self.file_generator = FileReplayGenerator()
        self.tcp_server = TcpServer()
        
        # 当前活动的生成器
        self.active_generator = self.sine_generator
        
        # 创建视图
        self.main_window = MainWindow()
        
        # 连接信号
        self._connect_signals()
        
        # 状态变量
        self.is_running = False
        self.current_mode = 0  # 0:正弦波，1:文件回放
        self.bytes_sent = 0
        self.last_bytes_sent = 0
        self.send_rate = 0
        
        # 创建定时器（用于更新状态）
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start(1000)  # 每秒更新一次
    
    def _connect_signals(self):
        """连接信号和槽"""
        # 视图 -> 控制器
        self.main_window.sine_params_changed.connect(self._on_sine_params_changed)
        self.main_window.sampling_rate_changed.connect(self._on_sampling_rate_changed)
        self.main_window.server_start_requested.connect(self._on_server_start)
        self.main_window.server_stop_requested.connect(self._on_server_stop)
        self.main_window.server_params_changed.connect(self._on_server_params_changed)
        self.main_window.file_load_requested.connect(self._on_file_load)
        self.main_window.playback_speed_changed.connect(self._on_playback_speed_changed)
        self.main_window.mode_changed.connect(self._on_mode_changed)
        
        # 模型 -> 控制器
        self.sine_generator.data_generated.connect(self._on_data_generated)
        self.file_generator.data_generated.connect(self._on_data_generated)
        self.sine_generator.error_occurred.connect(self._on_error)
        self.file_generator.error_occurred.connect(self._on_error)
        self.tcp_server.error_occurred.connect(self._on_error)
        self.tcp_server.client_connected.connect(self._on_client_connected)
        self.tcp_server.client_disconnected.connect(self._on_client_disconnected)
        self.tcp_server.data_sent.connect(self._on_data_sent)
    
    def show_main_window(self):
        """显示主窗口"""
        self.main_window.show()
    
    def _on_sine_params_changed(self, channel, frequency, amplitude):
        """正弦波参数改变事件处理"""
        self.sine_generator.set_channel_params(channel, frequency, amplitude)
        self._log(f"通道{channel+1}参数已更新：频率={frequency}Hz，幅值={amplitude}μV")
    
    def _on_sampling_rate_changed(self, rate):
        """采样率改变事件处理"""
        if self.is_running:
            self._log("服务运行时无法更改采样率")
            return
        
        self.sine_generator.sampling_rate = rate
        self.file_generator.sampling_rate = rate
        self._log(f"采样率已更新：{rate}Hz")
    
    def _on_server_params_changed(self, host, port, max_clients):
        """服务器参数改变事件处理"""
        if self.is_running:
            self._log("服务运行时无法更改服务器参数")
            return
        
        self.tcp_server.set_host(host)
        self.tcp_server.set_port(port)
        self.tcp_server.set_max_clients(max_clients)
        self._log(f"服务器参数已更新：主机={host}，端口={port}，最大连接数={max_clients}")
    
    def _on_file_load(self, file_path):
        """文件加载事件处理"""
        if self.is_running and self.current_mode == 1:
            self._log("服务运行时无法加载文件")
            return
        
        success = self.file_generator.load_file(file_path)
        
        if success:
            # 读取文件信息
            try:
                df = pd.read_csv(file_path)
                rows = len(df)
                cols = df.shape[1]
                
                file_info = f"文件名：{os.path.basename(file_path)}\n"
                file_info += f"路径：{file_path}\n"
                file_info += f"行数：{rows}\n"
                file_info += f"通道数：{cols}\n"
                
                # 显示文件信息
                self.main_window.set_file_info(file_info)
                
                self._log(f"成功加载文件：{file_path}")
            except Exception as e:
                self._log(f"读取文件信息失败：{str(e)}")
        else:
            self.main_window.set_file_info("文件加载失败")
    
    def _on_playback_speed_changed(self, speed):
        """回放速度改变事件处理"""
        self.file_generator.set_playback_speed(speed)
        self._log(f"回放速度已更新：{speed}x")
    
    def _on_mode_changed(self, mode):
        """模式改变事件处理"""
        if self.is_running:
            self._log("服务运行时无法切换模式")
            # 恢复UI状态
            self.main_window._on_mode_changed(self.current_mode)
            return
        
        self.current_mode = mode
        if mode == 0:
            self.active_generator = self.sine_generator
            self._log("已切换到正弦波生成模式")
        else:
            self.active_generator = self.file_generator
            self._log("已切换到文件回放模式")
    
    def _on_server_start(self):
        """服务器启动事件处理"""
        if self.is_running:
            return
        
        try:
            # 启动TCP服务器
            if not self.tcp_server.start():
                self.main_window.show_error("启动服务器失败")
                self.main_window._on_stop_clicked()  # 恢复UI状态
                return
            
            # 启动信号生成器
            self.active_generator.start()
            
            self.is_running = True
            self._log("服务已启动")
            
            # 更新状态
            self._update_status()
        except Exception as e:
            self.main_window.show_error(f"启动服务失败: {str(e)}")
            self.main_window._on_stop_clicked()  # 恢复UI状态
            self._log(f"启动服务出错: {str(e)}")
    
    def _on_server_stop(self):
        """服务器停止事件处理"""
        if not self.is_running:
            return
        
        try:
            # 停止信号生成器
            self.sine_generator.stop()
            self.file_generator.stop()
            
            # 停止TCP服务器
            self.tcp_server.stop()
            
            self.is_running = False
            self._log("服务已停止")
            
            # 更新状态
            self._update_status()
        except Exception as e:
            self.main_window.show_error(f"停止服务失败: {str(e)}")
            self._log(f"停止服务出错: {str(e)}")
    
    def _on_data_generated(self, data):
        """数据生成事件处理"""
        if self.is_running:
            # 检查数据是否有效
            if data is None or len(data) == 0:
                return
            
            # 检查数据是否包含NaN值
            if np.isnan(data).any():
                # 将NaN值替换为0
                data = np.nan_to_num(data)
            
            # 发送数据
            self.tcp_server.send_data(data)
            
            # 更新波形图
            self.main_window.update_plot(data)
    
    def _on_client_connected(self, ip, port):
        """客户端连接事件处理"""
        self._log(f"客户端已连接：{ip}:{port}")
        self._update_status()
    
    def _on_client_disconnected(self, ip, port):
        """客户端断开事件处理"""
        self._log(f"客户端已断开：{ip}:{port}")
        self._update_status()
    
    def _on_data_sent(self, bytes_count):
        """数据发送事件处理"""
        self.bytes_sent += bytes_count
    
    def _on_error(self, message):
        """错误事件处理"""
        self._log(f"错误：{message}")
        self.main_window.show_error(message)
    
    def _update_status(self):
        """更新状态信息"""
        if self.is_running:
            # 计算发送速率
            current_time = time.time()
            self.send_rate = self.bytes_sent - self.last_bytes_sent
            self.last_bytes_sent = self.bytes_sent
            
            # 更新服务器状态
            client_count = self.tcp_server.get_client_count()
            self.main_window.set_server_status(True, client_count, self.send_rate)
        else:
            self.main_window.set_server_status(False)
    
    def _log(self, message):
        """添加日志消息"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        self.main_window.add_log(log_message) 
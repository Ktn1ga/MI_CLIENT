#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
主窗口视图 - 负责用户界面展示
"""

import os
import numpy as np
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QTabWidget, QGroupBox, QLabel, QLineEdit, 
                            QPushButton, QSpinBox, QDoubleSpinBox, QComboBox,
                            QFileDialog, QTextEdit, QGridLayout, QCheckBox,
                            QSlider, QStatusBar, QMessageBox)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon
import pyqtgraph as pg

class MainWindow(QMainWindow):
    """主窗口类"""
    
    # 信号定义
    sine_params_changed = pyqtSignal(int, float, float)  # 正弦波参数改变信号（通道，频率，幅值）
    sampling_rate_changed = pyqtSignal(int)  # 采样率改变信号
    server_start_requested = pyqtSignal()  # 服务器启动请求信号
    server_stop_requested = pyqtSignal()  # 服务器停止请求信号
    server_params_changed = pyqtSignal(str, int, int)  # 服务器参数改变信号（主机，端口，最大连接数）
    file_load_requested = pyqtSignal(str)  # 文件加载请求信号
    playback_speed_changed = pyqtSignal(float)  # 回放速度改变信号
    mode_changed = pyqtSignal(int)  # 模式改变信号（0:正弦波，1:文件回放）
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("脑电信号发生器系统")
        self.resize(1200, 800)
        
        # 初始化UI
        self._init_ui()
        
        # 设置状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("就绪")
        
        # 初始化定时器（用于更新状态）
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start(1000)  # 每秒更新一次
        
        # 数据缓冲（用于绘图）
        self.data_buffer = np.zeros((8, 1000))  # 8通道，1000个采样点
        self.buffer_index = 0
    
    def _init_ui(self):
        """初始化用户界面"""
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 创建选项卡
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)
        
        # 创建信号生成选项卡
        signal_tab = QWidget()
        tab_widget.addTab(signal_tab, "信号生成")
        
        # 创建网络设置选项卡
        network_tab = QWidget()
        tab_widget.addTab(network_tab, "网络设置")
        
        # 创建日志选项卡
        log_tab = QWidget()
        tab_widget.addTab(log_tab, "系统日志")
        
        # 设置信号生成选项卡
        self._setup_signal_tab(signal_tab)
        
        # 设置网络设置选项卡
        self._setup_network_tab(network_tab)
        
        # 设置日志选项卡
        self._setup_log_tab(log_tab)
        
        # 创建控制按钮
        control_layout = QHBoxLayout()
        main_layout.addLayout(control_layout)
        
        self.start_button = QPushButton("启动服务")
        self.start_button.setFixedHeight(40)
        self.start_button.clicked.connect(self._on_start_clicked)
        control_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("停止服务")
        self.stop_button.setFixedHeight(40)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._on_stop_clicked)
        control_layout.addWidget(self.stop_button)
    
    def _setup_signal_tab(self, tab):
        """设置信号生成选项卡"""
        layout = QVBoxLayout(tab)
        
        # 模式选择
        mode_group = QGroupBox("信号生成模式")
        mode_layout = QHBoxLayout(mode_group)
        
        self.sine_mode_radio = QCheckBox("模式1：正弦波生成")
        self.sine_mode_radio.setChecked(True)
        self.sine_mode_radio.clicked.connect(lambda: self._on_mode_changed(0))
        mode_layout.addWidget(self.sine_mode_radio)
        
        self.file_mode_radio = QCheckBox("模式2：文件回放")
        self.file_mode_radio.clicked.connect(lambda: self._on_mode_changed(1))
        mode_layout.addWidget(self.file_mode_radio)
        
        layout.addWidget(mode_group)
        
        # 创建堆叠部件
        self.signal_stack = QTabWidget()
        layout.addWidget(self.signal_stack)
        
        # 正弦波设置页
        sine_page = QWidget()
        self._setup_sine_page(sine_page)
        self.signal_stack.addTab(sine_page, "正弦波参数设置")
        
        # 文件回放设置页
        file_page = QWidget()
        self._setup_file_page(file_page)
        self.signal_stack.addTab(file_page, "文件回放设置")
        
        # 波形显示区域
        wave_group = QGroupBox("实时波形显示")
        wave_layout = QVBoxLayout(wave_group)
        
        # 创建绘图部件
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.setLabel('left', '幅值', units='μV')
        self.plot_widget.setLabel('bottom', '时间', units='s')
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setYRange(-1000, 1000)
        wave_layout.addWidget(self.plot_widget)
        
        # 创建曲线对象
        self.curves = []
        colors = ['r', 'g', 'b', 'c', 'm', 'y', (100, 100, 100), (200, 100, 0)]
        for i in range(8):
            curve = self.plot_widget.plot(pen=pg.mkPen(color=colors[i], width=1), name=f"通道{i+1}")
            self.curves.append(curve)
        
        layout.addWidget(wave_group)
        
        # 采样率设置
        rate_group = QGroupBox("采样率设置")
        rate_layout = QHBoxLayout(rate_group)
        
        rate_layout.addWidget(QLabel("采样率:"))
        
        self.rate_spinbox = QSpinBox()
        self.rate_spinbox.setRange(10, 1000)
        self.rate_spinbox.setValue(250)
        self.rate_spinbox.setSingleStep(10)
        self.rate_spinbox.setSuffix(" Hz")
        self.rate_spinbox.valueChanged.connect(self._on_sampling_rate_changed)
        rate_layout.addWidget(self.rate_spinbox)
        
        layout.addWidget(rate_group)
    
    def _setup_sine_page(self, page):
        """设置正弦波参数页面"""
        layout = QVBoxLayout(page)
        
        # 通道参数表格
        param_group = QGroupBox("通道参数设置")
        param_layout = QGridLayout(param_group)
        
        # 表头
        param_layout.addWidget(QLabel("通道"), 0, 0)
        param_layout.addWidget(QLabel("频率 (Hz)"), 0, 1)
        param_layout.addWidget(QLabel("幅值 (μV)"), 0, 2)
        
        # 通道参数控件
        self.freq_spinboxes = []
        self.amp_spinboxes = []
        
        for i in range(8):
            # 通道标签
            param_layout.addWidget(QLabel(f"通道 {i+1}"), i+1, 0)
            
            # 频率微调框
            freq_spinbox = QDoubleSpinBox()
            freq_spinbox.setRange(0.1, 100.0)
            freq_spinbox.setValue(10.0)
            freq_spinbox.setSingleStep(0.1)
            freq_spinbox.setDecimals(1)
            freq_spinbox.setSuffix(" Hz")
            freq_spinbox.valueChanged.connect(lambda v, ch=i: self._on_sine_params_changed(ch))
            param_layout.addWidget(freq_spinbox, i+1, 1)
            self.freq_spinboxes.append(freq_spinbox)
            
            # 幅值微调框
            amp_spinbox = QDoubleSpinBox()
            amp_spinbox.setRange(0, 1000.0)
            amp_spinbox.setValue(100.0)
            amp_spinbox.setSingleStep(1.0)
            amp_spinbox.setDecimals(1)
            amp_spinbox.setSuffix(" μV")
            amp_spinbox.valueChanged.connect(lambda v, ch=i: self._on_sine_params_changed(ch))
            param_layout.addWidget(amp_spinbox, i+1, 2)
            self.amp_spinboxes.append(amp_spinbox)
        
        layout.addWidget(param_group)
    
    def _setup_file_page(self, page):
        """设置文件回放参数页面"""
        layout = QVBoxLayout(page)
        
        # 文件选择
        file_group = QGroupBox("数据文件设置")
        file_layout = QVBoxLayout(file_group)
        
        file_path_layout = QHBoxLayout()
        file_path_layout.addWidget(QLabel("文件路径:"))
        
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setReadOnly(True)
        file_path_layout.addWidget(self.file_path_edit)
        
        self.browse_button = QPushButton("浏览...")
        self.browse_button.clicked.connect(self._on_browse_clicked)
        file_path_layout.addWidget(self.browse_button)
        
        file_layout.addLayout(file_path_layout)
        
        # 回放速度
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("回放速度:"))
        
        self.speed_spinbox = QDoubleSpinBox()
        self.speed_spinbox.setRange(0.5, 5.0)
        self.speed_spinbox.setValue(1.0)
        self.speed_spinbox.setSingleStep(0.1)
        self.speed_spinbox.setDecimals(1)
        self.speed_spinbox.setSuffix("x")
        self.speed_spinbox.valueChanged.connect(self._on_playback_speed_changed)
        speed_layout.addWidget(self.speed_spinbox)
        
        file_layout.addLayout(speed_layout)
        
        layout.addWidget(file_group)
        
        # 文件信息
        info_group = QGroupBox("文件信息")
        info_layout = QVBoxLayout(info_group)
        
        self.file_info_text = QTextEdit()
        self.file_info_text.setReadOnly(True)
        info_layout.addWidget(self.file_info_text)
        
        layout.addWidget(info_group)
    
    def _setup_network_tab(self, tab):
        """设置网络设置选项卡"""
        layout = QVBoxLayout(tab)
        
        # TCP服务器设置
        server_group = QGroupBox("TCP服务器设置")
        server_layout = QGridLayout(server_group)
        
        server_layout.addWidget(QLabel("主机地址:"), 0, 0)
        self.host_edit = QLineEdit("127.0.0.1")
        self.host_edit.textChanged.connect(self._on_server_params_changed)
        server_layout.addWidget(self.host_edit, 0, 1)
        
        server_layout.addWidget(QLabel("端口:"), 1, 0)
        self.port_spinbox = QSpinBox()
        self.port_spinbox.setRange(1024, 65535)
        self.port_spinbox.setValue(50012)
        self.port_spinbox.valueChanged.connect(self._on_server_params_changed)
        server_layout.addWidget(self.port_spinbox, 1, 1)
        
        server_layout.addWidget(QLabel("最大连接数:"), 2, 0)
        self.max_clients_spinbox = QSpinBox()
        self.max_clients_spinbox.setRange(1, 20)
        self.max_clients_spinbox.setValue(5)
        self.max_clients_spinbox.valueChanged.connect(self._on_server_params_changed)
        server_layout.addWidget(self.max_clients_spinbox, 2, 1)
        
        layout.addWidget(server_group)
        
        # 连接状态
        status_group = QGroupBox("连接状态")
        status_layout = QVBoxLayout(status_group)
        
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        status_layout.addWidget(self.status_text)
        
        layout.addWidget(status_group)
    
    def _setup_log_tab(self, tab):
        """设置日志选项卡"""
        layout = QVBoxLayout(tab)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        clear_button = QPushButton("清除日志")
        clear_button.clicked.connect(self._on_clear_log_clicked)
        layout.addWidget(clear_button)
    
    def _on_sine_params_changed(self, channel):
        """正弦波参数改变事件处理"""
        frequency = self.freq_spinboxes[channel].value()
        amplitude = self.amp_spinboxes[channel].value()
        self.sine_params_changed.emit(channel, frequency, amplitude)
    
    def _on_sampling_rate_changed(self):
        """采样率改变事件处理"""
        rate = self.rate_spinbox.value()
        self.sampling_rate_changed.emit(rate)
    
    def _on_server_params_changed(self):
        """服务器参数改变事件处理"""
        host = self.host_edit.text()
        port = self.port_spinbox.value()
        max_clients = self.max_clients_spinbox.value()
        self.server_params_changed.emit(host, port, max_clients)
    
    def _on_browse_clicked(self):
        """浏览文件按钮点击事件处理"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择CSV文件", "", "CSV文件 (*.csv);;所有文件 (*.*)"
        )
        
        if file_path:
            self.file_path_edit.setText(file_path)
            self.file_load_requested.emit(file_path)
    
    def _on_playback_speed_changed(self):
        """回放速度改变事件处理"""
        speed = self.speed_spinbox.value()
        self.playback_speed_changed.emit(speed)
    
    def _on_mode_changed(self, mode):
        """模式改变事件处理"""
        if mode == 0:  # 正弦波模式
            self.sine_mode_radio.setChecked(True)
            self.file_mode_radio.setChecked(False)
        else:  # 文件回放模式
            self.sine_mode_radio.setChecked(False)
            self.file_mode_radio.setChecked(True)
        
        self.signal_stack.setCurrentIndex(mode)
        self.mode_changed.emit(mode)
    
    def _on_start_clicked(self):
        """启动按钮点击事件处理"""
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.server_start_requested.emit()
    
    def _on_stop_clicked(self):
        """停止按钮点击事件处理"""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.server_stop_requested.emit()
    
    def _on_clear_log_clicked(self):
        """清除日志按钮点击事件处理"""
        self.log_text.clear()
    
    def _update_status(self):
        """更新状态信息"""
        # 由控制器调用更新
        pass
    
    def update_plot(self, data):
        """更新波形图
        
        Args:
            data: 8通道数据，numpy数组
        """
        # 检查数据是否有效
        if data is None or len(data) == 0:
            return
        
        # 检查数据是否包含NaN值
        if np.isnan(data).any():
            # 将NaN值替换为0
            data = np.nan_to_num(data)
        
        # 更新数据缓冲区
        self.data_buffer[:, self.buffer_index] = data
        self.buffer_index = (self.buffer_index + 1) % self.data_buffer.shape[1]
        
        # 重新排列数据以便绘图
        plot_data = np.roll(self.data_buffer, -self.buffer_index, axis=1)
        
        # 更新曲线
        x = np.arange(self.data_buffer.shape[1]) / self.rate_spinbox.value()
        for i in range(8):
            self.curves[i].setData(x, plot_data[i])
    
    def set_server_status(self, running, client_count=0, send_rate=0):
        """设置服务器状态
        
        Args:
            running: 服务器是否运行
            client_count: 客户端连接数
            send_rate: 发送速率（字节/秒）
        """
        status = "运行中" if running else "已停止"
        self.status_text.setText(f"服务器状态: {status}\n"
                                f"客户端连接数: {client_count}\n"
                                f"发送速率: {send_rate} 字节/秒")
        
        if running:
            self.statusBar.showMessage(f"服务器运行中 - {client_count}个客户端连接")
        else:
            self.statusBar.showMessage("服务器已停止")
    
    def set_file_info(self, info):
        """设置文件信息
        
        Args:
            info: 文件信息字符串
        """
        self.file_info_text.setText(info)
    
    def add_log(self, message):
        """添加日志消息
        
        Args:
            message: 日志消息
        """
        self.log_text.append(message)
    
    def show_error(self, message):
        """显示错误消息
        
        Args:
            message: 错误消息
        """
        QMessageBox.critical(self, "错误", message)
    
    def show_info(self, message):
        """显示信息消息
        
        Args:
            message: 信息消息
        """
        QMessageBox.information(self, "信息", message) 
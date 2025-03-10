import os
import time
import pyqtgraph as pg
import numpy as np
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
    QLabel, QLineEdit, QSpinBox, QPushButton, QTabWidget, 
    QTextEdit, QCheckBox, QGridLayout, QSplitter, QMessageBox,
    QComboBox, QDoubleSpinBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
import logging

class MainWindow(QMainWindow):
    """主窗口类"""
    
    # 信号定义
    tcp_connect_requested = pyqtSignal(str, int)  # TCP连接请求信号
    tcp_disconnect_requested = pyqtSignal()  # TCP断开连接请求信号
    ws_server_start_requested = pyqtSignal(str, int)  # WebSocket服务器启动请求信号
    ws_server_stop_requested = pyqtSignal()  # WebSocket服务器停止请求信号
    tcp_params_changed = pyqtSignal(str, int)  # TCP参数改变信号
    ws_params_changed = pyqtSignal(str, int)  # WebSocket参数改变信号
    clear_data_requested = pyqtSignal()  # 清空数据请求信号
    
    def __init__(self):
        super().__init__()
        
        # 设置窗口标题和大小
        self.setWindowTitle("脑电信号接收器")
        self.resize(1000, 800)
        
        # 初始化UI
        self._init_ui()
        
        # 创建状态更新定时器
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start(1000)  # 每秒更新一次状态
        
        # 数据接收速率统计
        self.data_rate = 0
        self.data_count = 0
        self.last_data_time = time.time()
        
    def _init_ui(self):
        """初始化UI"""
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 创建分割器
        splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(splitter)
        
        # 创建上部分（波形显示和控制）
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        splitter.addWidget(top_widget)
        
        # 创建波形显示组
        wave_group = QGroupBox("脑电波形显示")
        wave_layout = QVBoxLayout(wave_group)
        
        # 创建波形显示控件
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
            
        # 创建标签曲线对象
        self.label_curves = []
        for i in range(2):
            curve = self.plot_widget.plot(pen=pg.mkPen(color=(50, 50, 50), width=1, style=Qt.DashLine), name=f"标签{i+1}")
            self.label_curves.append(curve)
        
        # 添加波形控制面板
        wave_control_layout = QHBoxLayout()
        wave_layout.addLayout(wave_control_layout)
        
        # 通道选择
        wave_control_layout.addWidget(QLabel("通道:"))
        self.channel_combo = QComboBox()
        self.channel_combo.addItems(["全部"] + [f"通道 {i+1}" for i in range(8)])
        self.channel_combo.currentIndexChanged.connect(self._on_channel_changed)
        wave_control_layout.addWidget(self.channel_combo)
        
        # 显示标签复选框
        self.show_labels_checkbox = QCheckBox("显示标签")
        self.show_labels_checkbox.setChecked(True)
        self.show_labels_checkbox.stateChanged.connect(self._on_show_labels_changed)
        wave_control_layout.addWidget(self.show_labels_checkbox)
        
        # 自动缩放复选框
        self.auto_scale_checkbox = QCheckBox("自动缩放")
        self.auto_scale_checkbox.setChecked(False)
        self.auto_scale_checkbox.stateChanged.connect(self._on_auto_scale_changed)
        wave_control_layout.addWidget(self.auto_scale_checkbox)
        
        # Y轴跟随复选框
        self.y_follow_checkbox = QCheckBox("Y轴跟随")
        self.y_follow_checkbox.setChecked(False)
        self.y_follow_checkbox.setEnabled(not self.auto_scale_checkbox.isChecked())
        wave_control_layout.addWidget(self.y_follow_checkbox)
        
        # 添加Y轴范围控制（仅在非自动缩放模式下可用）
        self.y_range_widget = QWidget()
        y_range_layout = QHBoxLayout(self.y_range_widget)
        y_range_layout.setContentsMargins(0, 0, 0, 0)
        
        y_range_layout.addWidget(QLabel("Y轴范围:"))
        self.y_min_spinbox = QDoubleSpinBox()
        self.y_min_spinbox.setRange(-10000, 0)
        self.y_min_spinbox.setValue(-1000)
        self.y_min_spinbox.setSingleStep(100)
        self.y_min_spinbox.valueChanged.connect(self._on_y_range_changed)
        y_range_layout.addWidget(self.y_min_spinbox)
        
        y_range_layout.addWidget(QLabel("至"))
        self.y_max_spinbox = QDoubleSpinBox()
        self.y_max_spinbox.setRange(0, 10000)
        self.y_max_spinbox.setValue(1000)
        self.y_max_spinbox.setSingleStep(100)
        self.y_max_spinbox.valueChanged.connect(self._on_y_range_changed)
        y_range_layout.addWidget(self.y_max_spinbox)
        
        wave_control_layout.addWidget(self.y_range_widget)
        self.y_range_widget.setVisible(not self.auto_scale_checkbox.isChecked())
        
        # 添加时间窗口控制
        wave_control_layout.addWidget(QLabel("时间窗口(秒):"))
        self.time_window_spinbox = QDoubleSpinBox()
        self.time_window_spinbox.setRange(1, 60)
        self.time_window_spinbox.setValue(10)
        self.time_window_spinbox.setSingleStep(1)
        self.time_window_spinbox.valueChanged.connect(self._on_time_window_changed)
        wave_control_layout.addWidget(self.time_window_spinbox)
        
        # 清空数据按钮
        self.clear_data_button = QPushButton("清空数据")
        self.clear_data_button.clicked.connect(self._on_clear_data_clicked)
        wave_control_layout.addWidget(self.clear_data_button)
            
        top_layout.addWidget(wave_group)
        
        # 创建下部分（选项卡）
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        splitter.addWidget(bottom_widget)
        
        # 创建选项卡
        tab_widget = QTabWidget()
        bottom_layout.addWidget(tab_widget)
        
        # 创建连接选项卡
        connection_tab = QWidget()
        self._setup_connection_tab(connection_tab)
        tab_widget.addTab(connection_tab, "连接设置")
        
        # 创建WebSocket选项卡
        websocket_tab = QWidget()
        self._setup_websocket_tab(websocket_tab)
        tab_widget.addTab(websocket_tab, "WebSocket")
        
        # 创建日志选项卡
        log_tab = QWidget()
        self._setup_log_tab(log_tab)
        tab_widget.addTab(log_tab, "日志")
        
        # 设置分割器初始大小
        splitter.setSizes([600, 200])
        
        # 创建状态栏
        self.statusBar().showMessage("就绪")
        
        # 创建TCP状态标签
        self.tcp_status_label = QLabel("TCP: 未连接")
        self.statusBar().addPermanentWidget(self.tcp_status_label)
        
        # 创建WebSocket状态标签
        self.ws_status_label = QLabel("WebSocket: 未连接")
        self.statusBar().addPermanentWidget(self.ws_status_label)
        
        # 创建数据速率标签
        self.data_rate_label = QLabel("数据速率: 0 帧/秒")
        self.statusBar().addPermanentWidget(self.data_rate_label)
        
    def _setup_connection_tab(self, tab):
        """设置连接选项卡"""
        layout = QVBoxLayout(tab)
        
        # TCP连接设置
        tcp_group = QGroupBox("TCP连接设置")
        tcp_layout = QGridLayout(tcp_group)
        
        # 服务器地址
        tcp_layout.addWidget(QLabel("服务器地址:"), 0, 0)
        self.host_edit = QLineEdit("127.0.0.1")
        tcp_layout.addWidget(self.host_edit, 0, 1)
        
        # 服务器端口
        tcp_layout.addWidget(QLabel("服务器端口:"), 1, 0)
        self.port_spinbox = QSpinBox()
        self.port_spinbox.setRange(1, 65535)
        self.port_spinbox.setValue(50012)
        tcp_layout.addWidget(self.port_spinbox, 1, 1)
        
        # 自动重连设置
        tcp_layout.addWidget(QLabel("自动重连:"), 2, 0)
        self.auto_reconnect_checkbox = QCheckBox()
        self.auto_reconnect_checkbox.setChecked(True)
        tcp_layout.addWidget(self.auto_reconnect_checkbox, 2, 1)
        
        # 重连间隔
        tcp_layout.addWidget(QLabel("重连间隔(秒):"), 3, 0)
        self.reconnect_interval_spinbox = QSpinBox()
        self.reconnect_interval_spinbox.setRange(1, 60)
        self.reconnect_interval_spinbox.setValue(5)
        tcp_layout.addWidget(self.reconnect_interval_spinbox, 3, 1)
        
        # 调试模式
        tcp_layout.addWidget(QLabel("调试模式:"), 4, 0)
        self.debug_mode_checkbox = QCheckBox()
        self.debug_mode_checkbox.setChecked(False)
        self.debug_mode_checkbox.stateChanged.connect(self._on_debug_mode_changed)
        tcp_layout.addWidget(self.debug_mode_checkbox, 4, 1)
        
        # 连接按钮
        self.connect_button = QPushButton("连接")
        self.connect_button.clicked.connect(self._on_connect_clicked)
        tcp_layout.addWidget(self.connect_button, 5, 0)
        
        # 断开连接按钮
        self.disconnect_button = QPushButton("断开")
        self.disconnect_button.setEnabled(False)
        self.disconnect_button.clicked.connect(self._on_disconnect_clicked)
        tcp_layout.addWidget(self.disconnect_button, 5, 1)
        
        layout.addWidget(tcp_group)
        
        # 显示设置
        display_group = QGroupBox("显示设置")
        display_layout = QGridLayout(display_group)
        
        # 通道选择
        display_layout.addWidget(QLabel("显示通道:"), 0, 0)
        self.channel_combo = QComboBox()
        self.channel_combo.addItem("全部通道")
        for i in range(8):
            self.channel_combo.addItem(f"通道 {i+1}")
        self.channel_combo.currentIndexChanged.connect(self._on_channel_changed)
        display_layout.addWidget(self.channel_combo, 0, 1)
        
        # 显示标签
        self.show_labels_checkbox = QCheckBox("显示标签")
        self.show_labels_checkbox.setChecked(True)
        self.show_labels_checkbox.stateChanged.connect(self._on_show_labels_changed)
        display_layout.addWidget(self.show_labels_checkbox, 1, 0)
        
        # 自动缩放
        self.auto_scale_checkbox = QCheckBox("自动缩放")
        self.auto_scale_checkbox.setChecked(False)
        display_layout.addWidget(self.auto_scale_checkbox, 1, 1)
        
        # 清空数据按钮
        self.clear_button = QPushButton("清空数据")
        self.clear_button.clicked.connect(self._on_clear_data_clicked)
        display_layout.addWidget(self.clear_button, 2, 0, 1, 2)
        
        layout.addWidget(display_group)
        
        # 添加弹性空间
        layout.addStretch()
        
    def _setup_websocket_tab(self, tab):
        """设置WebSocket选项卡"""
        layout = QVBoxLayout(tab)
        
        # WebSocket客户端设置
        ws_group = QGroupBox("WebSocket客户端设置")
        ws_layout = QGridLayout(ws_group)
        
        # 服务器地址
        ws_layout.addWidget(QLabel("服务器地址:"), 0, 0)
        self.ws_host_edit = QLineEdit("127.0.0.1")
        ws_layout.addWidget(self.ws_host_edit, 0, 1)
        
        # 服务器端口
        ws_layout.addWidget(QLabel("服务器端口:"), 1, 0)
        self.ws_port_spinbox = QSpinBox()
        self.ws_port_spinbox.setRange(1, 65535)
        self.ws_port_spinbox.setValue(8765)
        ws_layout.addWidget(self.ws_port_spinbox, 1, 1)
        
        # 连接按钮
        self.ws_start_button = QPushButton("连接")
        self.ws_start_button.clicked.connect(self._on_ws_start_clicked)
        ws_layout.addWidget(self.ws_start_button, 2, 0)
        
        # 断开连接按钮
        self.ws_stop_button = QPushButton("断开连接")
        self.ws_stop_button.clicked.connect(self._on_ws_stop_clicked)
        self.ws_stop_button.setEnabled(False)
        ws_layout.addWidget(self.ws_stop_button, 2, 1)
        
        layout.addWidget(ws_group)
        
        # WebSocket数据信息
        data_group = QGroupBox("数据信息")
        data_layout = QVBoxLayout(data_group)
        
        self.ws_data_text = QTextEdit()
        self.ws_data_text.setReadOnly(True)
        data_layout.addWidget(self.ws_data_text)
        
        layout.addWidget(data_group)
        
    def _setup_log_tab(self, tab):
        """设置日志选项卡"""
        layout = QVBoxLayout(tab)
        
        # 日志显示
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        # 清空日志按钮
        clear_log_button = QPushButton("清空日志")
        clear_log_button.clicked.connect(self._on_clear_log_clicked)
        layout.addWidget(clear_log_button)
        
    def _on_connect_clicked(self):
        """连接按钮点击事件"""
        host = self.host_edit.text().strip()
        port = self.port_spinbox.value()
        
        # 更新UI状态
        self.connect_button.setEnabled(False)
        self.host_edit.setEnabled(False)
        self.port_spinbox.setEnabled(False)
        
        # 添加连接中的状态提示
        self.tcp_status_label.setText("连接中...")
        self.tcp_status_label.setStyleSheet("color: orange;")
        
        # 发送连接请求信号
        self.tcp_connect_requested.emit(host, port)
        
    def _on_disconnect_clicked(self):
        """断开连接按钮点击事件"""
        # 发送断开连接请求信号
        self.tcp_disconnect_requested.emit()
        
    def _on_ws_start_clicked(self):
        """WebSocket连接按钮点击回调"""
        # 获取主机和端口
        host = self.ws_host_edit.text() or "127.0.0.1"
        port = self.ws_port_spinbox.value() or 8765
        
        # 禁用连接按钮，启用断开连接按钮
        self.ws_start_button.setEnabled(False)
        self.ws_stop_button.setEnabled(True)
        
        # 发送连接请求信号
        self.ws_server_start_requested.emit(host, port)
        
        # 发送参数改变信号
        self.ws_params_changed.emit(host, port)
        
    def _on_ws_stop_clicked(self):
        """断开连接按钮点击事件"""
        # 发送断开连接请求信号
        self.ws_server_stop_requested.emit()
        
    def _on_clear_log_clicked(self):
        """清空日志按钮点击事件"""
        self.log_text.clear()
        
    def _on_clear_data_clicked(self):
        """清空数据按钮点击事件"""
        self.clear_data_requested.emit()
        
    def _on_channel_changed(self, index):
        """通道选择改变回调"""
        # 更新图表
        data = {
            'channels': [np.array(buffer) for buffer in self.channel_buffers] if hasattr(self, 'channel_buffers') else [],
            'labels': [np.array(buffer) for buffer in self.label_buffers] if hasattr(self, 'label_buffers') else [],
            'time': np.array(self.time_buffer) if hasattr(self, 'time_buffer') else np.array([])
        }
        self.update_plot(data)
        
    def _on_show_labels_changed(self, state):
        """显示标签复选框状态改变事件"""
        for curve in self.label_curves:
            curve.show() if state == Qt.Checked else curve.hide()
            
    def _on_auto_scale_changed(self, state):
        """自动缩放复选框状态改变事件"""
        is_auto_scale = state == Qt.Checked
        self.y_range_widget.setVisible(not is_auto_scale)
        self.y_follow_checkbox.setEnabled(not is_auto_scale)
        
        # 更新图表
        data = {
            'channels': [np.array(buffer) for buffer in self.channel_buffers] if hasattr(self, 'channel_buffers') else [],
            'labels': [np.array(buffer) for buffer in self.label_buffers] if hasattr(self, 'label_buffers') else [],
            'time': np.array(self.time_buffer) if hasattr(self, 'time_buffer') else np.array([])
        }
        self.update_plot(data)
        
    def _on_y_range_changed(self):
        """Y轴范围改变回调"""
        if not self.auto_scale_checkbox.isChecked():
            y_min = self.y_min_spinbox.value()
            y_max = self.y_max_spinbox.value()
            if y_min < y_max:
                self.plot_widget.setYRange(y_min, y_max)
            else:
                # 如果最小值大于等于最大值，调整最大值
                self.y_max_spinbox.setValue(y_min + 100)
    
    def _on_time_window_changed(self):
        """时间窗口改变回调"""
        # 更新图表
        data = {
            'channels': [np.array(buffer) for buffer in self.channel_buffers] if hasattr(self, 'channel_buffers') else [],
            'labels': [np.array(buffer) for buffer in self.label_buffers] if hasattr(self, 'label_buffers') else [],
            'time': np.array(self.time_buffer) if hasattr(self, 'time_buffer') else np.array([])
        }
        self.update_plot(data)
        
    def _on_debug_mode_changed(self, state):
        """调试模式复选框状态改变事件"""
        # 发送信号给控制器
        debug_enabled = state == Qt.Checked
        # 这里需要通过控制器来设置调试模式
        # 由于没有直接的信号，我们需要在日志中记录状态变化
        self.add_log(f"调试模式已{'启用' if debug_enabled else '禁用'}")
        
        # 在下一个版本中，可以添加一个专门的信号来处理这个事件
        # 现在我们通过一个临时方法来处理
        from PyQt5.QtCore import QMetaObject, Qt
        QMetaObject.invokeMethod(self, "_debug_mode_changed_internal", 
                                Qt.QueuedConnection, 
                                Qt.Q_ARG(bool, debug_enabled))
    
    def _debug_mode_changed_internal(self, enabled):
        """内部方法，用于将调试模式状态传递给控制器"""
        # 这个方法将在事件循环中被调用，此时控制器应该已经创建
        # 并且已经连接到视图
        for child in self.children():
            if hasattr(child, 'set_debug_mode'):
                child.set_debug_mode(enabled)
                return
        
    def _update_status(self):
        """更新状态信息"""
        # 更新数据速率
        current_time = time.time()
        elapsed = current_time - self.last_data_time
        if elapsed >= 1.0:
            self.data_rate = self.data_count / elapsed
            self.data_count = 0
            self.last_data_time = current_time
            self.data_rate_label.setText(f"数据速率: {self.data_rate:.1f} 帧/秒")
            
    def update_plot(self, data):
        """更新波形图"""
        if not data:
            return
            
        try:
            channels = data.get('channels', [])
            labels = data.get('labels', [])
            time_data = data.get('time', np.array([]))
            
            if len(time_data) == 0:
                return
            
            # 获取时间窗口设置
            time_window = self.time_window_spinbox.value()
            
            # 计算时间轴范围
            current_time = time_data[-1] if len(time_data) > 0 else 0
            x_min = max(0, current_time - time_window)
            x_max = current_time
            
            # 设置X轴范围以实现时间轴对齐
            self.plot_widget.setXRange(x_min, x_max)
                
            # 检查当前选择的通道
            selected_channel = self.channel_combo.currentIndex() - 1  # -1表示全部通道
            
            # 计算当前可见数据的Y轴范围（用于Y轴跟随功能）
            visible_y_min = float('inf')
            visible_y_max = float('-inf')
            
            # 更新通道曲线
            for i, channel_data in enumerate(channels):
                if i < len(self.curves):
                    # 如果选择了特定通道，只显示该通道
                    if selected_channel == -1 or selected_channel == i:
                        if len(channel_data) > 0:  # 确保有数据
                            self.curves[i].setData(time_data, channel_data)
                            self.curves[i].show()
                            
                            # 计算可见部分的数据范围
                            if self.y_follow_checkbox.isChecked() and not self.auto_scale_checkbox.isChecked():
                                visible_indices = np.where((time_data >= x_min) & (time_data <= x_max))[0]
                                if len(visible_indices) > 0:
                                    visible_data = channel_data[visible_indices]
                                    if len(visible_data) > 0:
                                        channel_min = np.min(visible_data)
                                        channel_max = np.max(visible_data)
                                        visible_y_min = min(visible_y_min, channel_min)
                                        visible_y_max = max(visible_y_max, channel_max)
                        else:
                            self.curves[i].hide()
                    else:
                        self.curves[i].hide()
                    
            # 更新标签曲线
            show_labels = self.show_labels_checkbox.isChecked()
            for i, label_data in enumerate(labels):
                if i < len(self.label_curves):
                    if show_labels and len(label_data) > 0:
                        # 将标签值缩放到可见范围
                        scaled_data = label_data * 100  # 缩放因子
                        self.label_curves[i].setData(time_data, scaled_data)
                        self.label_curves[i].show()
                    else:
                        self.label_curves[i].hide()
            
            # Y轴范围处理
            if self.auto_scale_checkbox.isChecked():
                # 自动缩放Y轴
                self.plot_widget.enableAutoRange(axis='y')
            elif self.y_follow_checkbox.isChecked() and visible_y_min != float('inf') and visible_y_max != float('-inf'):
                # Y轴跟随模式 - 使用可见数据的范围，并添加10%的边距
                y_range = visible_y_max - visible_y_min
                padding = max(y_range * 0.1, 10)  # 至少10μV的边距
                self.plot_widget.setYRange(visible_y_min - padding, visible_y_max + padding)
                self.plot_widget.disableAutoRange(axis='y')
            else:
                # 使用用户设置的Y轴范围
                y_min = self.y_min_spinbox.value()
                y_max = self.y_max_spinbox.value()
                self.plot_widget.setYRange(y_min, y_max)
                self.plot_widget.disableAutoRange(axis='y')
                
            # 保存当前数据缓冲区的引用，用于通道切换时更新
            self.channel_buffers = channels
            self.label_buffers = labels
            self.time_buffer = time_data
                
        except Exception as e:
            logging.error(f"更新波形图时出错: {str(e)}")
            # 不在UI上显示此错误，避免频繁弹窗
            
    def clear_plot(self):
        """清空波形图"""
        for curve in self.curves:
            curve.setData([], [])
        for curve in self.label_curves:
            curve.setData([], [])
            
    def set_tcp_status(self, connected):
        """设置TCP连接状态"""
        if connected:
            self.connect_button.setEnabled(False)
            self.disconnect_button.setEnabled(True)
            self.host_edit.setEnabled(False)
            self.port_spinbox.setEnabled(False)
            self.tcp_status_label.setText("已连接")
            self.tcp_status_label.setStyleSheet("color: green;")
        else:
            self.connect_button.setEnabled(True)
            self.disconnect_button.setEnabled(False)
            self.host_edit.setEnabled(True)
            self.port_spinbox.setEnabled(True)
            self.tcp_status_label.setText("未连接")
            self.tcp_status_label.setStyleSheet("color: red;")
            
            # 当断开连接时，显示重连提示
            if hasattr(self, 'auto_reconnect_checkbox') and self.auto_reconnect_checkbox.isChecked():
                self.add_log("连接已断开，系统将自动尝试重连...")
            
    def set_ws_status(self, connected, client_count=None):
        """设置WebSocket状态"""
        if connected:
            self.ws_status_label.setText("WebSocket: 已连接")
            self.ws_status_label.setStyleSheet("color: green")
            self.ws_start_button.setEnabled(False)
            self.ws_stop_button.setEnabled(True)
            
            # 更新WebSocket状态标签
            status_text = "WebSocket: 已连接"
            self.ws_status_label.setText(status_text)
        else:
            self.ws_status_label.setText("WebSocket: 未连接")
            self.ws_status_label.setStyleSheet("color: red")
            self.ws_start_button.setEnabled(True)
            self.ws_stop_button.setEnabled(False)
            
        # 更新客户端信息
        if connected:
            self.ws_data_text.setText(f"当前连接的客户端数: {client_count}")
        else:
            self.ws_data_text.clear()
            
    def update_data_rate(self, frames):
        """更新数据速率"""
        self.data_count += frames
        
    def add_log(self, message):
        """添加日志"""
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        log_message = f"[{timestamp}] {message}"
        self.log_text.append(log_message)
        
        # 滚动到底部
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
        
        # 如果消息包含重连信息，更新状态标签
        if "尝试重新连接" in message and "次" in message:
            try:
                # 尝试提取当前重连次数和最大次数
                parts = message.split("(第 ")[1].split("/")
                current = parts[0].strip()
                maximum = parts[1].split(" ")[0].strip()
                self.tcp_status_label.setText(f"重连中 ({current}/{maximum})")
                self.tcp_status_label.setStyleSheet("color: orange;")
            except:
                # 如果提取失败，显示一般重连状态
                self.tcp_status_label.setText("重连中...")
                self.tcp_status_label.setStyleSheet("color: orange;")
        
    def show_error(self, message):
        """显示错误消息"""
        QMessageBox.critical(self, "错误", message)
        
        # 如果是连接错误，添加更详细的提示
        if "[Errno 61]" in message or "Connection refused" in message:
            self.add_log("连接错误: 服务器拒绝连接，可能原因:")
            self.add_log("1. 服务器未启动")
            self.add_log("2. 服务器地址或端口不正确")
            self.add_log("3. 服务器防火墙阻止了连接")
            self.add_log("4. 网络连接问题")
            self.add_log("建议: 检查服务器状态，确认地址和端口正确")
        
    def show_info(self, message):
        """显示信息消息"""
        QMessageBox.information(self, "信息", message)
        
    def reset_ws_ui(self):
        """重置WebSocket UI状态"""
        self.ws_start_button.setEnabled(True)
        self.ws_stop_button.setEnabled(False)
        self.ws_status_label.setText("WebSocket: 未连接")
        self.ws_status_label.setStyleSheet("color: red")
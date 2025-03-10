import logging
import json
import numpy as np
from PyQt5.QtCore import QObject, pyqtSlot
from PyQt5.QtWidgets import QMessageBox

from ..models.tcp_client import TCPClient
from ..models.eeg_parser import EEGParser
from ..models.data_buffer import DataBuffer
from ..models.websocket_client import WebSocketClient

class MainController(QObject):
    """主控制器，用于协调模型和视图之间的交互"""
    
    def __init__(self, view):
        super().__init__()
        self.view = view
        
        # 初始化模型
        self.tcp_client = TCPClient()
        self.eeg_parser = EEGParser()
        self.data_buffer = DataBuffer()
        self.websocket_client = WebSocketClient()
        
        # 连接信号和槽
        self._connect_signals()
        
        # 初始化日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # 调试模式标志
        self.debug_mode = False
        
        # 原始数据和解析数据的比较缓冲区
        self.raw_data_buffer = []
        self.parsed_data_buffer = []
        self.max_debug_buffer_size = 100  # 最多保存100帧数据用于比较
        
        # 将控制器设置为视图的子对象，以便能够接收调试模式设置
        self.setParent(view)
        
    def _connect_signals(self):
        """连接信号和槽"""
        # TCP客户端信号
        self.tcp_client.connected.connect(self._on_tcp_connected)
        self.tcp_client.disconnected.connect(self._on_tcp_disconnected)
        self.tcp_client.data_received.connect(self._on_data_received)
        self.tcp_client.connection_error.connect(self._on_tcp_error)
        self.tcp_client.log_message.connect(self._on_tcp_log)
        
        # 脑电解析器信号
        self.eeg_parser.data_parsed.connect(self._on_data_parsed)
        
        # 数据缓冲器信号
        self.data_buffer.data_updated.connect(self._on_data_updated)
        
        # WebSocket客户端信号
        self.websocket_client.connected.connect(self._on_ws_connected)
        self.websocket_client.disconnected.connect(self._on_ws_disconnected)
        self.websocket_client.data_received.connect(self._on_ws_data_received)
        self.websocket_client.connection_error.connect(self._on_ws_error)
        self.websocket_client.log_message.connect(self._on_ws_log)
        
        # 视图信号
        self.view.tcp_connect_requested.connect(self.connect_to_server)
        self.view.tcp_disconnect_requested.connect(self.disconnect_from_server)
        self.view.ws_server_start_requested.connect(self.connect_to_ws_server)
        self.view.ws_server_stop_requested.connect(self.disconnect_from_ws_server)
        self.view.tcp_params_changed.connect(self._on_tcp_params_changed)
        self.view.ws_params_changed.connect(self._on_ws_params_changed)
        self.view.clear_data_requested.connect(self.clear_data)
        
    @pyqtSlot(str, int)
    def connect_to_server(self, host, port):
        """连接到TCP服务器"""
        # 设置自动重连
        auto_reconnect = self.view.auto_reconnect_checkbox.isChecked()
        reconnect_interval = self.view.reconnect_interval_spinbox.value()
        self.tcp_client.set_auto_reconnect(auto_reconnect, reconnect_interval)
        
        # 连接前添加日志
        self.view.add_log(f"正在连接到服务器 {host}:{port}...")
        
        # 尝试连接
        self.tcp_client.connect(host, port)
        
    @pyqtSlot()
    def disconnect_from_server(self):
        """断开TCP服务器连接"""
        self.tcp_client.disconnect()
        
    @pyqtSlot(str, int)
    def connect_to_ws_server(self, host, port):
        """连接到WebSocket服务器"""
        # 设置自动重连
        auto_reconnect = self.view.auto_reconnect_checkbox.isChecked()
        reconnect_interval = self.view.reconnect_interval_spinbox.value()
        self.websocket_client.set_auto_reconnect(auto_reconnect, reconnect_interval)
        
        # 添加日志
        self.view.add_log(f"正在连接到WebSocket服务器 {host}:{port}...")
        
        # 尝试连接
        success = self.websocket_client.connect(host, port)
        
        # 如果连接失败但没有触发错误信号，显示一般性错误
        if not success and not self.websocket_client.get_connection_status():
            self.view.add_log("WebSocket服务器连接失败，请检查网络设置或服务器状态")
            self.view.show_error("WebSocket服务器连接失败")
            # 重置UI状态
            self.view.reset_ws_ui()
        
    @pyqtSlot()
    def disconnect_from_ws_server(self):
        """断开WebSocket服务器连接"""
        self.websocket_client.disconnect()
        
    @pyqtSlot()
    def clear_data(self):
        """清空数据缓冲区"""
        self.data_buffer.clear()
        self.view.clear_plot()
        self.view.add_log("数据已清空")
        
    @pyqtSlot(str, int)
    def _on_tcp_connected(self, host, port):
        """TCP连接成功回调"""
        self.view.set_tcp_status(True)
        self.view.add_log(f"已连接到TCP服务器 {host}:{port}")
        
    @pyqtSlot()
    def _on_tcp_disconnected(self):
        """TCP断开连接回调"""
        self.view.set_tcp_status(False)
        self.view.add_log("已断开TCP服务器连接")
        
    @pyqtSlot(bytes)
    def _on_data_received(self, data):
        """接收到TCP数据回调"""
        try:
            # 记录接收到的数据大小
            logging.debug(f"接收到 {len(data)} 字节的数据")
            
            # 如果开启了调试模式，保存原始数据
            if self.debug_mode:
                # 将原始字节转换为十六进制字符串以便记录
                hex_data = ' '.join([f'{b:02X}' for b in data])
                self.raw_data_buffer.append(hex_data)
                # 保持缓冲区大小
                if len(self.raw_data_buffer) > self.max_debug_buffer_size:
                    self.raw_data_buffer.pop(0)
            
            # 处理接收到的数据
            frames_processed = self.eeg_parser.process_data(data)
            if frames_processed > 0:
                self.view.update_data_rate(frames_processed)
                logging.debug(f"成功处理了 {frames_processed} 帧数据")
            elif len(data) > 0:
                logging.debug("接收到数据但未能解析出完整帧")
        except Exception as e:
            logging.error(f"处理接收数据时出错: {str(e)}")
            self.view.add_log(f"数据处理错误: {str(e)}")
        
    @pyqtSlot(str)
    def _on_tcp_error(self, error_msg):
        """TCP错误回调"""
        self.view.show_error(error_msg)
        self.view.add_log(f"TCP错误: {error_msg}")
        
        # 检查是否是连接被拒绝错误
        if "[Errno 61]" in error_msg or "Connection refused" in error_msg:
            # 更新连接状态
            self.view.set_tcp_status(False)
            
            # 提供更多诊断信息
            self.view.add_log("正在检查网络连接...")
            
            # 可以在这里添加网络诊断代码
            # 例如，检查服务器是否可ping通
            import subprocess
            import platform
            
            try:
                # 获取当前连接的主机
                host = self.tcp_client.host
                port = self.tcp_client.port
                
                # 根据操作系统选择ping命令参数
                param = '-n' if platform.system().lower() == 'windows' else '-c'
                command = ['ping', param, '1', host]
                
                # 执行ping命令
                ping_result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=2)
                
                if ping_result.returncode == 0:
                    self.view.add_log(f"服务器主机 {host} 可以ping通，但端口 {port} 连接被拒绝")
                    self.view.add_log("可能是服务器程序未运行或端口配置错误")
                else:
                    self.view.add_log(f"无法ping通服务器主机 {host}")
                    self.view.add_log("可能是网络连接问题或主机不存在")
            except Exception as e:
                self.view.add_log(f"网络诊断失败: {str(e)}")
        
        # 如果错误消息包含"最大重试次数"，说明自动重连已经失败
        if "最大重试次数" in error_msg:
            self.view.add_log("自动重连已达到最大尝试次数，请手动重新连接")
            # 确保UI状态正确更新
            self.view.set_tcp_status(False)
        
    @pyqtSlot(dict)
    def _on_data_parsed(self, data):
        """数据解析完成回调"""
        try:
            # 检查数据完整性
            if 'channels' not in data or 'labels' not in data:
                logging.warning("解析的数据不完整，缺少通道或标签数据")
                return
            
            # 如果开启了调试模式，保存解析后的数据
            if self.debug_mode:
                # 只保存通道数据用于比较
                channels_data = data['channels']
                self.parsed_data_buffer.append(channels_data)
                # 保持缓冲区大小
                if len(self.parsed_data_buffer) > self.max_debug_buffer_size:
                    self.parsed_data_buffer.pop(0)
                
                # 每收到10帧数据，进行一次比较分析
                if len(self.parsed_data_buffer) % 10 == 0:
                    self._analyze_data_quality()
            
            # 添加到数据缓冲区
            self.data_buffer.add_data(data)
            
            # 如果WebSocket客户端已连接，发送数据
            if self.websocket_client.get_connection_status():
                self.websocket_client.send_data(data)
        except Exception as e:
            logging.error(f"处理解析数据时出错: {str(e)}")
            self.view.add_log(f"数据解析处理错误: {str(e)}")
        
    @pyqtSlot(dict)
    def _on_data_updated(self, data):
        """数据更新回调"""
        try:
            # 更新视图
            self.view.update_plot(data)
        except Exception as e:
            logging.error(f"更新图表时出错: {str(e)}")
            self.view.add_log(f"图表更新错误: {str(e)}")
        
    @pyqtSlot(str, int)
    def _on_ws_connected(self, host, port):
        """WebSocket连接成功回调"""
        self.view.set_ws_status(True)
        self.view.add_log(f"已连接到WebSocket服务器 {host}:{port}")
        
    @pyqtSlot()
    def _on_ws_disconnected(self):
        """WebSocket断开连接回调"""
        self.view.set_ws_status(False)
        self.view.add_log("已断开WebSocket服务器连接")
        
    @pyqtSlot(dict)
    def _on_ws_data_received(self, data):
        """接收到WebSocket数据回调"""
        try:
            # 处理接收到的数据
            logging.debug(f"接收到WebSocket数据: {data}")
            
            # 这里可以添加对接收到的数据的处理逻辑
            # 例如，如果数据包含控制命令，可以执行相应的操作
            
            # 添加到日志
            self.view.add_log(f"接收到WebSocket数据: {str(data)[:100]}...")
        except Exception as e:
            logging.error(f"处理WebSocket数据时出错: {str(e)}")
            self.view.add_log(f"WebSocket数据处理错误: {str(e)}")
        
    @pyqtSlot(str)
    def _on_ws_error(self, error_msg):
        """WebSocket错误回调"""
        self.view.show_error(error_msg)
        self.view.add_log(f"WebSocket错误: {error_msg}")
        
        # 如果WebSocket客户端未连接，重置UI状态
        if not self.websocket_client.get_connection_status():
            self.view.reset_ws_ui()
        
        # 检查是否是连接超时错误
        if "连接超时" in error_msg:
            # 询问用户是否要重试
            retry = QMessageBox.question(
                self.view,
                "WebSocket连接超时",
                "WebSocket连接超时，是否要重试？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if retry == QMessageBox.Yes:
                # 获取当前的主机和端口
                host = self.view.ws_host_edit.text() or "127.0.0.1"
                port = self.view.ws_port_spinbox.value() or 8765
                
                # 重新尝试连接
                self.connect_to_ws_server(host, port)
        
    @pyqtSlot(str)
    def _on_ws_log(self, message):
        """WebSocket日志回调"""
        self.view.add_log(message)
        
    @pyqtSlot(str, int)
    def _on_tcp_params_changed(self, host, port):
        """TCP参数改变回调"""
        # 可以在这里添加对TCP参数改变的处理逻辑
        pass
        
    @pyqtSlot(str, int)
    def _on_ws_params_changed(self, host, port):
        """WebSocket参数改变回调"""
        # 可以在这里添加对WebSocket参数改变的处理逻辑
        pass
        
    def set_sampling_rate(self, rate):
        """设置采样率"""
        self.eeg_parser.set_sampling_rate(rate)
        
    def set_auto_reconnect(self, enabled, interval=None):
        """设置自动重连"""
        self.tcp_client.set_auto_reconnect(enabled, interval)
        
    @pyqtSlot(str)
    def _on_tcp_log(self, message):
        """TCP日志回调"""
        self.view.add_log(message)
        
    def set_debug_mode(self, enabled):
        """设置调试模式"""
        self.debug_mode = enabled
        logging.info(f"调试模式已{'启用' if enabled else '禁用'}")
        
        # 如果禁用调试模式，清空调试缓冲区
        if not enabled:
            self.raw_data_buffer.clear()
            self.parsed_data_buffer.clear()
            
        # 通知视图调试模式已改变
        self.view._debug_mode_changed_internal(enabled)
        
    def _analyze_data_quality(self):
        """分析数据质量"""
        if not self.debug_mode or len(self.parsed_data_buffer) < 10:
            return
            
        # 这里可以添加数据质量分析逻辑
        # 例如，检查数据的连续性、噪声水平等
        
        # 简单示例：计算最近10帧数据的平均值和标准差
        try:
            recent_data = np.array(self.parsed_data_buffer[-10:])
            mean_values = np.mean(recent_data, axis=0)
            std_values = np.std(recent_data, axis=0)
            
            # 检查是否有异常值
            for i, (mean, std) in enumerate(zip(mean_values, std_values)):
                if std > 100:  # 假设标准差大于100表示数据波动较大
                    logging.warning(f"通道 {i+1} 数据波动较大: 均值={mean:.2f}, 标准差={std:.2f}")
        except Exception as e:
            logging.error(f"分析数据质量时出错: {str(e)}") 
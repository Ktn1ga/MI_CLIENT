import socket
import time
import threading
import logging
from PyQt5.QtCore import QObject, pyqtSignal

class TCPClient(QObject):
    """TCP客户端，用于接收脑电数据"""
    
    # 信号定义
    connected = pyqtSignal(str, int)  # 连接成功信号（主机，端口）
    disconnected = pyqtSignal()  # 断开连接信号
    data_received = pyqtSignal(bytes)  # 数据接收信号
    connection_error = pyqtSignal(str)  # 连接错误信号
    log_message = pyqtSignal(str)  # 日志消息信号
    
    def __init__(self):
        super().__init__()
        self.host = "127.0.0.1"
        self.port = 8888
        self.socket = None
        self.is_connected = False
        self.auto_reconnect = True
        self.reconnect_interval = 3  # 重连间隔（秒）
        self.receive_thread = None
        self.reconnect_thread = None
        self.running = False
        
    def connect(self, host=None, port=None):
        """连接到服务器"""
        if host:
            self.host = host
        if port:
            self.port = port
            
        if self.is_connected:
            self.disconnect()
            
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5)  # 设置超时时间
            
            # 尝试连接前检查服务器是否可达
            try:
                self.socket.connect((self.host, self.port))
            except ConnectionRefusedError:
                # 特别处理连接被拒绝的情况
                error_msg = f"连接被拒绝 [Errno 61]: 无法连接到 {self.host}:{self.port}，请确认服务器是否已启动"
                self.connection_error.emit(error_msg)
                logging.error(error_msg)
                
                # 发送断开连接信号，确保UI状态更新
                self.disconnected.emit()
                
                # 如果启用自动重连，启动重连线程
                if self.auto_reconnect and not self.reconnect_thread:
                    self.reconnect_thread = threading.Thread(target=self._auto_reconnect)
                    self.reconnect_thread.daemon = True
                    self.reconnect_thread.start()
                return False
                
            self.is_connected = True
            self.running = True
            
            # 启动接收线程
            self.receive_thread = threading.Thread(target=self._receive_data)
            self.receive_thread.daemon = True
            self.receive_thread.start()
            
            self.connected.emit(self.host, self.port)
            logging.info(f"已连接到服务器 {self.host}:{self.port}")
            return True
        except Exception as e:
            self.is_connected = False
            error_msg = f"连接服务器失败: {str(e)}"
            self.connection_error.emit(error_msg)
            logging.error(error_msg)
            
            # 发送断开连接信号，确保UI状态更新
            self.disconnected.emit()
            
            # 如果启用自动重连，启动重连线程
            if self.auto_reconnect and not self.reconnect_thread:
                self.reconnect_thread = threading.Thread(target=self._auto_reconnect)
                self.reconnect_thread.daemon = True
                self.reconnect_thread.start()
            return False
    
    def disconnect(self):
        """断开连接"""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        
        self.is_connected = False
        self.disconnected.emit()
        logging.info("已断开服务器连接")
    
    def _receive_data(self):
        """接收数据线程"""
        buffer_size = 1024
        
        while self.running and self.is_connected:
            try:
                data = self.socket.recv(buffer_size)
                if not data:
                    # 连接已关闭
                    self.is_connected = False
                    self.disconnected.emit()
                    logging.warning("服务器关闭了连接")
                    break
                
                # 发送接收到的数据
                self.data_received.emit(data)
            except socket.timeout:
                # 超时，继续尝试
                continue
            except Exception as e:
                if self.running:  # 只有在仍然运行时才报告错误
                    self.is_connected = False
                    error_msg = f"接收数据时出错: {str(e)}"
                    self.connection_error.emit(error_msg)
                    self.disconnected.emit()
                    logging.error(error_msg)
                break
        
        # 如果启用自动重连且仍在运行
        if self.auto_reconnect and self.running and not self.is_connected and not self.reconnect_thread:
            self.reconnect_thread = threading.Thread(target=self._auto_reconnect)
            self.reconnect_thread.daemon = True
            self.reconnect_thread.start()
    
    def _auto_reconnect(self):
        """自动重连线程"""
        retry_count = 0
        max_retries = 10  # 最大重试次数
        
        while self.auto_reconnect and self.running and not self.is_connected and retry_count < max_retries:
            retry_count += 1
            log_msg = f"尝试重新连接到 {self.host}:{self.port}... (第 {retry_count}/{max_retries} 次)"
            logging.info(log_msg)
            self.log_message.emit(log_msg)
            
            try:
                # 创建新的套接字
                if self.socket:
                    try:
                        self.socket.close()
                    except:
                        pass
                
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(5)
                self.socket.connect((self.host, self.port))
                
                self.is_connected = True
                self.running = True
                
                # 启动接收线程
                self.receive_thread = threading.Thread(target=self._receive_data)
                self.receive_thread.daemon = True
                self.receive_thread.start()
                
                self.connected.emit(self.host, self.port)
                success_msg = f"重连成功: 已连接到服务器 {self.host}:{self.port}"
                logging.info(success_msg)
                self.log_message.emit(success_msg)
                break
            except ConnectionRefusedError:
                error_msg = f"重连失败: 连接被拒绝 [Errno 61] - 服务器 {self.host}:{self.port} 未响应"
                logging.warning(error_msg)
                self.log_message.emit(error_msg)
            except Exception as e:
                error_msg = f"重连失败: {str(e)}"
                logging.warning(error_msg)
                self.log_message.emit(error_msg)
            
            # 等待重连间隔
            time.sleep(self.reconnect_interval)
        
        if retry_count >= max_retries and not self.is_connected:
            error_msg = f"重连失败: 已达到最大重试次数 ({max_retries})，请检查服务器状态或手动重连"
            logging.error(error_msg)
            self.connection_error.emit(error_msg)
            self.log_message.emit(error_msg)
            # 发送断开连接信号，确保UI状态更新
            self.disconnected.emit()
        
        self.reconnect_thread = None
    
    def send_data(self, data):
        """发送数据到服务器"""
        if not self.is_connected or not self.socket:
            return False
        
        try:
            self.socket.sendall(data)
            return True
        except Exception as e:
            error_msg = f"发送数据失败: {str(e)}"
            self.connection_error.emit(error_msg)
            logging.error(error_msg)
            self.is_connected = False
            self.disconnected.emit()
            return False
    
    def set_auto_reconnect(self, enabled, interval=None):
        """设置自动重连"""
        self.auto_reconnect = enabled
        if interval is not None:
            self.reconnect_interval = interval 
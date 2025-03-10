#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
TCP服务器模型 - 负责网络通信和数据传输
"""

import socket
import threading
import time
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal

class TcpServer(QObject):
    """TCP服务器类，负责数据传输"""
    
    # 信号定义
    client_connected = pyqtSignal(str, int)  # 客户端连接信号（IP, 端口）
    client_disconnected = pyqtSignal(str, int)  # 客户端断开信号（IP, 端口）
    error_occurred = pyqtSignal(str)  # 错误信号
    data_sent = pyqtSignal(int)  # 数据发送信号（字节数）
    
    def __init__(self, host='localhost', port=50012, max_clients=5):
        super().__init__()
        self.host = host
        self.port = port
        self.max_clients = max_clients
        self.server_socket = None
        self.is_running = False
        self.clients = []  # 客户端连接列表
        self.lock = threading.Lock()  # 线程锁
        self.accept_thread = None
    
    def start(self):
        """启动TCP服务器"""
        if self.is_running:
            return
        
        try:
            # 关闭之前的服务器套接字（如果存在）
            if self.server_socket:
                try:
                    self.server_socket.close()
                except:
                    pass
            
            # 创建服务器套接字
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(self.max_clients)
            self.server_socket.settimeout(1.0)  # 设置超时，便于停止服务器
            
            self.is_running = True
            
            # 启动接受客户端线程
            self.accept_thread = threading.Thread(target=self._accept_clients)
            self.accept_thread.daemon = True
            self.accept_thread.start()
            
            return True
        except Exception as e:
            self.error_occurred.emit(f"启动服务器失败: {str(e)}")
            return False
    
    def stop(self):
        """停止TCP服务器"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # 关闭所有客户端连接
        with self.lock:
            for client in self.clients:
                try:
                    client.close()
                except:
                    pass
            self.clients = []
        
        # 关闭服务器套接字
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None
        
        # 等待接受线程结束
        if self.accept_thread and self.accept_thread.is_alive():
            self.accept_thread.join(2.0)
    
    def _accept_clients(self):
        """接受客户端连接的线程函数"""
        while self.is_running:
            try:
                client_socket, addr = self.server_socket.accept()
                
                # 检查是否超过最大连接数
                with self.lock:
                    if len(self.clients) >= self.max_clients:
                        client_socket.close()
                        continue
                    
                    self.clients.append(client_socket)
                
                # 发送客户端连接信号
                self.client_connected.emit(addr[0], addr[1])
                
            except socket.timeout:
                # 超时，继续循环
                continue
            except Exception as e:
                if self.is_running:
                    self.error_occurred.emit(f"接受客户端连接失败: {str(e)}")
                break
    
    def send_data(self, data):
        """向所有客户端发送数据
        
        Args:
            data: 8通道脑电数据，numpy数组
        
        Returns:
            int: 成功发送的客户端数量
        """
        if not self.is_running or not self.clients:
            return 0
        
        # 检查数据是否有效
        if data is None or len(data) == 0:
            return 0
        
        # 将数据打包成帧
        try:
            frame = self._pack_data(data)
        except Exception as e:
            self.error_occurred.emit(f"数据打包错误: {str(e)}")
            return 0
        
        # 发送数据
        sent_count = 0
        disconnected_clients = []
        
        with self.lock:
            for client in self.clients:
                try:
                    client.sendall(frame)
                    sent_count += 1
                    self.data_sent.emit(len(frame))
                except:
                    # 记录断开的客户端
                    disconnected_clients.append(client)
            
            # 移除断开的客户端
            for client in disconnected_clients:
                try:
                    self.clients.remove(client)
                    # 尝试获取客户端地址
                    try:
                        addr = client.getpeername()
                        self.client_disconnected.emit(addr[0], addr[1])
                    except:
                        pass
                    client.close()
                except:
                    pass
        
        return sent_count
    
    def _pack_data(self, data):
        """将数据打包成帧
        
        帧结构：
        [帧头][数据段][标签段][帧尾]
        帧头：2字节（0xA0, 0xFF）
        数据段：8通道×3字节（小端序存储）
        标签段：2通道×3字节（预留扩展位）
        帧尾：2字节（0xC0, 0x00）
        
        Args:
            data: 8通道脑电数据，numpy数组
        
        Returns:
            bytes: 打包后的帧数据
        """
        # 帧头
        frame = bytearray([0xA0, 0xFF])
        
        # 数据段（8通道）
        for i in range(min(8, len(data))):
            # 将电压值转换为24位整数
            # 换算公式：int_value = (voltage / ref_voltage) * 8388607
            # 这里假设参考电压为1000μV
            ref_voltage = 1000.0
            int_value = int((data[i] / ref_voltage) * 8388607)
            
            # 限制在24位有符号整数范围内
            int_value = max(-8388608, min(8388607, int_value))
            
            # 转换为3字节（小端序）
            if int_value < 0:
                int_value += 16777216  # 2^24
            
            frame.append(int_value & 0xFF)
            frame.append((int_value >> 8) & 0xFF)
            frame.append((int_value >> 16) & 0xFF)
        
        # 如果通道数不足8个，补零
        for i in range(max(0, 8 - len(data))):
            frame.extend([0, 0, 0])
        
        # 标签段（2通道，预留）
        for i in range(2):
            frame.extend([0, 0, 0])
        
        # 帧尾
        frame.extend([0xC0, 0x00])
        # 输出帧
        print(frame)
        print(bytes(frame))

        return bytes(frame)
    
    def get_client_count(self):
        """获取当前连接的客户端数量"""
        with self.lock:
            return len(self.clients)
    
    def set_host(self, host):
        """设置服务器主机地址"""
        if not self.is_running:
            self.host = host
    
    def set_port(self, port):
        """设置服务器端口"""
        if not self.is_running:
            self.port = port
    
    def set_max_clients(self, max_clients):
        """设置最大客户端连接数"""
        self.max_clients = max_clients 
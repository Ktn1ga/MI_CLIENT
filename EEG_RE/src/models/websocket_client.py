import asyncio
import json
import threading
import logging
import websockets
from PyQt5.QtCore import QObject, pyqtSignal
import time
import concurrent.futures

class WebSocketClient(QObject):
    """WebSocket客户端，用于接收脑电数据"""
    
    # 信号定义
    connected = pyqtSignal(str, int)  # 连接成功信号（主机，端口）
    disconnected = pyqtSignal()  # 断开连接信号
    data_received = pyqtSignal(dict)  # 数据接收信号
    connection_error = pyqtSignal(str)  # 连接错误信号
    log_message = pyqtSignal(str)  # 日志消息信号
    
    def __init__(self):
        super().__init__()
        self.host = "127.0.0.1"
        self.port = 8765
        self.websocket = None
        self.is_connected = False
        self.auto_reconnect = True
        self.reconnect_interval = 3  # 重连间隔（秒）
        self.client_thread = None
        self.reconnect_thread = None
        self.loop = None
        self.running = False
        
    def connect(self, host=None, port=None):
        """连接到WebSocket服务器"""
        if host:
            self.host = host
        if port:
            self.port = port
            
        if self.is_connected:
            self.disconnect()
            
        # 如果有之前的线程或循环未清理，先清理
        self._cleanup_resources()
            
        try:
            # 创建新的事件循环
            self.loop = asyncio.new_event_loop()
            
            # 启动客户端线程
            self.client_thread = threading.Thread(target=self._run_client)
            self.client_thread.daemon = True
            self.client_thread.start()
            
            # 等待客户端线程启动事件循环
            start_time = time.time()
            while not self.is_connected and time.time() - start_time < 5:  # 最多等待5秒
                time.sleep(0.1)
                
            if not self.is_connected:
                logging.error("WebSocket客户端连接超时")
                self.connection_error.emit("WebSocket客户端连接超时，可以尝试重新连接")
                # 清理资源，以便可以重新连接
                self._cleanup_resources()
                
                # 如果启用自动重连，启动重连线程
                if self.auto_reconnect and not self.reconnect_thread:
                    self.reconnect_thread = threading.Thread(target=self._auto_reconnect)
                    self.reconnect_thread.daemon = True
                    self.reconnect_thread.start()
                return False
                
            logging.info(f"已连接到WebSocket服务器 {self.host}:{self.port}")
            return True
        except Exception as e:
            error_msg = f"连接WebSocket服务器失败: {str(e)}"
            logging.error(error_msg)
            self.connection_error.emit(error_msg)
            # 清理资源，以便可以重新连接
            self._cleanup_resources()
            
            # 如果启用自动重连，启动重连线程
            if self.auto_reconnect and not self.reconnect_thread:
                self.reconnect_thread = threading.Thread(target=self._auto_reconnect)
                self.reconnect_thread.daemon = True
                self.reconnect_thread.start()
            return False
        
    def _cleanup_resources(self):
        """清理客户端资源，以便可以重新连接"""
        # 停止并清理事件循环
        if self.loop and not self.loop.is_closed():
            try:
                # 尝试优雅地关闭
                future = asyncio.run_coroutine_threadsafe(self._disconnect_websocket(), self.loop)
                # 等待协程完成，最多等待2秒
                try:
                    future.result(timeout=2.0)
                except (asyncio.TimeoutError, concurrent.futures.TimeoutError):
                    logging.warning("断开连接超时，将强制关闭")
                except Exception as e:
                    logging.warning(f"断开连接时出错: {str(e)}")
                    
                # 如果仍在运行，强制关闭
                if not self.loop.is_closed():
                    self.loop.call_soon_threadsafe(self.loop.stop)
                    # 给一点时间让循环停止
                    time.sleep(0.2)
                    if not self.loop.is_closed():
                        self.loop.close()
            except Exception as e:
                logging.warning(f"清理事件循环时出错: {str(e)}")
                
        self.loop = None
        
        # 等待并清理客户端线程
        if self.client_thread and self.client_thread.is_alive():
            try:
                # 增加超时时间，确保线程有足够时间终止
                self.client_thread.join(timeout=2)
                if self.client_thread.is_alive():
                    logging.warning("客户端线程未能在指定时间内终止")
            except Exception as e:
                logging.warning(f"等待客户端线程结束时出错: {str(e)}")
                
        self.client_thread = None
        self.websocket = None
        self.is_connected = False
        self.running = False
        
    def disconnect(self):
        """断开WebSocket连接"""
        if not self.is_connected:
            logging.info("WebSocket客户端未连接")
            return
        
        try:
            logging.info("正在断开WebSocket连接...")
            self.running = False
            
            # 使用清理资源方法
            self._cleanup_resources()
            
            self.disconnected.emit()
            logging.info("WebSocket连接已断开")
        except Exception as e:
            error_msg = f"断开WebSocket连接时出错: {str(e)}"
            logging.error(error_msg)
            self.connection_error.emit(error_msg)
            
            # 即使出错，也尝试强制清理
            self.is_connected = False
            self.websocket = None
            self.loop = None
            self.client_thread = None
        
    def _run_client(self):
        """在单独的线程中运行客户端"""
        # 设置当前线程的事件循环
        asyncio.set_event_loop(self.loop)
        
        try:
            # 启动客户端连接
            self.running = True
            self.loop.run_until_complete(self._connect_to_server())
            
            # 运行事件循环
            self.loop.run_forever()
        except Exception as e:
            error_msg = f"WebSocket客户端错误: {str(e)}"
            # 使用call_soon_threadsafe确保线程安全
            if self.loop and not self.loop.is_closed():
                self.loop.call_soon_threadsafe(lambda: self.connection_error.emit(error_msg))
            logging.error(error_msg)
        finally:
            # 确保资源被清理
            self.running = False
            self.is_connected = False
            
            # 关闭WebSocket连接
            if self.websocket and not self.loop.is_closed():
                try:
                    self.loop.run_until_complete(self.websocket.close())
                except Exception as e:
                    logging.error(f"关闭WebSocket连接时出错: {str(e)}")
            
            # 关闭事件循环
            if not self.loop.is_closed():
                try:
                    # 取消所有挂起的任务
                    pending = asyncio.all_tasks(self.loop)
                    if pending:
                        for task in pending:
                            task.cancel()
                        self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    
                    self.loop.close()
                except Exception as e:
                    logging.error(f"关闭事件循环时出错: {str(e)}")
                    
            logging.info("WebSocket客户端线程已终止")
            
            # 发送断开连接信号
            self.disconnected.emit()
            
            # 如果启用自动重连且仍在运行
            if self.auto_reconnect and not self.reconnect_thread:
                self.reconnect_thread = threading.Thread(target=self._auto_reconnect)
                self.reconnect_thread.daemon = True
                self.reconnect_thread.start()
        
    async def _connect_to_server(self):
        """连接到WebSocket服务器"""
        uri = f"ws://{self.host}:{self.port}"
        try:
            self.websocket = await websockets.connect(uri)
            self.is_connected = True
            
            # 发送连接成功信号
            self.loop.call_soon_threadsafe(lambda: self.connected.emit(self.host, self.port))
            self.loop.call_soon_threadsafe(lambda: self.log_message.emit(f"已连接到WebSocket服务器 {self.host}:{self.port}"))
            
            # 开始接收消息
            await self._receive_messages()
        except Exception as e:
            error_msg = f"连接到WebSocket服务器失败: {str(e)}"
            self.loop.call_soon_threadsafe(lambda: self.connection_error.emit(error_msg))
            self.loop.call_soon_threadsafe(lambda: self.log_message.emit(error_msg))
            logging.error(error_msg)
            self.is_connected = False
            
    async def _receive_messages(self):
        """接收WebSocket消息"""
        try:
            async for message in self.websocket:
                try:
                    # 尝试解析JSON消息
                    data = json.loads(message)
                    # 发送数据接收信号
                    self.loop.call_soon_threadsafe(lambda d=data: self.data_received.emit(d))
                except json.JSONDecodeError as e:
                    logging.warning(f"接收到无效的JSON数据: {str(e)}")
                    # 如果不是JSON，也发送原始消息
                    self.loop.call_soon_threadsafe(lambda m=message: self.data_received.emit({"raw": m}))
        except websockets.exceptions.ConnectionClosed:
            logging.info("WebSocket连接已关闭")
            self.is_connected = False
        except Exception as e:
            error_msg = f"接收WebSocket消息时出错: {str(e)}"
            logging.error(error_msg)
            self.loop.call_soon_threadsafe(lambda: self.connection_error.emit(error_msg))
            self.is_connected = False
            
    async def _disconnect_websocket(self):
        """断开WebSocket连接"""
        if self.websocket:
            try:
                await self.websocket.close()
                self.websocket = None
            except Exception as e:
                logging.error(f"断开WebSocket连接时出错: {str(e)}")
                
    def _auto_reconnect(self):
        """自动重连线程"""
        retry_count = 0
        max_retries = 10  # 最大重试次数
        
        while self.auto_reconnect and self.running and not self.is_connected and retry_count < max_retries:
            retry_count += 1
            log_msg = f"尝试重新连接到 {self.host}:{self.port}... (第 {retry_count}/{max_retries} 次)"
            logging.info(log_msg)
            self.log_message.emit(log_msg)
            
            # 尝试重新连接
            self.connect(self.host, self.port)
            
            # 如果连接成功，退出重连循环
            if self.is_connected:
                break
                
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
        """发送数据到WebSocket服务器"""
        # 先检查连接状态
        if not self.is_connected or not self.websocket:
            logging.warning("WebSocket未连接，无法发送数据")
            return False
            
        # 检查事件循环是否存在且正在运行
        if not self.loop or self.loop.is_closed():
            logging.warning("WebSocket事件循环未运行，无法发送数据")
            return False
            
        # 将数据转换为JSON字符串
        try:
            if isinstance(data, dict):
                # 将numpy.datetime64转换为ISO格式字符串
                if 'timestamp' in data and hasattr(data['timestamp'], 'astype'):
                    data['timestamp'] = str(data['timestamp'])
                json_data = json.dumps(data)
            else:
                json_data = json.dumps({"data": data})
        except Exception as e:
            logging.error(f"数据序列化为JSON时出错: {str(e)}")
            self.connection_error.emit(f"数据序列化为JSON时出错: {str(e)}")
            return False
            
        # 创建发送任务
        try:
            # 使用run_coroutine_threadsafe在事件循环中执行协程
            future = asyncio.run_coroutine_threadsafe(self._safe_send(json_data), self.loop)
            
            # 可选：等待发送完成并检查结果
            # result = future.result(timeout=1.0)
            # return result
            return True
        except RuntimeError as e:
            logging.error(f"发送数据时出错: {str(e)}")
            self.connection_error.emit(f"发送数据时出错: {str(e)}")
            return False
        except Exception as e:
            logging.error(f"发送数据时发生未预期的错误: {str(e)}")
            self.connection_error.emit(f"发送数据时发生未预期的错误: {str(e)}")
            return False
        
    async def _safe_send(self, message):
        """安全地发送消息到服务器"""
        if not self.websocket or not self.is_connected:
            return False
            
        try:
            await self.websocket.send(message)
            return True
        except websockets.exceptions.ConnectionClosed:
            # 连接已关闭
            self.is_connected = False
            self.loop.call_soon_threadsafe(self.disconnected.emit)
            return False
        except Exception as e:
            logging.error(f"发送数据到服务器时出错: {str(e)}")
            self.loop.call_soon_threadsafe(lambda: self.connection_error.emit(f"发送数据到服务器时出错: {str(e)}"))
            self.is_connected = False
            self.loop.call_soon_threadsafe(self.disconnected.emit)
            return False
        
    def set_auto_reconnect(self, enabled, interval=None):
        """设置自动重连"""
        self.auto_reconnect = enabled
        if interval is not None:
            self.reconnect_interval = interval
            
    def get_connection_status(self):
        """获取当前连接状态"""
        return self.is_connected 
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
工具函数 - 提供通用功能
"""

import os
import sys
import numpy as np
import pandas as pd
import datetime

def validate_csv_file(file_path):
    """验证CSV文件格式
    
    Args:
        file_path: CSV文件路径
    
    Returns:
        tuple: (是否有效, 错误消息)
    """
    if not os.path.exists(file_path):
        return False, "文件不存在"
    
    try:
        # 读取CSV文件
        df = pd.read_csv(file_path)
        
        # 检查通道数
        if df.shape[1] < 8:
            return False, f"通道数不足，需要至少8个通道，当前只有{df.shape[1]}个"
        
        # 检查数据类型
        for col in df.columns[:8]:
            if not np.issubdtype(df[col].dtype, np.number):
                return False, f"通道 {col} 包含非数值数据"
        
        return True, ""
    except Exception as e:
        return False, f"文件格式错误: {str(e)}"

def int_to_bytes(value, bytes_count=3, signed=True):
    """将整数转换为字节数组（小端序）
    
    Args:
        value: 整数值
        bytes_count: 字节数
        signed: 是否有符号
    
    Returns:
        bytes: 字节数组
    """
    if signed:
        # 处理负数
        if value < 0:
            # 计算补码表示
            max_val = 1 << (8 * bytes_count)
            value = max_val + value
    
    # 转换为字节数组（小端序）
    result = bytearray()
    for i in range(bytes_count):
        result.append((value >> (8 * i)) & 0xFF)
    
    return bytes(result)

def bytes_to_int(data, signed=True):
    """将字节数组（小端序）转换为整数
    
    Args:
        data: 字节数组
        signed: 是否有符号
    
    Returns:
        int: 整数值
    """
    value = 0
    for i, b in enumerate(data):
        value |= b << (8 * i)
    
    if signed:
        # 处理负数（补码表示）
        sign_bit = 1 << (8 * len(data) - 1)
        if value & sign_bit:
            value = value - (1 << (8 * len(data)))
    
    return value

def voltage_to_int(voltage, ref_voltage=1000.0):
    """将电压值转换为24位整数
    
    Args:
        voltage: 电压值（μV）
        ref_voltage: 参考电压（μV）
    
    Returns:
        int: 24位整数值
    """
    # 换算公式：int_value = (voltage / ref_voltage) * 8388607
    int_value = int((voltage / ref_voltage) * 8388607)
    
    # 限制在24位有符号整数范围内
    int_value = max(-8388608, min(8388607, int_value))
    
    return int_value

def int_to_voltage(int_value, ref_voltage=1000.0):
    """将24位整数转换为电压值
    
    Args:
        int_value: 24位整数值
        ref_voltage: 参考电压（μV）
    
    Returns:
        float: 电压值（μV）
    """
    # 换算公式：voltage = (int_value / 8388607) * ref_voltage
    voltage = (int_value / 8388607) * ref_voltage
    
    return voltage

def get_timestamp():
    """获取当前时间戳字符串
    
    Returns:
        str: 时间戳字符串
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

def create_sample_csv(file_path, rows=1000, channels=19):
    """创建示例CSV文件
    
    Args:
        file_path: 文件路径
        rows: 行数
        channels: 通道数
    """
    # 创建随机数据
    data = np.random.normal(0, 100, (rows, channels))
    
    # 创建DataFrame
    columns = [f"Channel_{i+1}" for i in range(channels)]
    df = pd.DataFrame(data, columns=columns)
    
    # 保存为CSV文件
    df.to_csv(file_path, index=False)
    
    return file_path 
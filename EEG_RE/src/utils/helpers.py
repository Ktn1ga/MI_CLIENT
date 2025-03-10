import time
import numpy as np

def bytes_to_hex_string(data):
    """将字节数据转换为十六进制字符串"""
    return ' '.join([f"{b:02X}" for b in data])

def format_timestamp(timestamp):
    """格式化时间戳"""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))

def scale_data(data, old_min, old_max, new_min, new_max):
    """缩放数据范围"""
    if old_max == old_min:
        return np.zeros_like(data) + new_min
    return ((data - old_min) / (old_max - old_min)) * (new_max - new_min) + new_min

def moving_average(data, window_size):
    """计算移动平均"""
    if len(data) < window_size:
        return data
    
    weights = np.ones(window_size) / window_size
    return np.convolve(data, weights, mode='valid')

def find_peaks(data, threshold):
    """查找峰值"""
    peaks = []
    for i in range(1, len(data) - 1):
        if data[i] > threshold and data[i] > data[i-1] and data[i] > data[i+1]:
            peaks.append(i)
    return peaks

def calculate_snr(signal, noise):
    """计算信噪比"""
    if np.sum(noise**2) == 0:
        return float('inf')
    
    signal_power = np.sum(signal**2) / len(signal)
    noise_power = np.sum(noise**2) / len(noise)
    
    if noise_power == 0:
        return float('inf')
    
    return 10 * np.log10(signal_power / noise_power)

def bandpass_filter(data, fs, lowcut, highcut, order=5):
    """带通滤波器"""
    try:
        from scipy.signal import butter, filtfilt
        
        nyq = 0.5 * fs
        low = lowcut / nyq
        high = highcut / nyq
        
        b, a = butter(order, [low, high], btype='band')
        return filtfilt(b, a, data)
    except ImportError:
        # 如果没有安装scipy，返回原始数据
        return data 
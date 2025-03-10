# 脑电信号处理系统 (EEG Processing System)

这是一个完整的脑电信号处理系统，包含信号生成和信号接收两个主要组件。该系统可用于脑机接口研究、脑电信号分析和相关应用开发。

## 系统架构

本系统由两个主要组件组成：

1. **脑电信号发生器 (EEG_GE)** - 生成模拟脑电信号
2. **脑电信号接收器 (EEG_RE)** - 接收、处理和显示脑电信号

## 组件说明

### 脑电信号发生器 (EEG_GE)

脑电信号发生器系统基于Python和PyQt5开发，支持实时生成八通道可调正弦波信号和从CSV文件读取历史脑电数据，通过TCP协议实时输出符合行业标准的脑电数据格式。

**主要功能**：
- 双模式信号生成（实时生成和历史数据读取）
- 基于TCP协议的网络传输
- 可视化界面和实时波形预览
- 可配置的信号参数

详细信息请参阅 [EEG_GE/README.md](EEG_GE/README.md)

### 脑电信号接收器 (EEG_RE)

脑电信号接收器是基于Python和PyQt5开发的应用程序，用于接收、解析、显示和转发脑电信号数据。

**主要功能**：
- 通过TCP连接接收脑电数据
- 自动重连功能
- 实时解析和显示脑电波形
- 支持通过WebSocket转发解析后的数据
- 多通道数据显示和数据记录

详细信息请参阅 [EEG_RE/README.md](EEG_RE/README.md)

## 系统要求

- Python 3.6+
- PyQt5 5.15.0+
- 其他依赖请参见各组件的requirements.txt文件

## 快速开始

1. 克隆仓库：
```bash
git clone <repository-url>
cd MI_CLIENT
```

2. 启动脑电信号发生器：
```bash
cd EEG_GE
pip install -r requirements.txt
python main.py
```

3. 启动脑电信号接收器：
```bash
cd ../EEG_RE
pip install -r requirements.txt
python main.py
```

4. 在接收器界面配置与发生器相同的IP地址和端口，然后点击"连接"。

## 许可证

MIT License 
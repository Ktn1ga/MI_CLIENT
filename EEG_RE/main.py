#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import logging
from PyQt5.QtWidgets import QApplication

from src.views.main_window import MainWindow
from src.controllers.main_controller import MainController

def main():
    """主程序入口"""
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # 创建应用
    app = QApplication(sys.argv)
    
    # 创建主窗口
    main_window = MainWindow()
    
    # 创建控制器
    controller = MainController(main_window)
    
    # 显示主窗口
    main_window.show()
    
    # 运行应用
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
脑电信号发生器系统 - 主程序入口
"""

import sys
from PyQt5.QtWidgets import QApplication
from src.controllers.main_controller import MainController

def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setApplicationName("脑电信号发生器系统")
    
    # 创建主控制器
    controller = MainController()
    controller.show_main_window()
    
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main()) 
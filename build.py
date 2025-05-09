#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import shutil
import subprocess
from datetime import datetime

def check_pyinstaller():
    """检查是否安装了PyInstaller"""
    try:
        import PyInstaller
        return True
    except ImportError:
        return False

def install_pyinstaller():
    """安装PyInstaller"""
    print("正在安装PyInstaller...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        return True
    except subprocess.CalledProcessError as e:
        print(f"安装PyInstaller失败: {e}")
        return False

def build_exe():
    """构建可执行程序"""
    # 检查源文件是否存在
    if not os.path.exists("jtdx_monitor.py"):
        print("错误: 未找到源文件 jtdx_monitor.py")
        return False

    # 创建构建目录
    build_dir = "build"
    dist_dir = "dist"
    for dir_path in [build_dir, dist_dir]:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
        os.makedirs(dir_path)

    # 构建命令
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--clean",
        "--onefile",  # 生成单个可执行文件
        "--name", "jtdx_monitor",
        "--icon", "NONE",  # 不使用图标
        "--add-data", "README.md;.",  # 添加README文件
        "--add-data", "notifiers.py;.",  # 添加通知模块
        "--hidden-import", "queue",
        "--hidden-import", "threading",
        "--hidden-import", "argparse",
        "--hidden-import", "requests",
        "--hidden-import", "urllib.parse",
        "--hidden-import", "abc",
        "jtdx_monitor.py"
    ]

    print("开始构建可执行程序...")
    try:
        subprocess.check_call(cmd)
        
        # 构建成功后，创建发布包
        release_name = f"jtdx_monitor_win64_{datetime.now().strftime('%Y%m%d')}"
        release_dir = os.path.join("dist", release_name)
        os.makedirs(release_dir, exist_ok=True)
        
        # 复制文件到发布目录
        shutil.copy(os.path.join("dist", "jtdx_monitor.exe"), 
                   os.path.join(release_dir, "jtdx_monitor.exe"))
        if os.path.exists("README.md"):
            shutil.copy("README.md", os.path.join(release_dir, "README.md"))
            
        # 创建启动脚本
        with open(os.path.join(release_dir, "启动监控.bat"), "w", encoding="utf-8") as f:
            f.write('@echo off\n')
            f.write('echo JTDX监控程序启动脚本\n')
            f.write('echo.\n')
            f.write('set JTDX_LOG_DIR=.\n')
            f.write('echo 当前监控目录: %JTDX_LOG_DIR%\n')
            f.write('echo.\n')
            f.write('jtdx_monitor.exe -d "%JTDX_LOG_DIR%"\n')
            f.write('pause\n')
            
        # 创建ZIP包
        shutil.make_archive(release_name, 'zip', "dist", release_name)
        print(f"\n构建完成！")
        print(f"可执行文件位置: {os.path.join('dist', release_name, 'jtdx_monitor.exe')}")
        print(f"发布包位置: {release_name}.zip")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"构建失败: {e}")
        return False

def main():
    print("JTDX监控程序构建工具")
    print("=" * 40)
    
    # 检查并安装依赖
    if not check_pyinstaller():
        print("未检测到PyInstaller，准备安装...")
        if not install_pyinstaller():
            print("安装PyInstaller失败，无法继续构建")
            return
    
    # 构建可执行程序
    if build_exe():
        print("\n构建过程完成")
    else:
        print("\n构建过程失败")

if __name__ == "__main__":
    main() 
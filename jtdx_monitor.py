#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import glob
import re
import json
import time
import queue
import threading
import argparse
import requests
import urllib.parse
from datetime import datetime
from typing import Tuple, Optional, Set
from notifiers import BaseNotifier, ServerChanNotifier
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import fnmatch
from message_queue import MessageQueue, Message

class JTDXLogMonitor:
    def __init__(self, log_dir: str, monitor_name: str, notifier: Optional[BaseNotifier] = None,
                 callsign_prefixes: Optional[Set[str]] = None):
        self.log_dir = log_dir
        self.monitor_name = monitor_name
        self.last_position = 0
        self.current_file = None
        self.notifier = notifier
        self.callsign_prefixes = callsign_prefixes or set()
    
    def should_process_callsign(self, callsign: Optional[str]) -> bool:
        """检查呼号是否应该被处理
        
        如果没有设置忽略规则，处理所有呼号
        如果设置了忽略规则，不处理匹配规则的呼号
        """
        if not callsign or not self.callsign_prefixes:
            return bool(callsign)
        
        # 如果呼号匹配任何一个需要忽略的通配符规则，则不处理
        return not any(fnmatch.fnmatch(callsign, pattern) for pattern in self.callsign_prefixes)
    
    def find_latest_log(self) -> Optional[str]:
        """查找最新的JTDX日志文件"""
        pattern = os.path.join(self.log_dir, "[0-9]" * 6 + "_ALL.TXT")
        log_files = glob.glob(pattern)
        if not log_files:
            return None
        return max(log_files)
    
    def parse_ft8_message(self, message: str) -> Tuple[Optional[str], Optional[str]]:
        """解析FT8消息，提取主叫和被叫台站"""
        # 移除解码状态标记
        message = re.sub(r'[*^]$', '', message.strip())
        
        # 忽略包含<...>的消息
        if '<...>' in message:
            return None, None
            
        parts = message.split()
        if not parts:
            return None, None
            
        if parts[0] == 'CQ':
            if len(parts) >= 3:
                # 检查是否是定向CQ（CQ EU VK6KXW OF87）
                if len(parts[1]) <= 4 and parts[1].isalpha():
                    # 定向CQ，第三部分是呼号
                    return parts[2], None
                # 普通CQ，第二部分是呼号
                return parts[1], None
        else:
            # 定向呼叫格式：被叫 主叫 信息
            if len(parts) >= 2:
                return parts[1], parts[0]
                
        return None, None
    
    def process_line(self, line: str) -> Optional[Tuple[str, str, str]]:
        """处理单行日志"""
        # 匹配解码行
        decode_pattern = r'^(\d{8}_\d{6})\s+(-?\d+)\s+(-?\d+(?:\.\d)?)\s+([0-9]|[1-9]\d{1,2}|1\d{3}|2\d{3}|3[0-4]\d{2}|3500)\s+~\s+(.+)$'
        match = re.match(decode_pattern, line.strip())
        
        if not match:
            return None
            
        timestamp, snr, dt, freq, message_and_status = match.groups()
        # 分离正文和状态标记
        if message_and_status and message_and_status[-1] in ('*', '^'):
            message = message_and_status[:-1]
        else:
            message = message_and_status
        caller, called = self.parse_ft8_message(message)
        
        # 检查呼号是否需要处理
        should_process_caller = self.should_process_callsign(caller)
        should_process_called = self.should_process_callsign(called)
        
        # 如果两个呼号都不需要处理，直接返回
        if not (should_process_caller or should_process_called):
            return None
        
        # 如果配置了消息队列，添加消息
        if self.notifier and caller:
            # 只添加主叫方呼号
            self.notifier.add_message(Message(caller))
        
        if caller or called:
            return timestamp, caller, called
        return None
    
    def monitor(self):
        """监控日志文件的新内容"""
        current_file = self.find_latest_log()
        if not current_file:
            print("未找到日志文件")
            return
            
        if current_file != self.current_file:
            if self.current_file:
                print(f"\n切换到新日志文件: {os.path.basename(current_file)}")
            else:
                print(f"开始监控日志文件: {os.path.basename(current_file)}")
            self.current_file = current_file
            self.last_position = os.path.getsize(current_file)
            return
            
        try:
            with open(current_file, 'r', encoding='utf-8') as f:
                file_size = os.path.getsize(current_file)
                if file_size < self.last_position:
                    # 文件被截断，重置位置
                    print(f"文件被截断，重新开始监控: {os.path.basename(current_file)}")
                    self.last_position = 0
                if file_size > self.last_position:
                    f.seek(self.last_position)
                    while True:
                        try:
                            line = f.readline()
                            if not line:
                                break
                            result = self.process_line(line)
                            if result:
                                timestamp, caller, called = result
                                dt = datetime.strptime(timestamp, '%Y%m%d_%H%M%S')
                                time_str = dt.strftime('%H:%M:%S')
                                if called:
                                    print(f"{time_str} - 定向呼叫: {caller} -> {called}")
                                else:
                                    print(f"{time_str} - CQ呼叫: {caller}")
                        except UnicodeDecodeError as e:
                            print(f"警告：跳过一行无法解码的日志（utf-8错误）：{e}")
                            continue
                    self.last_position = file_size
        except Exception as e:
            print(f"处理日志文件时出错: {e}")

class LogFileEventHandler(FileSystemEventHandler):
    def __init__(self, monitor: JTDXLogMonitor):
        self.monitor = monitor

    def on_modified(self, event):
        # 只处理文件修改事件
        if not event.is_directory and event.src_path.endswith('_ALL.TXT'):
            # 只处理最新日志文件
            if os.path.abspath(event.src_path) == os.path.abspath(self.monitor.current_file):
                self.monitor.monitor()  # 只处理新增内容

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='JTDX日志文件监控工具')
    parser.add_argument('-d', '--directory', 
                      default='.',
                      help='指定要监控的日志文件目录，默认为当前目录')
    parser.add_argument('-n', '--name',
                      default='JTDX监控',
                      help='监控程序名称，用于消息标题显示')
    parser.add_argument('--ignore-call',
                      action='append',
                      help='要忽略的呼号（支持通配符），可多次使用此参数指定多个要忽略的呼号')
    parser.add_argument('-i', '--interval',
                      type=int,
                      default=120,
                      help='消息发送间隔（秒），默认120秒')
    
    parser.add_argument('-t', '--tags',
                      default='',
                      help='消息标签，用于消息分类')
    

    parser.add_argument('--send-key',
                                default='sctp7164t4xjfgxv8vmzykvhim58szd',
                               help='Server酱发送密钥')
    
    args = parser.parse_args()
    
    # 检查目录是否存在
    if not os.path.isdir(args.directory):
        print(f"错误：目录 '{args.directory}' 不存在")
        return
    
        
    # 初始化通知器
    notifier = None
    if args.send_key:
        notifier = ServerChanNotifier(
            name=args.name,
            send_key=args.send_key,
            send_interval=args.interval,
            tags=args.tags
        )
        print("Server酱消息推送已启用")
    if not notifier:
        print("错误：Server酱配置不完整，请检查 send-key 参数")
        parser.print_help()
        return
    
    print(f"消息发送间隔：{args.interval}秒")
    
    # 处理呼号前缀
    callsign_prefixes = set(args.ignore_call) if args.ignore_call else None
    
    # 创建监控器实例
    monitor = JTDXLogMonitor(args.directory, args.name, notifier, callsign_prefixes)
    
    print(f"开始监控目录: {os.path.abspath(args.directory)}")
    print(f"监控名称: {args.name}")
    if callsign_prefixes:
        print(f"忽略呼号规则: {', '.join(sorted(callsign_prefixes))}")
    
    # 启动watchdog监控
    event_handler = LogFileEventHandler(monitor)
    observer = Observer()
    observer.schedule(event_handler, path=args.directory, recursive=False)
    observer.start()
    print(f"使用watchdog实时监控目录: {os.path.abspath(args.directory)}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        if monitor.notifier:
            print("\n正在发送剩余消息...")
            monitor.notifier.flush()
        print("\n停止监控")
    observer.join()

if __name__ == '__main__':
    main() 
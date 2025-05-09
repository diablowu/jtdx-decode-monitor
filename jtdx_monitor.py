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
from notifiers import BaseNotifier, WeChatWorkNotifier, ServerChanNotifier

class WeChatWorkAPI:
    """企业微信API封装"""
    def __init__(self, corp_id: str, agent_id: str, secret: str, to_user: str):
        self.corp_id = corp_id
        self.agent_id = agent_id
        self.secret = secret
        self.access_token = None
        self.token_expires = 0
        self.base_url = 'https://qyapi.weixin.qq.com'
        self.to_user = to_user
        
        # 启动token刷新线程
        self._start_token_refresh_thread()
    
    def _get_access_token(self) -> str:
        """获取access token"""
        url = urllib.parse.urljoin(self.base_url, '/cgi-bin/gettoken')
        params = {
            'corpid': self.corp_id,
            'corpsecret': self.secret
        }
        
        try:
            response = requests.get(url=url, params=params).json()
            if response.get('errcode') == 0:
                self.access_token = response['access_token']
                self.token_expires = time.time() + 7200  # token有效期2小时
                return self.access_token
            else:
                print(f"获取access token失败: {response}")
                return None
        except Exception as e:
            print(f"获取access token出错: {e}")
            return None
    
    def _refresh_token(self):
        """刷新access token的线程函数"""
        while True:
            self._get_access_token()
            # 每小时刷新一次
            time.sleep(3600)
    
    def _start_token_refresh_thread(self):
        """启动token刷新线程"""
        self._get_access_token()  # 先获取一次token
        thread = threading.Thread(target=self._refresh_token, daemon=True)
        thread.start()
    
    def send_message(self, content: str) -> bool:
        """发送文本消息"""
        if not self.access_token:
            return False
            
        url = urllib.parse.urljoin(self.base_url, 
              f'/cgi-bin/message/send?access_token={self.access_token}')
        
        data = {
            'touser': self.to_user,
            'msgtype': 'text',
            'agentid': self.agent_id,
            'text': {
                'content': content
            }
        }
        
        try:
            response = requests.post(url=url, json=data).json()
            if response.get('errcode') == 0:
                return True
            else:
                print(f"发送消息失败: {response}")
                return False
        except Exception as e:
            print(f"发送消息出错: {e}")
            return False

class MessageQueue:
    """消息队列管理"""
    def __init__(self, wechat_api, monitor_name: str):
        self.queue = queue.Queue()
        self.wechat_api = wechat_api
        self.monitor_name = monitor_name
        self.message_set: Set[str] = set()  # 用于消息去重
        self._start_send_thread()
    
    def add_message(self, message: str):
        """添加消息到队列"""
        if message not in self.message_set:
            self.queue.put(message)
            self.message_set.add(message)
    
    def _send_messages(self):
        """发送队列中的消息"""
        messages = []
        try:
            # 取出队列中所有消息
            while not self.queue.empty():
                messages.append(self.queue.get_nowait())
                self.queue.task_done()
            
            if messages:
                # 清空消息集合
                self.message_set.clear()
                
                # 发送消息
                title = f"{self.monitor_name}解码消息[{len(messages)}条]"
                content = "\n".join(messages)
                full_message = f"{title}\n{content}"
                
                if self.wechat_api:
                    self.wechat_api.send_message(full_message)
                    print(f"已发送 {len(messages)} 条消息")
        except Exception as e:
            print(f"发送消息时出错: {e}")
            # 如果发送失败，将消息放回队列
            for msg in messages:
                self.queue.put(msg)
    
    def _send_thread(self):
        """消息发送线程"""
        while True:
            try:
                self._send_messages()
                # 每两分钟执行一次
                time.sleep(120)
            except Exception as e:
                print(f"消息发送线程出错: {e}")
                time.sleep(120)  # 发生错误时也等待两分钟
    
    def _start_send_thread(self):
        """启动消息发送线程"""
        thread = threading.Thread(target=self._send_thread, daemon=True)
        thread.start()
    
    def flush(self):
        """立即发送所有待发送的消息"""
        self._send_messages()

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
        
        如果没有设置忽略前缀，处理所有呼号
        如果设置了忽略前缀，不处理匹配前缀的呼号
        """
        if not callsign or not self.callsign_prefixes:
            return bool(callsign)
        
        # 如果呼号以任何一个需要忽略的前缀开头，则不处理
        return not any(callsign.startswith(prefix) for prefix in self.callsign_prefixes)
    
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
            self.notifier.add_message(caller)
        
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
                    for line in f:
                        result = self.process_line(line)
                        if result:
                            timestamp, caller, called = result
                            dt = datetime.strptime(timestamp, '%Y%m%d_%H%M%S')
                            time_str = dt.strftime('%H:%M:%S')
                            if called:
                                print(f"{time_str} - 定向呼叫: {caller} -> {called}")
                            else:
                                print(f"{time_str} - CQ呼叫: {caller}")
                    
                    self.last_position = file_size
                    
        except Exception as e:
            print(f"处理日志文件时出错: {e}")

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='JTDX日志文件监控工具')
    parser.add_argument('-d', '--directory', 
                      default='.',
                      help='指定要监控的日志文件目录，默认为当前目录')
    parser.add_argument('-n', '--name',
                      default='JTDX监控',
                      help='监控程序名称，用于消息标题显示')
    parser.add_argument('-p', '--prefix',
                      action='append',
                      help='要忽略的呼号前缀，可多次使用此参数指定多个要忽略的前缀')
    parser.add_argument('-i', '--interval',
                      type=int,
                      default=120,
                      help='消息发送间隔（秒），默认120秒')
    
    # 通知方式选择
    notify_group = parser.add_mutually_exclusive_group()
    notify_group.add_argument('--wechat',
                          action='store_true',
                          help='使用企业微信通知')
    notify_group.add_argument('--serverchan',
                          action='store_true',
                          help='使用Server酱通知')
    
    # 企业微信参数
    wechat_group = parser.add_argument_group('企业微信配置')
    wechat_group.add_argument('--corp-id',
                           default="wx861828161a3f015c",
                           help='企业微信企业ID')
    wechat_group.add_argument('--agent-id',
                           default="1000002",
                           help='企业微信应用ID')
    wechat_group.add_argument('--secret',
                           default="q7EFHBUKk-S1pNBWD0pDXuYjDzahLZ2VaxQ7QfBrYeU",
                           help='企业微信应用Secret')
    wechat_group.add_argument('--to-user',
                           default="wubo16",
                           help='企业微信消息接收人，多个接收人用|分隔')
    
    # Server酱参数
    serverchan_group = parser.add_argument_group('Server酱配置')
    serverchan_group.add_argument('--send-key',
                                default='sctp7164t4xjfgxv8vmzykvhim58szd',
                               help='Server酱发送密钥')
    
    args = parser.parse_args()
    
    # 检查目录是否存在
    if not os.path.isdir(args.directory):
        print(f"错误：目录 '{args.directory}' 不存在")
        return
    
    # 检查通知方式配置
    if not (args.wechat or args.serverchan):
        print("错误：未指定通知方式，请使用 --wechat 或 --serverchan 选择一种通知方式")
        parser.print_help()
        return
        
    # 初始化通知器
    notifier = None
    if args.wechat and all([args.corp_id, args.agent_id, args.secret, args.to_user]):
        notifier = WeChatWorkNotifier(
            name=args.name,
            corp_id=args.corp_id,
            agent_id=args.agent_id,
            secret=args.secret,
            to_user=args.to_user,
            send_interval=args.interval
        )
        print("企业微信消息推送已启用")
    elif args.serverchan and args.send_key:
        notifier = ServerChanNotifier(
            name=args.name,
            send_key=args.send_key,
            send_interval=args.interval
        )
        print("Server酱消息推送已启用")
        
    if not notifier:
        if args.wechat:
            print("错误：企业微信配置不完整，请检查 corp-id、agent-id、secret 和 to-user 参数")
        elif args.serverchan:
            print("错误：Server酱配置不完整，请检查 send-key 参数")
        parser.print_help()
        return
    
    print(f"消息发送间隔：{args.interval}秒")
    
    # 处理呼号前缀
    callsign_prefixes = set(args.prefix) if args.prefix else None
    
    # 创建监控器实例
    monitor = JTDXLogMonitor(args.directory, args.name, notifier, callsign_prefixes)
    
    print(f"开始监控目录: {os.path.abspath(args.directory)}")
    print(f"监控名称: {args.name}")
    if callsign_prefixes:
        print(f"忽略呼号前缀: {', '.join(sorted(callsign_prefixes))}")
    
    while True:
        try:
            monitor.monitor()
            # 每秒检查一次新内容
            time.sleep(1)
        except KeyboardInterrupt:
            # 发送剩余的消息
            if monitor.notifier:
                print("\n正在发送剩余消息...")
                monitor.notifier.flush()
            print("\n停止监控")
            break
        except Exception as e:
            print(f"发生错误: {e}")
            break

if __name__ == '__main__':
    main() 
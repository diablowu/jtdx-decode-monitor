#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import abc
import time
import queue
import threading
import requests
import urllib.parse
from typing import Optional, Set

class BaseNotifier(abc.ABC):
    """通知器抽象基类"""
    
    def __init__(self, name: str, send_interval: int = 120, tags: str = ""):
        self.name = name
        self.send_interval = send_interval
        self.message_queue = queue.Queue()
        self.message_set: Set[str] = set()  # 用于消息去重
        self._start_send_thread()
        self.tags = tags
    
    @abc.abstractmethod
    def send_message(self, content: str) -> bool:
        """发送消息的具体实现"""
        pass
    
    def add_message(self, message: str):
        """添加消息到队列"""
        if message not in self.message_set:
            self.message_queue.put(message)
            self.message_set.add(message)
    
    def _send_messages(self):
        """发送队列中的消息"""
        messages = []
        try:
            # 取出队列中所有消息
            while not self.message_queue.empty():
                messages.append(self.message_queue.get_nowait())
                self.message_queue.task_done()
            
            if messages:
                # 清空消息集合
                self.message_set.clear()
                
                # 发送消息
                title = f"{self.name}解码消息[{len(messages)}条]"
                content = "\n".join(f'{i+1}. {m}' for i, m in enumerate(messages))
                full_message = f"{title}\n{content}"
                
                if self.send_message(full_message):
                    print(f"已发送 {len(messages)} 条消息")
                else:
                    # 发送失败，将消息放回队列
                    for msg in messages:
                        self.message_queue.put(msg)
                    
        except Exception as e:
            print(f"发送消息时出错: {e}")
            # 如果发送失败，将消息放回队列
            for msg in messages:
                self.message_queue.put(msg)
    
    def _send_thread(self):
        """消息发送线程"""
        while True:
            try:
                self._send_messages()
                # 使用配置的发送间隔
                time.sleep(self.send_interval)
            except Exception as e:
                print(f"消息发送线程出错: {e}")
                time.sleep(self.send_interval)  # 发生错误时也使用配置的间隔
    
    def _start_send_thread(self):
        """启动消息发送线程"""
        thread = threading.Thread(target=self._send_thread, daemon=True)
        thread.start()
    
    def flush(self):
        """立即发送所有待发送的消息"""
        self._send_messages()

class ServerChanNotifier(BaseNotifier):
    """Server酱通知实现"""
    
    def __init__(self, name: str, send_key: str, send_interval: int = 120):
        super().__init__(name, send_interval)
        self.send_key = send_key
        self.base_url = "https://sctapi.ftqq.com"
    
    def send_message(self, content: str) -> bool:
        """发送Server酱消息"""
        url = f"{self.base_url}/{self.send_key}.send"
        
        # 将消息拆分为标题和内容
        lines = content.split('\n', 1)
        title = lines[0]
        desp = lines[1] if len(lines) > 1 else ""
        
        data = {
            'title': title,
            'desp': desp,
            'tags': self.tags if self.tags else self.name,
        }
        
        try:
            response = requests.post(url, data=data).json()
            if response.get('code') == 0:
                return True
            else:
                print(f"发送Server酱消息失败: {response}")
                return False
        except Exception as e:
            print(f"发送Server酱消息出错: {e}")
            return False 
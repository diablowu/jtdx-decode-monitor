import queue
import threading
import time
from typing import Set


class MessageQueue:
    """消息队列管理"""
    def __init__(self, wechat_api, monitor_name: str):
        self.queue = queue.Queue()
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
                content = "\n".join(str(m) for m in messages)
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

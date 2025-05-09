#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import random
import argparse
from datetime import datetime, timedelta

class TestLogGenerator:
    """测试日志生成器"""
    
    def __init__(self, output_file: str, append_mode: bool = True):
        self.output_file = output_file
        self.append_mode = append_mode
        
        # 如果是追加模式，从文件最后的时间戳开始
        if self.append_mode and os.path.exists(self.output_file):
            self.current_time = self._get_last_timestamp()
        else:
            self.current_time = datetime.utcnow()
        
        # 模拟数据
        self.callsigns = [
            "BI1QXR", "VR2CO", "BD3CT", "BI1TMQ", "BD7IS",
            "BP12GOLD", "BG4WOM", "BH4WHQ", "BA1PK", "BG1QMY",
            "VK6KXW", "JA1XYZ", "W1ABC", "EA3XYZ"
        ]
        self.grids = ["OM89", "OL72", "OM98", "PM01", "ON80", "OF87"]
        self.directions = ["EU", "AS", "NA", "SA", "OC", "AF", "DX", "JA"]
        self.snr_range = (-21, 5)
        self.freq_range = (1000, 2500)
    
    def _get_last_timestamp(self) -> datetime:
        """获取文件中最后一行的时间戳"""
        try:
            with open(self.output_file, 'r', encoding='utf-8') as f:
                # 从文件末尾读取最后1024字节
                f.seek(0, 2)
                file_size = f.tell()
                chunk_size = min(1024, file_size)
                f.seek(max(0, file_size - chunk_size))
                lines = f.readlines()
                
                if lines:
                    last_line = lines[-1].strip()
                    # 尝试解析时间戳
                    try:
                        timestamp_str = last_line.split()[0]
                        return datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    except (IndexError, ValueError):
                        pass
        except Exception as e:
            print(f"读取最后时间戳出错: {e}")
        
        # 如果无法获取最后时间戳，使用当前时间
        return datetime.utcnow()
    
    def generate_timestamp(self) -> str:
        """生成时间戳"""
        timestamp = self.current_time.strftime("%Y%m%d_%H%M%S")
        # 随机增加1-5秒
        self.current_time += timedelta(seconds=random.randint(1, 5))
        return timestamp
    
    def generate_cq_message(self) -> str:
        """生成CQ消息"""
        callsign = random.choice(self.callsigns)
        grid = random.choice(self.grids)
        
        # 30%概率生成定向CQ
        if random.random() < 0.3:
            direction = random.choice(self.directions)
            return f"CQ {direction} {callsign} {grid}"
        
        return f"CQ {callsign} {grid}"
    
    def generate_directed_message(self) -> str:
        """生成定向呼叫消息"""
        caller = random.choice(self.callsigns)
        called = random.choice(self.callsigns)
        while caller == called:  # 避免自己呼叫自己
            called = random.choice(self.callsigns)
            
        message_types = [
            f"{called} {caller} {random.choice(self.grids)}",
            f"{called} {caller} R-15",
            f"{called} {caller} RRR",
            f"{called} {caller} 73",
            f"{called} {caller} RR73"
        ]
        return random.choice(message_types)
    
    def generate_line(self) -> str:
        """生成一行日志"""
        timestamp = self.generate_timestamp()
        snr = random.randint(*self.snr_range)
        # dt可以为0或正负一位小数
        dt = random.choice([0] + [round(x * 0.1, 1) for x in range(-9, 10) if x != 0])
        freq = random.randint(0, 3500)
        # 80%概率生成定向呼叫，20%概率生成CQ
        message = self.generate_directed_message() if random.random() < 0.8 else self.generate_cq_message()
        # 状态标记只可能为*、^或空
        status = random.choice(["*", "^", ""]) 
        return f"{timestamp}  {snr:3d}  {dt:+.1f} {freq} ~ {message}{status}\n"
    
    def generate_complex_message(self) -> str:
        """生成复杂消息（包含<...>）"""
        timestamp = self.generate_timestamp()
        snr = random.randint(*self.snr_range)
        dt = random.choice([0] + [round(x * 0.1, 1) for x in range(-9, 10) if x != 0])
        freq = random.randint(0, 3500)
        message = f"<...> {random.choice(self.callsigns)} {random.randint(-20, -10)}"
        status = random.choice(["*", "^", ""]) 
        return f"{timestamp}  {snr:3d}  {dt:+.1f} {freq} ~ {message}{status}\n"
    
    def run(self):
        """运行生成器"""
        mode = "追加" if self.append_mode else "覆盖"
        print(f"开始{mode}生成测试日志到文件: {self.output_file}")
        
        try:
            # 如果不是追加模式且文件存在，先清空文件
            if not self.append_mode and os.path.exists(self.output_file):
                open(self.output_file, 'w').close()
                print(f"已清空文件: {self.output_file}")
            
            while True:
                # 95%概率生成普通消息，5%概率生成复杂消息
                line = (self.generate_line() if random.random() < 0.95 
                       else self.generate_complex_message())
                
                with open(self.output_file, 'a', encoding='utf-8') as f:
                    f.write(line)
                    f.flush()  # 确保立即写入文件
                print(line.strip())
                
                # 随机等待1-5秒
                wait_time = random.uniform(1, 5)
                time.sleep(wait_time)
                
        except KeyboardInterrupt:
            print("\n停止生成测试日志")
        except Exception as e:
            print(f"生成测试日志时出错: {e}")

def main():
    parser = argparse.ArgumentParser(description='JTDX日志文件生成器')
    parser.add_argument('-o', '--output',
                      default='test_202504_ALL.TXT',
                      help='输出文件名，默认为test_202504_ALL.TXT')
    parser.add_argument('-a', '--append',
                      action='store_true',
                      default=True,
                      help='追加到现有文件（默认）')
    parser.add_argument('-n', '--new',
                      action='store_true',
                      help='创建新文件（如果文件存在则清空）')
    
    args = parser.parse_args()
    
    # 确保输出目录存在
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 如果指定了--new，则不使用追加模式
    append_mode = not args.new
    
    generator = TestLogGenerator(args.output, append_mode)
    generator.run()

if __name__ == '__main__':
    main() 
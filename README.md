# JTDX监控程序

这是一个用于监控JTDX日志文件的工具，可以实时显示解码的FT8消息，并支持多种通知推送方式。

## 功能特点

- 实时监控JTDX日志文件
- 解析FT8消息中的主叫和被叫台站
- 支持忽略指定前缀的呼号
- 支持多种消息推送方式：
  - 企业微信应用消息
  - Server酱推送
- 消息自动去重和批量发送

## 使用方法

1. 直接运行：
   - 双击"启动监控.bat"即可在当前目录监控JTDX日志文件

2. 命令行参数：
   ```bash
   jtdx_monitor.exe -d "日志目录路径" -n "监控名称" -p "要忽略的呼号前缀"
   ```

   主要参数说明：
   - `-d, --directory`: 指定要监控的日志文件目录，默认为当前目录
   - `-n, --name`: 监控程序名称，用于消息标题显示
   - `-p, --prefix`: 要忽略的呼号前缀，可多次使用此参数指定多个要忽略的前缀

3. 通知推送配置：

   a) 企业微信推送：
   ```bash
   jtdx_monitor.exe --wechat --corp-id "企业ID" --agent-id "应用ID" --secret "应用Secret" --to-user "接收人"
   ```

   b) Server酱推送：
   ```bash
   jtdx_monitor.exe --serverchan --send-key "发送密钥"
   ```

## 示例

1. 监控指定目录：
   ```bash
   jtdx_monitor.exe -d "D:\JTDX\log"
   ```

2. 忽略特定前缀的呼号：
   ```bash
   jtdx_monitor.exe -p BY4 -p BG -p BD7
   ```

3. 使用企业微信推送：
   ```bash
   jtdx_monitor.exe -d "D:\JTDX\log" -n "JTDX监控" --wechat --corp-id "wx123456" --agent-id "1000001" --secret "abcdef" --to-user "user1|user2"
   ```

4. 使用Server酱推送：
   ```bash
   jtdx_monitor.exe -d "D:\JTDX\log" -n "JTDX监控" --serverchan --send-key "SCT123456..."
   ```

## 注意事项

1. 程序需要持续运行才能监控日志文件
2. 消息每2分钟批量发送一次
3. 企业微信推送配置：
   - 需要在企业微信管理后台创建应用
   - 需要正确配置企业ID、应用ID和Secret
   - 接收人可以使用"|"分隔多个用户ID
4. Server酱推送配置：
   - 需要在Server酱官网注册并获取发送密钥
   - 支持微信、企业微信、钉钉等多种推送渠道
5. 建议使用启动脚本运行程序，方便查看运行状态 
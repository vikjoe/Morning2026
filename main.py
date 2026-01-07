import os
import requests
from datetime import datetime
import pytz

def send_morning_greeting():
    # 获取环境变量中的 Token
    # 这里我们默认使用 "PushPlus" 服务，因为它对个人微信推送支持较好
    # 你需要在 GitHub Secrets 中设置 PUSHPLUS_TOKEN
    token = os.environ.get("PUSHPLUS_TOKEN")
    
    if not token:
        print("错误: 未在环境变量中找到 PUSHPLUS_TOKEN。")
        print("请确保在 GitHub 仓库的 Settings -> Secrets and variables -> Actions 中添加了 PUSHPLUS_TOKEN。")
        # 为了防止 Workflow 失败（如果只是测试运行），这里可以抛出异常或者仅打印
        # 如果是生产环境，建议抛出异常以便通知
        return

    # 设置时区为北京时间
    tz = pytz.timezone('Asia/Shanghai')
    now = datetime.now(tz)
    date_str = now.strftime('%Y-%m-%d %H:%M:%S')
    
    # 消息内容
    title = "早上好！"
    content = f"现在是北京时间 {date_str}。<br>新的一天开始了，祝你今天心情愉快！<br><br>From: Morning2026 Project"
    
    # PushPlus API
    # 官方文档: https://www.pushplus.plus/doc/
    url = "http://www.pushplus.plus/send"
    data = {
        "token": token,
        "title": title,
        "content": content,
        "template": "html"
    }
    
    try:
        response = requests.post(url, json=data)
        result = response.json()
        if result.get("code") == 200:
            print("消息推送成功！")
        else:
            print(f"消息推送失败: {result}")
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == "__main__":
    send_morning_greeting()

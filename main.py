import os
import requests
from datetime import datetime, timedelta
import pytz
from bs4 import BeautifulSoup

# 配置需要监控的商品及其对应的生意社URL
# 如果需要添加其他商品，请先找到生意社该商品的列表页URL (类似 plist-1-xxx-1.html)
COMMODITY_URLS = {
    "丁二烯": "https://www.100ppi.com/mprice/plist-1-369-1.html"
}

def get_price_data(name, url):
    """
    爬取指定商品的报价信息，返回最近两天的记录列表
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    results = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8' # 生意社通常是utf-8
        
        if response.status_code != 200:
            print(f"[{name}] 请求失败，状态码: {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        # 根据之前的分析，表格通常是 table.lp-table
        # 或者直接找主要的 table
        table = soup.find('table')
        if not table:
            print(f"[{name}] 未找到数据表格")
            return []

        rows = table.find_all('tr')
        if len(rows) < 2:
            return []

        # 获取当前时间，用于比较日期
        tz = pytz.timezone('Asia/Shanghai')
        now = datetime.now(tz)
        today = now.date()
        two_days_ago = today - timedelta(days=2)

        # 跳过表头，从第2行开始
        for row in rows[1:]:
            cols = row.find_all('td')
            if len(cols) < 8:
                continue
            
            # 解析字段 (基于之前的 Browser Agent 分析)
            # 0: Name (Product Name)
            # 1: Specification (规格)
            # 2: Brand/Origin (品牌/产地)
            # 3: Price (价格) - index 3 is 4th column
            # 4: Type (报价类型)
            # 5: Location (交货地)
            # 6: Company (交易商)
            # 7: Date (日期) - index 7 is 8th column
            
            product_name = cols[0].get_text(strip=True)
            spec = cols[1].get_text(strip=True)
            price = cols[3].get_text(strip=True)
            company = cols[6].get_text(strip=True)
            date_str = cols[7].get_text(strip=True)

            # 简单的日期过滤
            try:
                # 假设日期格式为 YYYY-MM-DD
                row_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                
                # 保留最近两天的记录 (>= today - 2 days)
                if row_date >= two_days_ago:
                    results.append({
                        "name": product_name,
                        "spec": spec,
                        "price": price,
                        "company": company,
                        "date": date_str
                    })
            except ValueError:
                # 解析日期失败可能不是数据行
                continue
                
    except Exception as e:
        print(f"[{name}] 爬取发生错误: {e}")
        
    return results

def send_price_alert():
    token = os.environ.get("PUSHPLUS_TOKEN")
    if not token:
        print("错误: 未找到 PUSHPLUS_TOKEN，跳过推送。")
        return

    # 1. 获取数据
    all_data = []
    for name, url in COMMODITY_URLS.items():
        print(f"正在获取 {name} 的报价...")
        data = get_price_data(name, url)
        all_data.extend(data)

    if not all_data:
        print("没有获取到最近两天的新数据，不发送推送。")
        return

    # 2. 构造消息内容 (HTML)
    tz = pytz.timezone('Asia/Shanghai')
    now_str = datetime.now(tz).strftime('%Y-%m-%d %H:%M')
    
    title = f"商品报价更新 ({now_str})"
    content = f"<h3>生意社商品最新报价 ({now_str})</h3>"
    
    # 将数据按表格展示
    content += """
    <table border="1" style="border-collapse: collapse; width: 100%;">
        <tr style="background-color: #f2f2f2;">
            <th>商品</th>
            <th>规格</th>
            <th>价格</th>
            <th>商家</th>
            <th>日期</th>
        </tr>
    """
    
    for item in all_data:
        content += f"""
        <tr>
            <td>{item['name']}</td>
            <td>{item['spec']}</td>
            <td style="color: red; font-weight: bold;">{item['price']}</td>
            <td>{item['company']}</td>
            <td>{item['date']}</td>
        </tr>
        """
    content += "</table>"
    content += "<p>数据来源: 生意社 (100ppi.com)</p>"

    # 3. 推送
    url = "http://www.pushplus.plus/send"
    payload = {
        "token": token,
        "title": title,
        "content": content,
        "template": "html"
    }
    
    try:
        resp = requests.post(url, json=payload)
        print(f"推送结果: {resp.text}")
    except Exception as e:
        print(f"推送异常: {e}")

if __name__ == "__main__":
    send_price_alert()

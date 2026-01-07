import os
import requests
import io
from datetime import datetime, timedelta
import pytz
from bs4 import BeautifulSoup
import yaml
import glob

# 默认设置
CONFIG_DIR = "COMM-CFG"
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")

def load_configs():
    """从 COMM-CFG 目录加载所有 yaml 配置文件"""
    configs = []
    if not os.path.exists(CONFIG_DIR):
        print(f"配置文件目录 {CONFIG_DIR} 不存在")
        return configs

    for file_path in glob.glob(os.path.join(CONFIG_DIR, "*.yaml")):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                if config and 'name' in config and 'url' in config:
                    configs.append(config)
                else:
                    print(f"Skipping invalid config: {file_path}")
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
    return configs

def get_price_data(config):
    """根据配置爬取数据，并进行关键词过滤"""
    name = config.get('name')
    url = config.get('url')
    invalid_keywords = config.get('invalid_keywords', []) or []
    
    print(f"正在获取 {name} 的报价信息...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    all_prices = []
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            print(f"[{name}] 请求失败: {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table') # 假设主要数据还在第一个table或特定class
        if not table:
             # 尝试找 class="lp-table"
            table = soup.find('table', class_='lp-table')
        
        if not table:
            print(f"[{name}] 未找到数据表格")
            return []

        rows = table.find_all('tr')
        if len(rows) < 2:
            return []

        # 解析数据
        for row in rows[1:]:
            cols = row.find_all('td')
            if len(cols) < 8:
                continue
            
            # 解析原始文本
            product_name = cols[0].get_text(strip=True)
            spec = cols[1].get_text(strip=True)
            price = cols[3].get_text(strip=True)
            company = cols[6].get_text(strip=True)
            date_str = cols[7].get_text(strip=True)
            
            # 1. 关键词过滤 (如果包含无效关键字，直接跳过)
            # 检查字段: 商品名、规格、商家、价格
            full_text = f"{product_name} {spec} {price} {company}"
            is_invalid = False
            for kw in invalid_keywords:
                if kw in full_text:
                    is_invalid = True
                    break
            
            if is_invalid:
                continue
                
            # 2. 格式化数据
            try:
                row_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                all_prices.append({
                    "name": name, # 使用配置中的统称
                    "raw_name": product_name,
                    "spec": spec,
                    "price": price,
                    "company": company,
                    "date": row_date,
                    "date_str": date_str
                })
            except ValueError:
                continue

    except Exception as e:
        print(f"[{name}] 爬取异常: {e}")

    return all_prices

def organize_data(all_prices):
    """
    整理数据:
    1. 分离 '今日'(Today) 和 '昨日'(Yesterday)。
    2. 昨日数据只取最后3条有效报价。
    3. 全部按时间倒序排列 (越新越上面)。
    """
    tz = pytz.timezone('Asia/Shanghai')
    today = datetime.now(tz).date()
    yesterday = today - timedelta(days=1)
    
    today_data = []
    yesterday_data = []
    
    for item in all_prices:
        if item['date'] == today:
            today_data.append(item)
        elif item['date'] == yesterday:
            yesterday_data.append(item)
    
    # 排序: 越新越上面 (日期其实是一样的，这里主要依赖原始网页顺序，通常网页是倒序的吗？)
    # 假设网页是按时间倒序(最新在最上)，或者正序。
    # 生意社列表通常是 最新在最上。我们保持列表顺序即可，或者显式依赖抓取顺序。
    # 这里我们信任网页顺序，但为了保险，不做额外排序，假设爬虫抓下来是从上到下的。
    # 如果需要时间排序，需要更精确的时间字段，但网页只有日期。
    
    # 按照需求：越新的在上面。
    # 生意社默认是从上往下是：最新 -> 最旧。
    # 所以 list[0] 是最新的。
    
    # 昨日数据：取“最后三条有效报价”。
    # “最后”在时间轴上意味着“最晚”，即列表的最上面。
    # “三条”
    yesterday_slice = yesterday_data[:3] # 取最新的3条
    
    return today_data, yesterday_slice

def send_notification(today_data, yesterday_data):
    if not PUSHPLUS_TOKEN:
        print("未找到 PUSHPLUS_TOKEN，跳过推送")
        return
        
    if not today_data and not yesterday_data:
        print("今日和昨日均无有效数据，不推送。")
        return

    tz = pytz.timezone('Asia/Shanghai')
    now_str = datetime.now(tz).strftime('%Y-%m-%d %H:%M')
    
    title = f"商品报价日报 ({now_str})"
    
    # 构建 HTML
    # 样式：越新越上面。
    # 我们先展示 Today (Highlight), 然后 Yesterday.
    
    html = f"<h3>📅 报价更新 ({now_str})</h3>"
    
    html += """
    <table border="1" style="border-collapse: collapse; width: 100%; font-size: 14px;">
        <tr style="background-color: #333; color: white;">
            <th>日期</th>
            <th>名称</th>
            <th>价格</th>
            <th>商家</th>
        </tr>
    """
    
    # 1. 今日数据 (HighLight)
    # 背景色淡黄色或淡红色提示
    for item in today_data:
        html += f"""
        <tr style="background-color: #fff9c4; font-weight: bold;">
            <td style="color: #d32f2f;">{item['date_str']} (新)</td>
            <td>{item['raw_name']}<br><span style="font-size:12px;color:gray;">{item['spec']}</span></td>
            <td style="color: red; font-size: 16px;">{item['price']}</td>
            <td>{item['company']}</td>
        </tr>
        """
        
    # 2. 昨日数据 (Greyed out / Normal)
    for item in yesterday_data:
        html += f"""
        <tr style="background-color: #f5f5f5; color: #666;">
            <td>{item['date_str']}</td>
            <td>{item['raw_name']}<br><span style="font-size:12px;color:gray;">{item['spec']}</span></td>
            <td>{item['price']}</td>
            <td>{item['company']}</td>
        </tr>
        """
        
    html += "</table>"
    html += "<p style='font-size:12px; color: gray;'>注: 黄色高亮为今日最新数据，灰色为昨日参考(最近3条)。</p>"
    
    # 发送
    url = "http://www.pushplus.plus/send"
    payload = {
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": html,
        "template": "html"
    }
    
    try:
        resp = requests.post(url, json=payload)
        print(f"推送响应: {resp.text}")
    except Exception as e:
        print(f"推送失败: {e}")

def main():
    configs = load_configs()
    if not configs:
        print("没有找到配置文件。")
        return

    all_fetched_items = []
    
    for config in configs:
        items = get_price_data(config)
        all_fetched_items.extend(items)
        
    # 按商品分组处理，还是汇总处理？
    # 用户需求好像是汇总发一个推送。
    # 但如果为了排序 "越新的报价越在上面"，应该是全局排序。
    
    # 即使是多个商品，也可以混合在一起按日期排。
    # 不过通常我们希望按商品归类。
    # 鉴于目前只有一个商品丁二烯，我们先不做复杂的商品分组，直接全局处理。
    
    today_data, yesterday_data = organize_data(all_fetched_items)
    
    send_notification(today_data, yesterday_data)

if __name__ == "__main__":
    main()

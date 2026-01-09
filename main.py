import os
import requests
import io
import sys
from datetime import datetime, timedelta
import pytz
from bs4 import BeautifulSoup
import yaml
import glob
import json
import hashlib
import subprocess
import smtplib
from email.mime.text import MIMEText
from email.header import Header

# 强制设置终端输出为 UTF-8 编码，防止 Windows 乱码
if sys.stdout.encoding != 'utf-8':
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except Exception:
        pass

# 默认设置
CONFIG_DIR = "COMM-CFG"
DATA_DIR = "data"
RECORD_FILE = os.path.join(DATA_DIR, "processed_records.json")
SINOPEC_HISTORY_FILE = os.path.join(DATA_DIR, "sinopec_butadiene_history.json")
NR_HISTORY_FILE = os.path.join(DATA_DIR, "natural_rubber_history.json")
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")

# 邮件配置 (从环境变量读取)
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_AUTH_CODE = os.environ.get("EMAIL_AUTH_CODE")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER")

def get_sinopec_factory_price():
    """获取中石化丁二烯当日出厂价 (从资讯列表页抓取)"""
    list_url = "https://www.100ppi.com/news/list-14--369-1.html"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    
    tz = pytz.timezone('Asia/Shanghai')
    today = datetime.now(tz)
    # 格式化为 "1月9日" 而不是 "01月09日"，以匹配网页标题
    today_md = f"{today.month}月{today.day}日"
    
    try:
        resp = requests.get(list_url, headers=headers, timeout=15)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 寻找包含 "中石化丁二烯出厂价格" 的标题
        news_items = soup.find_all('div', class_='list-item') or soup.find_all('li')
        target_url = None
        for item in news_items:
            text = item.get_text()
            if today_md in text and "中石化丁2烯出厂价" in text.replace("二", "2") or \
               (today_md in text and "中石化" in text and "丁二烯" in text and "价格" in text):
                link = item.find('a')
                if link and link.get('href'):
                    target_url = link.get('href')
                    if not target_url.startswith('http'):
                        if target_url.startswith('/'):
                            target_url = "https://www.100ppi.com" + target_url
                        else:
                            target_url = "https://www.100ppi.com/" + target_url
                    break
        
        if not target_url:
            print(f"今日 ({today_md}) 尚未发布中石化丁二烯出厂价资讯。")
            return None

        # 进入详情页抓取具体厂家价格
        print(f"发现今日中石化资讯: {target_url}，正在解析详情...")
        detail_resp = requests.get(target_url, headers=headers, timeout=15)
        detail_resp.encoding = 'utf-8'
        detail_soup = BeautifulSoup(detail_resp.text, 'html.parser')
        content = detail_soup.get_text()
        
        # 简单解析逻辑：寻找数字
        # 通常格式: "上海石化执行9100元/吨", "扬子石化执行9100元/吨"
        # 预定义一些常见厂家
        plants = ["上海石化", "扬子石化", "镇海炼化", "广州石化", "茂名石化", "中韩石化", "中科炼化"]
        prices = {}
        for p in plants:
            if p in content:
                # 寻找厂家后面的 4 位数字
                idx = content.find(p)
                import re
                match = re.search(r'(\d{4})', content[idx:idx+50])
                if match:
                    prices[p] = int(match.group(1))
        
        if not prices:
            # 如果没抓到具体的，尝试抓通稿中的统一价格
            match = re.search(r'执行(\d{4})元', content)
            if match:
                prices["中石化(统一)"] = int(match.group(1))
        
        if prices:
            return {
                "date": today.strftime('%Y-%m-%d'),
                "prices": prices,
                "url": target_url
            }
    except Exception as e:
        print(f"抓取中石化出厂价失败: {e}")
    return None

def generate_sinopec_html(today_sinopec, history):
    """为中石化价格生成专门的 HTML 报告"""
    tz = pytz.timezone('Asia/Shanghai')
    now_str = datetime.now(tz).strftime('%Y-%m-%d %H:%M')
    
    html = f"<h2>🚀 中石化丁二烯出厂价更新报告</h2>"
    html += f"<p><b>更新时间:</b> {now_str}</p>"
    
    # 1. 当日详情与对比
    prices = today_sinopec['prices']
    avg_price = sum(prices.values()) / len(prices)
    
    html += "<h3>📍 今日厂家报价</h3>"
    html += '<table border="1" style="border-collapse: collapse; width: 100%; text-align: center;">'
    html += '<tr style="background:#eee;"><th>厂家</th><th>价格 (元/吨)</th><th>状态</th></tr>'
    
    for plant, price in prices.items():
        style = ""
        status = "正常"
        if price != avg_price:
            style = 'style="background-color: #ffcdd2; color: red; font-weight: bold;"'
            status = "⚠️ 价格异常"
        
        html += f'<tr {style}><td>{plant}</td><td>{price}</td><td>{status}</td></tr>'
    html += "</table>"
    
    # 2. 最近7天趋势
    html += "<h3>📈 最近 7 天价格趋势</h3>"
    html += '<table border="1" style="border-collapse: collapse; width: 100%; text-align: center;">'
    html += '<tr style="background:#333; color:white;"><th>日期</th><th>报价</th><th>变动</th></tr>'
    
    # 包含今天及历史前6天
    all_dates = history + [{"date": today_sinopec['date'], "price": int(avg_price)}]
    recent_7 = all_dates[-7:]
    recent_7.reverse() # 最新的在前
    
    for i, entry in enumerate(recent_7):
        price = entry['price']
        change = "持平"
        if i < len(recent_7) - 1:
            prev_price = recent_7[i+1]['price']
            diff = price - prev_price
            if diff > 0: change = f'<span style="color:red;">+{diff}</span>'
            elif diff < 0: change = f'<span style="color:green;">{diff}</span>'
            
        html += f"<tr><td>{entry['date']}</td><td>{price}</td><td>{change}</td></tr>"
    html += "</table>"
    html += f'<p style="font-size:12px;"><a href="{today_sinopec["url"]}">查看原资讯页面</a></p>'
    
    return html

def get_natural_rubber_price():
    """获取天然橡胶当日报价动态 (从资讯列表页抓取)"""
    list_url = "https://www.100ppi.com/news/list-15--56-1.html"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    
    tz = pytz.timezone('Asia/Shanghai')
    today = datetime.now(tz)
    date_pattern = f"{today.year}-{today.month:02d}-{today.day:02d}"
    today_title_str = f"（{date_pattern}）"
    
    try:
        resp = requests.get(list_url, headers=headers, timeout=15)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 寻找包含 "天然橡胶商品报价动态" 的标题
        news_items = soup.find_all('div', class_='list-item') or soup.find_all('li')
        target_url = None
        for item in news_items:
            text = item.get_text()
            if "天然橡胶商品报价动态" in text and date_pattern in text:
                link = item.find('a')
                if link and link.get('href'):
                    target_url = link.get('href')
                    if not target_url.startswith('http'):
                        if target_url.startswith('/'):
                            target_url = "https://www.100ppi.com" + target_url
                        else:
                            target_url = "https://www.100ppi.com/" + target_url
                    break
        
        if not target_url:
            print(f"今日 ({date_pattern}) 尚未发布天然橡胶报价动态。")
            return None

        print(f"发现今日天然橡胶资讯: {target_url}，正在解析详情...")
        detail_resp = requests.get(target_url, headers=headers, timeout=15)
        detail_resp.encoding = 'utf-8'
        detail_soup = BeautifulSoup(detail_resp.text, 'html.parser')
        
        # 抓取表格数据
        table = detail_soup.find('table')
        if not table:
            print("未能在详情页找到报价表格。")
            return None
            
        prices = {}
        rows = table.find_all('tr')
        for row in rows[1:]: # 跳过表头
            cols = row.find_all('td')
            if len(cols) >= 4:
                trader = cols[0].get_text(strip=True)
                brand = cols[1].get_text(strip=True)
                price_str = cols[3].get_text(strip=True)
                # 提取数字
                import re
                match = re.search(r'(\d+)', price_str)
                if match:
                    key = f"{trader}({brand})"
                    prices[key] = int(match.group(1))
        
        if prices:
            return {
                "date": today.strftime('%Y-%m-%d'),
                "prices": prices,
                "url": target_url
            }
    except Exception as e:
        print(f"抓取天然橡胶报价失败: {e}")
    return None

def generate_nr_html(today_nr, history):
    """为天然橡胶价格生成专属 HTML 报告"""
    tz = pytz.timezone('Asia/Shanghai')
    now_str = datetime.now(tz).strftime('%Y-%m-%d %H:%M')
    
    html = f"<h2>🌳 天然橡胶商品报价动态报告</h2>"
    html += f"<p><b>更新时间:</b> {now_str}</p>"
    
    prices = today_nr['prices']
    avg_price = sum(prices.values()) / len(prices)
    
    html += "<h3>📍 今日交易商报价详情</h3>"
    html += '<table border="1" style="border-collapse: collapse; width: 100%; text-align: center; font-size: 13px;">'
    html += '<tr style="background:#eee;"><th>交易商(品牌)</th><th>报价 (元/吨)</th><th>对比</th></tr>'
    
    for label, price in prices.items():
        style = ""
        diff_text = "持平"
        diff = price - avg_price
        if abs(diff) > 10:
            style = 'style="background-color: #fff9c4;"'
            if diff > 0: 
                diff_text = f'<span style="color:red;">偏高 {int(diff)}</span>'
                style = 'style="background-color: #ffcdd2; font-weight:bold;"'
            else: 
                diff_text = f'<span style="color:green;">偏低 {int(abs(diff))}</span>'

        html += f'<tr {style}><td>{label}</td><td>{price}</td><td>{diff_text}</td></tr>'
    html += "</table>"
    
    # 最近趋势
    html += "<h3>📈 最近 7 天均价走势</h3>"
    html += '<table border="1" style="border-collapse: collapse; width: 100%; text-align: center;">'
    html += '<tr style="background:#333; color:white;"><th>日期</th><th>均价</th><th>变动</th></tr>'
    
    all_dates = history + [{"date": today_nr['date'], "price": int(avg_price)}]
    recent_7 = all_dates[-7:]
    recent_7.reverse()
    
    for i, entry in enumerate(recent_7):
        price = entry['price']
        change = "持平"
        if i < len(recent_7) - 1:
            prev_price = recent_7[i+1]['price']
            diff = price - prev_price
            if diff > 0: change = f'<span style="color:red;">+{int(diff)}</span>'
            elif diff < 0: change = f'<span style="color:green;">-{int(abs(diff))}</span>'
            
        html += f"<tr><td>{entry['date']}</td><td>{price}</td><td>{change}</td></tr>"
    html += "</table>"
    html += f'<p style="font-size:12px;"><a href="{today_nr["url"]}">查看原资讯页面</a></p>'
    
    return html

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

def get_item_hash(item):
    """计算单条数据的唯一指纹"""
    # 组合关键字段: 日期 + 名称 + 价格 + 商家 + 规格
    unique_str = f"{item['date_str']}_{item['name']}_{item['price']}_{item['company']}_{item['spec']}"
    return hashlib.md5(unique_str.encode('utf-8')).hexdigest()

def load_processed_records():
    """加载已处理记录"""
    if not os.path.exists(RECORD_FILE):
        return {"date": "", "hashes": [], "sinopec_done_date": "", "nr_done_date": ""}
    try:
        with open(RECORD_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if "sinopec_done_date" not in data: data["sinopec_done_date"] = ""
            if "nr_done_date" not in data: data["nr_done_date"] = ""
            return data
    except Exception:
        return {"date": "", "hashes": [], "sinopec_done_date": "", "nr_done_date": ""}

def save_processed_records(records):
    """保存记录到文件"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    with open(RECORD_FILE, 'w', encoding='utf-8') as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

def git_commit_changes():
    """将状态文件的变更提交回 Git"""
    try:
        # 配置 git 用户 (如果是 GitHub Actions 环境)
        subprocess.run(["git", "config", "--global", "user.name", "github-actions[bot]"], check=True)
        subprocess.run(["git", "config", "--global", "user.email", "github-actions[bot]@users.noreply.github.com"], check=True)
        
        # Add & Commit & Push
        subprocess.run(["git", "add", DATA_DIR], check=True) # 提交整个 data 目录（包含历史记录）
        subprocess.run(["git", "commit", "-m", "Auto-update prices and history [skip ci]"], check=False)
        subprocess.run(["git", "push"], check=True)
        print("已成功提交状态记录更新。")
    except Exception as e:
        print(f"Git 提交失败 (本地运行可忽略): {e}")

def get_price_data(config):
    """根据配置爬取数据，并进行关键词过滤"""
    name = config.get('name')
    url = config.get('url')
    invalid_keywords = config.get('invalid_keywords', []) or []
    
    print(f"正在获取 {name} 的报价信息...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    all_prices = []
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            print(f"[{name}] 请求失败: {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 优化: 尝试多个可能的表格选择器，确保抓到的是数据表而不是导航表
        target_table = None
        
        # 优先级1: 带有特定类的表格
        for cls in ['list-tbl', 'lp-table']:
            t = soup.find('table', class_=cls)
            if t:
                target_table = t
                break
        
        # 优先级2: 遍历所有表格，寻找包含关键词的表格
        if not target_table:
            tables = soup.find_all('table')
            for t in tables:
                if "商品名称" in t.get_text() or "报价" in t.get_text():
                    target_table = t
                    break

        if not target_table:
            print(f"[{name}] 未找到有效的数据表格。")
            return []

        rows = target_table.find_all('tr')
        
        # 解析数据
        valid_row_count = 0
        for i, row in enumerate(rows):
            cols = row.find_all('td')
            # 必须满足至少 8 列 (商品, 规格, 厂家, 价格, 类型, 地区, 交易商, 日期)
            if len(cols) < 8:
                continue
            
            valid_row_count += 1
            
            # 解析原始文本
            product_name = cols[0].get_text(strip=True)
            spec = cols[1].get_text(strip=True)
            price = cols[3].get_text(strip=True)
            company = cols[6].get_text(strip=True)
            date_str = cols[7].get_text(strip=True)
            
            # 1. 关键词过滤
            full_text = f"{product_name} {spec} {price} {company}"
            is_invalid = False
            for kw in invalid_keywords:
                if kw in full_text:
                    is_invalid = True
                    break
            
            if is_invalid:
                continue
                
            # 2. 格式化数据并存入
            try:
                row_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                all_prices.append({
                    "name": name, 
                    "raw_name": product_name,
                    "spec": spec,
                    "price": price,
                    "company": company,
                    "date": row_date,
                    "date_str": date_str
                })
            except ValueError:
                continue
        
        print(f"[{name}] 扫描完毕。过滤后有效: {len(all_prices)}")

    except Exception as e:
        print(f"[{name}] 爬取异常: {e}")

    return all_prices

def organize_data(all_prices, sent_hashes):
    """整理数据"""
    tz = pytz.timezone('Asia/Shanghai')
    today = datetime.now(tz).date()
    yesterday = today - timedelta(days=1)
    
    today_data = []
    yesterday_data = []
    new_items_count = 0
    
    for item in all_prices:
        item_hash = get_item_hash(item)
        item['is_new'] = False
        
        if item['date'] == today:
            if item_hash not in sent_hashes:
                item['is_new'] = True
                new_items_count += 1
            today_data.append(item)
        elif item['date'] == yesterday:
            yesterday_data.append(item)
    
    yesterday_slice = yesterday_data[:3]
    return today_data, yesterday_slice, new_items_count

def generate_html_report(today_data, yesterday_data):
    """生成统一的 HTML 报表内容"""
    tz = pytz.timezone('Asia/Shanghai')
    now_str = datetime.now(tz).strftime('%Y-%m-%d %H:%M')
    
    html = f"<h3>📅 市场散户报价更新 ({now_str})</h3>"
    html += """
    <table border="1" style="border-collapse: collapse; width: 100%; font-size: 14px;">
        <tr style="background-color: #333; color: white;">
            <th>日期</th>
            <th>名称</th>
            <th>价格</th>
            <th>商家</th>
        </tr>
    """
    for item in today_data:
        row_style = "background-color: #ffcdd2; font-weight: bold; border: 2px solid red;" if item.get('is_new') else "background-color: #fff9c4;"
        date_display = f"{item['date_str']} (NEW)" if item.get('is_new') else item['date_str']
        html += f'<tr style="{row_style}"><td style="color: #d32f2f;">{date_display}</td><td>{item["raw_name"]}<br><span style="font-size:12px;color:gray;">{item["spec"]}</span></td><td style="color: red; font-size: 16px;">{item["price"]}</td><td>{item["company"]}</td></tr>'
        
    for item in yesterday_data:
        html += f'<tr style="background-color: #f5f5f5; color: #666;"><td>{item["date_str"]}</td><td>{item["raw_name"]}<br><span style="font-size:12px;color:gray;">{item["spec"]}</span></td><td>{item["price"]}</td><td>{item["company"]}</td></tr>'
        
    html += "</table><p style='font-size:12px; color: gray;'>注: 红色为最新，黄色为今日旧闻，灰色为昨日参考。</p>"
    return html

def send_notification(html_content):
    """通过 PushPlus 发送微信通知"""
    if not PUSHPLUS_TOKEN: return False
    tz = pytz.timezone('Asia/Shanghai')
    title = f"📢 丁二烯价格更新 ({datetime.now(tz).strftime('%H:%M')})"
    try:
        resp = requests.post("http://www.pushplus.plus/send", json={"token": PUSHPLUS_TOKEN, "title": title, "content": html_content, "template": "html"}, timeout=20)
        return resp.status_code == 200
    except: return False

def send_email_notification(html_content):
    """通过 SMTP 发送 QQ 邮件通知"""
    if not all([EMAIL_SENDER, EMAIL_AUTH_CODE, EMAIL_RECEIVER]): return False
    tz = pytz.timezone('Asia/Shanghai')
    msg = MIMEText(html_content, 'html', 'utf-8')
    msg['Subject'] = Header(f"丁二烯报价更新服务 - {datetime.now(tz).strftime('%Y-%m-%d %H:%M')}", 'utf-8')
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    try:
        server = smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=15)
        server.login(EMAIL_SENDER, EMAIL_AUTH_CODE)
        server.sendmail(EMAIL_SENDER, [EMAIL_RECEIVER], msg.as_string())
        try: server.quit()
        except: pass
        return True
    except Exception as e:
        if "(-1," in str(e): return True
        return False

def main():
    tz = pytz.timezone('Asia/Shanghai')
    now = datetime.now(tz)
    today_str = now.strftime('%Y-%m-%d')
    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] 脚本启动...")
    
    records = load_processed_records()
    if records["date"] != today_str:
        records.update({
            "date": today_str, 
            "hashes": [], 
            "sinopec_done_date": records.get("sinopec_done_date", ""),
            "nr_done_date": records.get("nr_done_date", "")
        })
    
    # --- 任务 1: 中石化丁二烯专场 ---
    sinopec_triggered = False
    if records.get("sinopec_done_date") != today_str:
        if 9 <= now.hour <= 17: # 扩大测试窗口
            print("正在监测中石化丁二烯报价...")
            sinopec_data = get_sinopec_factory_price()
            if sinopec_data:
                history = []
                if os.path.exists(SINOPEC_HISTORY_FILE):
                    with open(SINOPEC_HISTORY_FILE, 'r', encoding='utf-8') as f:
                        history = json.load(f)
                html = generate_sinopec_html(sinopec_data, history)
                if send_notification(html) or send_email_notification(html):
                    avg_p = sum(sinopec_data['prices'].values()) / len(sinopec_data['prices'])
                    history.append({"date": today_str, "price": int(avg_p), "is_sinopec": True})
                    with open(SINOPEC_HISTORY_FILE, 'w', encoding='utf-8') as f:
                        json.dump(history, f, indent=2, ensure_ascii=False)
                    records["sinopec_done_date"] = today_str
                    sinopec_triggered = True
                    save_processed_records(records)
                    git_commit_changes()

    # --- 任务 2: 天然橡胶专场 ---
    nr_triggered = False
    if records.get("nr_done_date") != today_str:
        if 9 <= now.hour <= 17: # 与中石化窗口一致
            print("正在监测天然橡胶当日动态...")
            nr_data = get_natural_rubber_price()
            if nr_data:
                history = []
                if os.path.exists(NR_HISTORY_FILE):
                    with open(NR_HISTORY_FILE, 'r', encoding='utf-8') as f:
                        history = json.load(f)
                html = generate_nr_html(nr_data, history)
                # 使用专门的标题推送
                if send_notification(html) or send_email_notification(html):
                    print("今日天然橡胶报价已成功推送并归档。")
                    avg_p = sum(nr_data['prices'].values()) / len(nr_data['prices'])
                    history.append({"date": today_str, "price": int(avg_p), "note": "Average"})
                    with open(NR_HISTORY_FILE, 'w', encoding='utf-8') as f:
                        json.dump(history, f, indent=2, ensure_ascii=False)
                    records["nr_done_date"] = today_str
                    nr_triggered = True
                    save_processed_records(records)
                    git_commit_changes()

    # --- 任务 3: 市场散户轮询 ---
    # 如果中石化还没出，执行散户轮询
    if records.get("sinopec_done_date") != today_str:
        print("执行常规散户丁二烯报价轮询...")
        configs = load_configs()
        sent_hashes = set(records["hashes"])
        all_items = []
        for cfg in configs: all_items.extend(get_price_data(cfg))
        
        today_data, yesterday_data, new_count = organize_data(all_items, sent_hashes)
        if new_count > 0:
            html = generate_html_report(today_data, yesterday_data)
            if send_notification(html) or send_email_notification(html):
                for item in today_data:
                    if item.get('is_new'): records["hashes"].append(get_item_hash(item))
                save_processed_records(records)
                git_commit_changes()
    else:
        if not sinopec_triggered:
            print("今日中石化报价已完成，散户常规轮询已跳过。")

if __name__ == "__main__":
    main()

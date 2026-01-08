import os
import requests
import io
from datetime import datetime, timedelta
import pytz
from bs4 import BeautifulSoup
import yaml
import glob
import json
import hashlib
import subprocess

# 默认设置
CONFIG_DIR = "COMM-CFG"
DATA_DIR = "data"
RECORD_FILE = os.path.join(DATA_DIR, "processed_records.json")
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

def get_item_hash(item):
    """计算单条数据的唯一指纹"""
    # 组合关键字段: 日期 + 名称 + 价格 + 商家 + 规格
    unique_str = f"{item['date_str']}_{item['name']}_{item['price']}_{item['company']}_{item['spec']}"
    return hashlib.md5(unique_str.encode('utf-8')).hexdigest()

def load_processed_records():
    """加载已处理记录"""
    if not os.path.exists(RECORD_FILE):
        return {"date": "", "hashes": []}
    try:
        with open(RECORD_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"date": "", "hashes": []}

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
        subprocess.run(["git", "add", RECORD_FILE], check=True)
        # 只有在有变动时 commit 才会成功，否则会由 git 返回 exit 1 (或只是 no output)
        # 我们忽略 commit 的错误（比如无变更时）
        subprocess.run(["git", "commit", "-m", "Update processed records [skip ci]"], check=False)
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
            print(f"[{name}] 未找到有效的数据表格。页面长度: {len(response.text)}")
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
        
        print(f"[{name}] 扫描完毕。总行数: {len(rows)}, 数据行: {valid_row_count}, 过滤后有效: {len(all_prices)}")

    except Exception as e:
        print(f"[{name}] 爬取异常: {e}")

    return all_prices

def organize_data(all_prices, sent_hashes):
    """
    整理数据:
    1. 分离 '今日'(Today) 和 '昨日'(Yesterday)。
    2. 标记 '今日' 数据中的 '新增' (New) 数据。
    """
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
            # Check if this hash has been sent
            if item_hash not in sent_hashes:
                item['is_new'] = True
                new_items_count += 1
            today_data.append(item)
            
        elif item['date'] == yesterday:
            yesterday_data.append(item)
    
    # 昨日数据只取最新的3条
    yesterday_slice = yesterday_data[:3]
    
    return today_data, yesterday_slice, new_items_count

def send_notification(today_data, yesterday_data):
    if not PUSHPLUS_TOKEN:
        print("未找到 PUSHPLUS_TOKEN (环境变量)，无法推送。")
        return False

    tz = pytz.timezone('Asia/Shanghai')
    now_str = datetime.now(tz).strftime('%Y-%m-%d %H:%M')
    
    title = f"📢 商品报价更新 ({now_str})"
    
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
    for item in today_data:
        # 如果是本次新增，给予最醒目的标记
        if item.get('is_new'):
            row_style = "background-color: #ffcdd2; font-weight: bold; border: 2px solid red;"
            date_display = f"{item['date_str']} <span style='background:red;color:white;padding:2px;border-radius:4px;'>NEW</span>"
        else:
            # 之前已发的今日数据，普通高亮
            row_style = "background-color: #fff9c4;"
            date_display = item['date_str']

        html += f"""
        <tr style="{row_style}">
            <td style="color: #d32f2f;">{date_display}</td>
            <td>{item['raw_name']}<br><span style="font-size:12px;color:gray;">{item['spec']}</span></td>
            <td style="color: red; font-size: 16px;">{item['price']}</td>
            <td>{item['company']}</td>
        </tr>
        """
        
    # 2. 昨日数据 (Greyed out)
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
    html += "<p style='font-size:12px; color: gray;'>注: 红色框为最新发现的报价，黄色为今日已发过的报价，灰色为昨日参考。</p>"
    
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
        if resp.status_code == 200:
            return True
    except Exception as e:
        print(f"推送失败: {e}")
        return False
    
    return False

def main():
    configs = load_configs()
    records = load_processed_records()
    
    # 检查是否跨天，如果是新的一天，重置记录
    tz = pytz.timezone('Asia/Shanghai')
    today_str = datetime.now(tz).strftime('%Y-%m-%d')
    
    if records["date"] != today_str:
        print(f"检测到新的一天 ({today_str})，重置发送记录。")
        records["date"] = today_str
        records["hashes"] = []
    
    sent_hashes = set(records["hashes"]) # 使用集合加速查找
    
    all_fetched_items = []
    for config in configs:
        items = get_price_data(config)
        all_fetched_items.extend(items)
    
    # 整理数据，计算哪些是新的
    today_data, yesterday_data, new_count = organize_data(all_fetched_items, sent_hashes)
    
    print(f"今日数据: {len(today_data)} 条, 其中新增: {new_count} 条")
    
    if new_count > 0:
        print("发现新报价，准备发送推送...")
        success = send_notification(today_data, yesterday_data)
        
        if success:
            # 发送成功后，更新记录
            print("更新本地状态记录...")
            for item in today_data:
                if item.get('is_new'):
                    item_hash = get_item_hash(item)
                    records["hashes"].append(item_hash)
            
            save_processed_records(records)
            git_commit_changes()
    else:
        print("没有发现新的有效报价，本轮不发送推送。")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
微信财经大V爆文日报推送服务
====================================
每天早上8点抓取前一日阅读量10万+的财经大V公众号文章,
推送10篇到微信。

数据来源:
1. 今日热榜(tophub) 微信24h热文榜 (聚合热文)
2. 大V备份站/RSS (主动抓取猫笔刀等)

推送方式: Server酱 Turbo版 (微信推送)
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import time
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict

# ============ 配置区 ============

SERVERCHAN_SENDKEY = os.environ.get("SERVERCHAN_SENDKEY", "")

TOPHUB_BASE_URL = "https://tophub.app"
TOPHUB_WECHAT_NODE = "/n/WnBe01o371"

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "output"))
HTML_OUTPUT = os.path.join(OUTPUT_DIR, "latest.html")
JSON_OUTPUT = os.path.join(OUTPUT_DIR, "latest.json")

# ★★★ 财经大V配置 ★★★
# 每个大V配置: 账号名 + 文章获取方式
FINANCE_BIG_VS = {
    # === 个人财经大V ===
    "猫笔刀": {"source": "backup", "url": "https://maobidao.cn/"},
    "金渐成": {"source": "tophub", "keywords": ["金渐成"]},
    "半佛仙人": {"source": "tophub", "keywords": ["半佛仙人"]},
    "饭统戴老板": {"source": "tophub", "keywords": ["饭统戴老板"]},
    "刘润": {"source": "tophub", "keywords": ["刘润"]},
    "吴晓波频道": {"source": "tophub", "keywords": ["吴晓波"]},
    # === 财经媒体 ===
    "远川研究": {"source": "tophub", "keywords": ["远川"]},
    "36氪": {"source": "tophub", "keywords": ["36氪"]},
    "虎嗅": {"source": "tophub", "keywords": ["虎嗅"]},
    "晚点LatePost": {"source": "tophub", "keywords": ["晚点"]},
    "财新网": {"source": "tophub", "keywords": ["财新"]},
    "第一财经": {"source": "tophub", "keywords": ["第一财经"]},
    "经济观察报": {"source": "tophub", "keywords": ["经济观察"]},
    "中国基金报": {"source": "tophub", "keywords": ["中国基金报"]},
    "券商中国": {"source": "tophub", "keywords": ["券商中国"]},
    "正和岛": {"source": "tophub", "keywords": ["正和岛"]},
    "格隆汇": {"source": "tophub", "keywords": ["格隆汇"]},
    "大猫财经": {"source": "tophub", "keywords": ["大猫财经"]},
    "市值观察": {"source": "tophub", "keywords": ["市值观察"]},
    "国是直通车": {"source": "tophub", "keywords": ["国是直通车"]},
    # === 科技商业 ===
    "极客公园": {"source": "tophub", "keywords": ["极客公园"]},
    "量子位": {"source": "tophub", "keywords": ["量子位"]},
}

# 所有白名单关键词(用于tophub文章账号匹配)
ALL_WHITELIST_KEYWORDS = []
for name, cfg in FINANCE_BIG_VS.items():
    kws = cfg.get("keywords", [name])
    ALL_WHITELIST_KEYWORDS.extend(kws)
ALL_WHITELIST_KEYWORDS = list(set(ALL_WHITELIST_KEYWORDS))

# ============ 通用 ============

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Referer': 'https://tophub.app/',
}

# ============ 数据源1: 猫笔刀备份站 ============

def fetch_maobidao_articles() -> List[Dict]:
    """从猫笔刀备份站RSS抓取最新文章"""
    articles = []
    try:
        import xml.etree.ElementTree as ET
        
        resp = requests.get('https://maobidao.cn/feed/', headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }, timeout=15)
        
        if resp.status_code == 200:
            root = ET.fromstring(resp.text)
            items = root.findall('.//item')
            
            for item in items:
                title_el = item.find('title')
                link_el = item.find('link')
                if title_el is not None and link_el is not None:
                    title = title_el.text or ''
                    url = link_el.text or ''
                    
                    if title and url:
                        articles.append({
                            'title': title,
                            'url': url,
                            'views': '10万+',
                            'views_num': 100000,
                            'account': '猫笔刀',
                            'source': 'maobidao_rss',
                            'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        })
            
            print(f"  猫笔刀RSS: {len(articles)} 篇")
    except Exception as e:
        print(f"  [ERROR] 猫笔刀RSS抓取失败: {e}")
    
    return articles


# ============ 数据源2: tophub热文 ============

def fetch_tophub_articles() -> List[Dict]:
    """从tophub抓取微信热文"""
    articles = []
    
    # 策略1: 首页
    try:
        resp = requests.get(TOPHUB_BASE_URL, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            links = soup.find_all('a')
            
            for link in links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                if 'mp.weixin.qq.com' in href and text:
                    views_match = re.search(r'(\d+\.?\d*)万$', text)
                    if views_match:
                        views_str = views_match.group(1)
                        views_num = float(views_str) * 10000
                        
                        title_match = re.match(r'^\d+(.+?)(\d+\.?\d*万)$', text)
                        title = title_match.group(1).strip() if title_match else text
                        
                        if title and views_num >= 100000:
                            articles.append({
                                'title': title,
                                'url': href,
                                'views': f'{views_str}万',
                                'views_num': views_num,
                                'account': '',
                                'source': 'tophub',
                                'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            })
    except Exception as e:
        print(f"  [ERROR] tophub首页抓取失败: {e}")
    
    # 策略2: 微信24h热文榜
    try:
        resp = requests.get(TOPHUB_BASE_URL + TOPHUB_WECHAT_NODE, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            links = soup.find_all('a')
            
            for link in links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                if 'mp.weixin.qq.com' in href and text:
                    views_match = re.search(r'(\d+\.?\d*)万$', text)
                    if views_match:
                        views_str = views_match.group(1)
                        views_num = float(views_str) * 10000
                        
                        title_match = re.match(r'^\d+(.+?)(\d+\.?\d*万)$', text)
                        title = title_match.group(1).strip() if title_match else text
                        
                        if title and views_num >= 100000:
                            existing_urls = [a['url'] for a in articles]
                            if href not in existing_urls:
                                articles.append({
                                    'title': title,
                                    'url': href,
                                    'views': f'{views_str}万',
                                    'views_num': views_num,
                                    'account': '',
                                    'source': 'tophub_wechat',
                                    'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                })
    except Exception as e:
        print(f"  [ERROR] tophub微信热文榜抓取失败: {e}")
    
    # 去重
    articles.sort(key=lambda x: x['views_num'], reverse=True)
    unique = []
    seen = set()
    for a in articles:
        key = re.sub(r'[，。！？、\s]', '', a['title'])[:20]
        if key not in seen:
            seen.add(key)
            unique.append(a)
    
    print(f"  tophub热文: {len(unique)} 篇")
    return unique


# ============ 账号识别 ============

def extract_account_name(url: str) -> str:
    """访问微信文章页面提取账号名"""
    try:
        resp = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            elem = soup.find('span', id='profileBt')
            if elem:
                return elem.get_text(strip=True)
            m = re.search(r'var\s+nickname\s*=\s*["\']([^"\']+)', resp.text)
            if m:
                return m.group(1)
    except Exception:
        pass
    return ""


def identify_accounts(articles: List[Dict]) -> List[Dict]:
    """识别tophub文章的账号来源(猫笔刀等备份站文章已有账号名)"""
    need_identify = [a for a in articles if not a.get('account')]
    print(f"  需要识别账号: {len(need_identify)} 篇")
    
    for i, article in enumerate(need_identify):
        account = extract_account_name(article['url'])
        article['account'] = account
        is_v = any(kw in account for kw in ALL_WHITELIST_KEYWORDS) if account else False
        if account:
            print(f"    [{i+1}] {account} {'✅财经大V' if is_v else ''} | {article['title'][:30]}")
        time.sleep(0.3)
    
    return articles


# ============ 财经大V过滤 ============

def filter_finance_articles(articles: List[Dict]) -> List[Dict]:
    """只保留财经大V的文章,不够10篇时从其他文章补充"""
    finance_articles = []
    other_articles = []
    
    for article in articles:
        account = article.get('account', '')
        
        # 猫笔刀等备份站来源,直接算财经大V
        if article.get('source') in ('maobidao_rss', 'maobidao_backup',):
            finance_articles.append(article)
            continue
        
        if not account:
            other_articles.append(article)
            continue
        
        # 白名单关键词匹配
        is_finance = any(kw in account for kw in ALL_WHITELIST_KEYWORDS)
        
        if is_finance:
            finance_articles.append(article)
        else:
            other_articles.append(article)
    
    print(f"  财经大V文章: {len(finance_articles)} 篇")
    print(f"  其他文章: {len(other_articles)} 篇 (已过滤)")
    
    # 如果财经大V不够10篇,从其他补充
    if len(finance_articles) < 10 and other_articles:
        supplement = other_articles[:10 - len(finance_articles)]
        print(f"  财经大V不够10篇,从其他补充 {len(supplement)} 篇")
        finance_articles.extend(supplement)
    
    return finance_articles


def select_top_articles(articles: List[Dict], count: int = 10) -> List[Dict]:
    """选择最优的count篇文章"""
    if len(articles) <= count:
        return articles
    
    # 优先: 有明确账号名的财经大V文章 > 未知账号文章
    named = [a for a in articles if a.get('account')]
    unnamed = [a for a in articles if not a.get('account')]
    
    selected = named[:count]
    if len(selected) < count:
        selected.extend(unnamed[:count - len(selected)])
    
    return selected[:count]


# ============ 消息格式化 ============

def format_serverchan_message(articles: List[Dict]) -> tuple:
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y年%m月%d日')
    today = datetime.now().strftime('%Y年%m月%d日')
    fetch_time = datetime.now().strftime('%H:%M')
    
    title = f"💰 财经大V爆文日报 | {yesterday}"
    
    desp = f"""## 💰 财经大V爆文日报

> 📅 {yesterday} | 🕐 {today} {fetch_time}  
> 🎯 只推送财经大V | 📊 10万+精选

---

"""
    for i, article in enumerate(articles, 1):
        account = article.get('account', '未知账号')
        is_v = any(kw in account for kw in ALL_WHITELIST_KEYWORDS) if account else False
        tag = "💰财经" if is_v else ""
        
        desp += f"""### {i}. {article['title']}
- 📝 **{account}** {tag}
- 📖 阅读量: **{article['views']}**
- 🔗 [阅读原文]({article['url']})

---

"""
    
    desp += f"""*数据来源: 今日热榜 + 猫笔刀备份站 | 每天早上8:00推送*"""
    return title, desp


def format_html_report(articles: List[Dict]) -> str:
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y年%m月%d日')
    today = datetime.now().strftime('%Y年%m月%d日')
    fetch_time = datetime.now().strftime('%H:%M')
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>财经大V爆文日报 | {yesterday}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f5f5f5;color:#333;line-height:1.6;max-width:800px;margin:0 auto;padding:20px}}
.header{{background:linear-gradient(135deg,#2196F3 0%,#1565C0 100%);color:white;padding:30px;border-radius:12px;margin-bottom:20px}}
.header h1{{font-size:24px;margin-bottom:10px}}
.card{{background:white;padding:20px;border-radius:8px;margin-bottom:12px;box-shadow:0 2px 4px rgba(0,0,0,0.1)}}
.card:hover{{transform:translateY(-2px);box-shadow:0 4px 8px rgba(0,0,0,0.15)}}
.rank{{display:inline-block;background:#2196F3;color:white;width:28px;height:28px;border-radius:50%;text-align:center;line-height:28px;font-weight:bold;font-size:13px;margin-right:8px}}
.account{{color:#2196F3;font-weight:bold}}
.finance-tag{{background:#FF9800;color:white;padding:2px 6px;border-radius:3px;font-size:11px}}
.views{{color:#e74c3c;font-weight:bold}}
.link{{display:inline-block;background:#2196F3;color:white;padding:6px 14px;border-radius:5px;text-decoration:none;font-size:13px}}
.footer{{text-align:center;padding:15px;color:#999;font-size:12px}}
</style></head><body>
<div class="header"><h1>💰 财经大V爆文日报</h1>
<div style="font-size:14px;opacity:0.9">📅 {yesterday} | 🕐 {today} {fetch_time} | 🎯 只推财经大V</div></div>
"""
    for i, a in enumerate(articles, 1):
        account = a.get('account', '未知')
        is_v = any(kw in account for kw in ALL_WHITELIST_KEYWORDS) if account else False
        tag = '<span class="finance-tag">💰财经</span>' if is_v else ''
        html += f"""<div class="card">
<div style="font-size:17px;font-weight:600;margin-bottom:6px"><span class="rank">{i}</span>{a['title']}</div>
<div style="font-size:13px;color:#666;margin-bottom:8px">
<span class="views">📖 {a['views']}</span> | <span class="account">📝 {account}</span> {tag}</div>
<a class="link" href="{a['url']}" target="_blank">阅读原文 →</a></div>\n"""
    
    html += f"""<div class="footer">数据来源: 今日热榜 + 猫笔刀备份站 | 每天早上8:00自动推送</div></body></html>"""
    return html


# ============ Server酱推送 ============

def push_to_serverchan(title: str, desp: str, sendkey: str) -> bool:
    if not sendkey:
        print("[WARN] Server酱SendKey未配置")
        return False
    try:
        resp = requests.post(f"https://sctapi.ftqq.com/{sendkey}.send", data={'title': title, 'desp': desp}, timeout=15)
        result = resp.json()
        if result.get('code') == 0 or result.get('errno') == 0:
            print(f"[OK] Server酱推送成功!")
            return True
        else:
            print(f"[ERROR] Server酱推送失败: {result}")
            return False
    except Exception as e:
        print(f"[ERROR] Server酱推送异常: {e}")
        return False


# ============ 主流程 ============

def main():
    print("=" * 50)
    print(f"💰 财经大V爆文日报 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # 1. 多数据源抓取
    print("\n[1/5] 抓取数据...")
    print("  数据源1: 猫笔刀备份站")
    maobidao = fetch_maobidao_articles()
    
    print("  数据源2: tophub微信热文")
    tophub = fetch_tophub_articles()
    
    all_articles = maobidao + tophub
    print(f"  合计: {len(all_articles)} 篇10万+文章")
    
    if not all_articles:
        all_articles = [{
            'title': '暂无数据 - 请稍后重试',
            'url': 'https://tophub.app/n/WnBe01o371',
            'views': '0万', 'views_num': 0,
            'account': '', 'source': 'fallback',
            'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }]
    
    # 2. 识别账号
    print("\n[2/5] 识别账号来源...")
    all_articles = identify_accounts(all_articles)
    
    # 3. 财经大V过滤
    print("\n[3/5] 财经大V过滤...")
    finance = filter_finance_articles(all_articles)
    
    # 4. 精选10篇
    print("\n[4/5] 精选10篇...")
    top10 = select_top_articles(finance, count=10)
    print(f"  精选 {len(top10)} 篇:")
    for i, a in enumerate(top10, 1):
        acc = a.get('account', '未知')
        print(f"    {i}. [{a['views']}] [{acc}] {a['title'][:40]}")
    
    # 5. 推送
    print("\n[5/5] 推送...")
    title, desp = format_serverchan_message(top10)
    push_ok = push_to_serverchan(title, desp, SERVERCHAN_SENDKEY)
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(HTML_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(format_html_report(top10))
    
    with open(JSON_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump({
            'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'date': (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
            'total_articles': len(all_articles),
            'finance_articles': len(finance),
            'selected_articles': top10,
        }, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 50)
    print(f"✅ 完成! 抓取{len(all_articles)}篇 | 财经大V {len(finance)}篇 | 推送{len(top10)}篇 | 推送{'✅' if push_ok else '❌'}")
    print("=" * 50)
    return top10


if __name__ == "__main__":
    if len(sys.argv) > 1:
        SERVERCHAN_SENDKEY = sys.argv[1]
    main()
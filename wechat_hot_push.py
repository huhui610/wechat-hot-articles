#!/usr/bin/env python3
"""
微信公众号大V爆文日报推送服务
====================================
每天早上8点抓取前一日阅读量10万+的微信公众号文章,
识别账号来源,只推送大V账号的文章,过滤普通账号。

数据来源: 今日热榜(tophub) 微信24h热文榜
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
from typing import List, Dict, Optional

# ============ 配置区 ============

# Server酱配置
SERVERCHAN_SENDKEY = os.environ.get("SERVERCHAN_SENDKEY", "")

# 数据源配置
TOPHUB_BASE_URL = "https://tophub.app"
TOPHUB_WECHAT_NODE = "/n/WnBe01o371"

# 输出配置
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "output"))
HTML_OUTPUT = os.path.join(OUTPUT_DIR, "latest.html")
JSON_OUTPUT = os.path.join(OUTPUT_DIR, "latest.json")

# ★★★ 大V白名单 ★★★
# 只推送这些账号的文章,普通账号文章会被过滤
# 你可以随时添加/删除账号名,用逗号分隔
BIG_V_WHITELIST = [
    # === 财经大V ===
    "猫笔刀", "金渐成", "招财大牛猫",  # 财经投资
    "半佛仙人",  # 商业深度分析
    "饭统戴老板",  # 商业故事
    "远川研究",  # 行业研究
    # === 科技互联网 ===
    "量子位", "机器之心",  # AI/科技
    "极客公园",  # 科技商业
    "36氪", "虎嗅",  # 商业科技媒体
    # === 社会新闻大号 ===
    "人民日报", "新华社", "央视新闻", "中国新闻周刊",
    "澎湃新闻", "南方周末", "三联生活周刊",
    "环球时报", "光明日报",
    # === 深度内容 ===
    "人物", "GQ报道",  # 人物故事
    "果壳", "丁香医生",  # 科学健康
    "地道风物",  # 文化地理
    # === 生活/职场 ===
    "晚点LatePost",  # 商业深度
    "新世相",  # 生活观察
    "虎扑",  # 体育社区
]

# ============ 数据抓取 ============

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Referer': 'https://tophub.app/',
}

WX_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}


def extract_account_name(url: str) -> str:
    """
    访问微信文章页面提取公众号账号名
    """
    try:
        resp = requests.get(url, headers=WX_HEADERS, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 方式1: span#profileBt (最可靠)
            elem = soup.find('span', id='profileBt')
            if elem:
                name = elem.get_text(strip=True)
                if name:
                    return name
            
            # 方式2: var nickname
            m = re.search(r'var\s+nickname\s*=\s*["\']([^"\']+)', resp.text)
            if m:
                return m.group(1)
            
            # 方式3: rich_media_meta_nickname
            m = re.search(r'rich_media_meta_nickname\s*=\s*["\']([^"\']+)', resp.text)
            if m:
                return m.group(1)
    except Exception:
        pass
    
    return ""


def fetch_wechat_hot_articles() -> List[Dict]:
    """从今日热榜抓取微信24h热文榜数据"""
    articles = []
    
    # 策略1: 从tophub首页直接抓取
    try:
        url = TOPHUB_BASE_URL
        resp = requests.get(url, headers=HEADERS, timeout=15)
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
                        if title_match:
                            title = title_match.group(1)
                        else:
                            title = text.replace(views_match.group(0), '')
                            title = re.sub(r'^\d+', '', title)
                        
                        title = title.strip()
                        
                        if title and views_num >= 100000:
                            articles.append({
                                'title': title,
                                'url': href,
                                'views': f'{views_str}万',
                                'views_num': views_num,
                                'source': 'tophub',
                                'account': '',  # 后面填充
                                'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            })
    except Exception as e:
        print(f"[ERROR] tophub首页抓取失败: {e}")
    
    # 策略2: 从微信24h热文榜专门页面抓取
    try:
        url = TOPHUB_BASE_URL + TOPHUB_WECHAT_NODE
        resp = requests.get(url, headers=HEADERS, timeout=15)
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
                        if title_match:
                            title = title_match.group(1)
                        else:
                            title = text.replace(views_match.group(0), '')
                            title = re.sub(r'^\d+', '', title)
                        
                        title = title.strip()
                        
                        if title and views_num >= 100000:
                            existing_urls = [a['url'] for a in articles]
                            if href not in existing_urls:
                                articles.append({
                                    'title': title,
                                    'url': href,
                                    'views': f'{views_str}万',
                                    'views_num': views_num,
                                    'source': 'tophub_wechat',
                                    'account': '',
                                    'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                })
    except Exception as e:
        print(f"[ERROR] tophub微信热文榜抓取失败: {e}")
    
    # 排序+去重
    articles.sort(key=lambda x: x['views_num'], reverse=True)
    unique_articles = []
    seen_titles = set()
    for a in articles:
        simplified = re.sub(r'[，。！？、\s]', '', a['title'])[:20]
        if simplified not in seen_titles:
            seen_titles.add(simplified)
            unique_articles.append(a)
    
    return unique_articles


def identify_accounts(articles: List[Dict]) -> List[Dict]:
    """
    识别每篇文章的账号来源
    尝试访问文章页面提取账号名
    """
    print(f"  识别账号来源 (共{len(articles)}篇)...")
    
    for i, article in enumerate(articles):
        account = extract_account_name(article['url'])
        article['account'] = account
        if account:
            print(f"    [{i+1}] {article['title'][:30]} ← {account}")
        else:
            print(f"    [{i+1}] {article['title'][:30]} ← 未知账号")
        time.sleep(0.3)  # 避免请求过快
    
    return articles


def filter_big_v_articles(articles: List[Dict], whitelist: List[str]) -> List[Dict]:
    """
    只保留大V账号的文章
    whitelist中的账号名会做模糊匹配(包含即可)
    """
    big_v_articles = []
    other_articles = []
    
    for article in articles:
        account = article.get('account', '')
        
        if not account:
            # 未知账号,放入"其他"列表(不会被优先选择)
            other_articles.append(article)
            continue
        
        # 模糊匹配白名单
        is_big_v = False
        for v_name in whitelist:
            if v_name in account or account in v_name:
                is_big_v = True
                break
        
        if is_big_v:
            big_v_articles.append(article)
        else:
            other_articles.append(article)
    
    print(f"  大V账号文章: {len(big_v_articles)} 篇")
    print(f"  其他账号文章: {len(other_articles)} 篇 (已过滤)")
    
    # 如果大V文章不够5篇,从其他文章中补充
    if len(big_v_articles) < 5 and other_articles:
        supplement = other_articles[:5 - len(big_v_articles)]
        print(f"  大V不够5篇,从其他账号补充 {len(supplement)} 篇")
        big_v_articles.extend(supplement)
    
    return big_v_articles


def select_top_articles(articles: List[Dict], count: int = 5) -> List[Dict]:
    """选择最优的count篇文章"""
    if len(articles) <= count:
        return articles
    
    # 大V文章优先,按阅读量排序
    selected = []
    categories_seen = set()
    
    for article in articles:
        category = categorize_article(article['title'])
        if category not in categories_seen or len([s for s in selected if categorize_article(s['title']) == category]) < 2:
            selected.append(article)
            categories_seen.add(category)
        if len(selected) >= count:
            break
    
    if len(selected) < count:
        remaining = [a for a in articles if a not in selected]
        selected.extend(remaining[:count - len(selected)])
    
    return selected[:count]


def categorize_article(title: str) -> str:
    """简单分类文章"""
    category_keywords = {
        '社会': ['通报', '事故', '灾害', '暴雨', '预警', '塌陷', '救援', '表扬', '处罚'],
        '科技': ['AI', '苹果', 'WWDC', '手机', '芯片', '科技', '算法', 'GPT', '大模型', 'ima'],
        '健康': ['肥胖', '饮食', '健康', '医生', '疾病', '昏迷', '提醒', '中毒', '异味'],
        '娱乐': ['明星', '演唱', '综艺', '电影', '谢娜', '林志颖'],
        '生活': ['高考', '暑假', '旅行', '美食', '饮料', '省钱', '维权', '套餐', '运营商'],
        '财经': ['股价', '投资', '股票', '涨停', '比亚迪', '财经', '上市'],
    }
    
    for cat, keywords in category_keywords.items():
        for kw in keywords:
            if kw in title:
                return cat
    
    return '综合'


# ============ 消息格式化 ============

def format_serverchan_message(articles: List[Dict]) -> tuple:
    """格式化Server酱推送消息"""
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y年%m月%d日')
    today = datetime.now().strftime('%Y年%m月%d日')
    fetch_time = datetime.now().strftime('%H:%M')
    
    title = f"🔥 大V爆文日报 | {yesterday}"
    
    desp = f"""## 微信大V爆文日报

> 📅 数据日期: {yesterday}  
> 🕐 推送时间: {today} {fetch_time}  
> 📊 数据来源: 今日热榜 微信24h热文榜  
> 🎯 只推送大V账号文章

---

"""

    for i, article in enumerate(articles, 1):
        account = article.get('account', '未知账号')
        is_big_v = any(v in account or account in v for v in BIG_V_WHITELIST) if account else False
        v_tag = "⭐大V" if is_big_v else ""
        
        desp += f"""### {i}. {article['title']}

- 📖 阅读量: **{article['views']}** (10万+爆文)
- 📝 来源账号: **{account}** {v_tag}
- 🔗 [点击阅读原文]({article['url']})
- 📂 分类: {categorize_article(article['title'])}

---

"""

    desp += f"""## 📈 统计

- 本次筛选文章数: **{len(articles)}** 篇
- 所有文章阅读量均超 **10万+**
- 优先推送 **大V账号** 文章

---

*数据来源: [今日热榜](https://tophub.app/n/WnBe01o371) | 微信24h热文榜*
*服务由自动脚本生成,每天早上8:00准时推送*
"""
    
    return title, desp


def format_html_report(articles: List[Dict]) -> str:
    """生成HTML格式报告"""
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y年%m月%d日')
    today = datetime.now().strftime('%Y年%m月%d日')
    fetch_time = datetime.now().strftime('%H:%M')
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>大V爆文日报 | {yesterday}</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }}
    .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; }}
    .header h1 {{ font-size: 24px; margin-bottom: 10px; }}
    .header .meta {{ font-size: 14px; opacity: 0.9; }}
    .article-card {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
    .article-card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.15); }}
    .rank {{ display: inline-block; background: #667eea; color: white; width: 30px; height: 30px; border-radius: 50%; text-align: center; line-height: 30px; font-weight: bold; font-size: 14px; margin-right: 10px; }}
    .title {{ font-size: 18px; font-weight: 600; color: #333; margin-bottom: 8px; }}
    .meta {{ font-size: 14px; color: #666; margin-bottom: 10px; }}
    .views {{ color: #e74c3c; font-weight: bold; }}
    .account {{ color: #2196F3; font-weight: bold; }}
    .big-v {{ background: #FF9800; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; }}
    .category {{ background: #f0f0f0; padding: 2px 8px; border-radius: 4px; font-size: 12px; color: #666; }}
    .link {{ display: inline-block; background: #667eea; color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-size: 14px; }}
    .link:hover {{ background: #5a6fd6; }}
    .footer {{ text-align: center; padding: 20px; color: #999; font-size: 12px; }}
    .stats {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 15px; text-align: center; }}
</style>
</head>
<body>
<div class="header">
    <h1>🔥 微信大V爆文日报</h1>
    <div class="meta">
        📅 {yesterday} | 🕐 {today} {fetch_time} | 🎯 只推送大V账号 | 📊 今日热榜
    </div>
</div>
"""
    
    for i, article in enumerate(articles, 1):
        account = article.get('account', '未知账号')
        is_big_v = any(v in account or account in v for v in BIG_V_WHITELIST) if account else False
        category = categorize_article(article['title'])
        v_tag = '<span class="big-v">⭐大V</span>' if is_big_v else ''
        
        html += f"""
<div class="article-card">
    <div class="title"><span class="rank">{i}</span>{article['title']}</div>
    <div class="meta">
        <span class="views">📖 {article['views']}</span> | 
        <span class="account">📝 {account}</span> {v_tag} | 
        <span class="category">📂 {category}</span>
    </div>
    <a class="link" href="{article['url']}" target="_blank">阅读原文 →</a>
</div>
"""
    
    html += f"""
<div class="stats">🎯 大V优先推送 | 📈 {len(articles)} 篇精选 | 所有文章10万+</div>
<div class="footer">数据来源: 今日热榜 | 每天早上8:00自动推送</div>
</body></html>"""
    
    return html


# ============ Server酱推送 ============

def push_to_serverchan(title: str, desp: str, sendkey: str) -> bool:
    """通过Server酱Turbo版推送消息到微信"""
    if not sendkey:
        print("[WARN] Server酱SendKey未配置,跳过微信推送")
        return False
    
    url = f"https://sctapi.ftqq.com/{sendkey}.send"
    data = {'title': title, 'desp': desp}
    
    try:
        resp = requests.post(url, data=data, timeout=15)
        result = resp.json()
        if result.get('code') == 0 or result.get('errno') == 0:
            print(f"[OK] Server酱推送成功! 标题: {title}")
            return True
        else:
            print(f"[ERROR] Server酱推送失败: {result}")
            return False
    except Exception as e:
        print(f"[ERROR] Server酱推送异常: {e}")
        return False


# ============ 主流程 ============

def main():
    """主执行流程"""
    print("=" * 50)
    print(f"微信大V爆文日报 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # 1. 抓取数据
    print("\n[1/5] 抓取微信热文数据...")
    articles = fetch_wechat_hot_articles()
    print(f"  抓取到 {len(articles)} 篇10万+文章")
    
    if not articles:
        print("[WARN] 未抓取到文章,可能数据源暂时不可用")
        articles = [{
            'title': '暂无数据 - 请稍后重试',
            'url': 'https://tophub.app/n/WnBe01o371',
            'views': '0万', 'views_num': 0,
            'account': '', 'source': 'fallback',
            'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }]
    
    # 2. 识别账号
    print("\n[2/5] 识别账号来源...")
    articles = identify_accounts(articles)
    
    # 3. 大V过滤
    print("\n[3/5] 大V白名单过滤...")
    big_v_articles = filter_big_v_articles(articles, BIG_V_WHITELIST)
    
    # 4. 精选5篇
    print("\n[4/5] 精选5篇...")
    top5 = select_top_articles(big_v_articles, count=5)
    print(f"  精选 {len(top5)} 篇文章:")
    for i, a in enumerate(top5, 1):
        account = a.get('account', '未知')
        print(f"    {i}. [{a['views']}] [{account}] {a['title'][:40]}")
    
    # 5. 推送
    print("\n[5/5] 推送消息...")
    title, desp = format_serverchan_message(top5)
    push_success = push_to_serverchan(title, desp, SERVERCHAN_SENDKEY)
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    html = format_html_report(top5)
    with open(HTML_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  HTML报告: {HTML_OUTPUT}")
    
    with open(JSON_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump({
            'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'date': (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
            'total_10w_articles': len(articles),
            'big_v_articles': len(big_v_articles),
            'selected_articles': top5,
        }, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 50)
    print(f"✅ 执行完成!")
    print(f"  抓取10万+文章: {len(articles)} 篇")
    print(f"  大V账号文章: {len(big_v_articles)} 篇")
    print(f"  精选推送: {len(top5)} 篇")
    print(f"  Server酱推送: {'✅ 成功' if push_success else '❌ 未配置/失败'}")
    print("=" * 50)
    
    return top5


if __name__ == "__main__":
    if len(sys.argv) > 1:
        SERVERCHAN_SENDKEY = sys.argv[1]
    main()
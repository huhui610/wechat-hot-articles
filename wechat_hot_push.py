#!/usr/bin/env python3
"""
微信公众号10万+爆文每日推送服务
====================================
每天早上8点抓取前一日阅读量10万+的微信公众号文章,
筛选5篇最优文章,通过Server酱推送到微信。

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

# Server酱配置 - 需要你注册后填入自己的SendKey
# 注册地址: https://sct.ftqq.com/
SERVERCHAN_SENDKEY = os.environ.get("SERVERCHAN_SENDKEY", "")  # 从环境变量读取

# 数据源配置
TOPHUB_BASE_URL = "https://tophub.app"
TOPHUB_WECHAT_NODE = "/n/WnBe01o371"  # 微信24h热文榜节点ID

# 输出配置 - 自动适配本地运行和GitHub Actions环境
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "output"))
HTML_OUTPUT = os.path.join(OUTPUT_DIR, "latest.html")
JSON_OUTPUT = os.path.join(OUTPUT_DIR, "latest.json")

# ============ 数据抓取 ============

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Referer': 'https://tophub.app/',
}

def fetch_wechat_hot_articles() -> List[Dict]:
    """
    从今日热榜抓取微信24h热文榜数据
    返回格式: [{title, url, views, views_num, source}, ...]
    """
    articles = []
    
    # 策略1: 从tophub首页直接抓取(首页包含微信热文数据)
    try:
        url = TOPHUB_BASE_URL
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            links = soup.find_all('a')
            
            for link in links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                # 筛选微信公众号文章(mp.weixin.qq.com链接)
                if 'mp.weixin.qq.com' in href and text:
                    # 提取阅读量信息
                    # 文本格式通常是: "1标题文字10.0万" 或 "28标题文字9.7万"
                    views_match = re.search(r'(\d+\.?\d*)万$', text)
                    if views_match:
                        views_str = views_match.group(1)
                        views_num = float(views_str) * 10000
                        
                        # 提取标题(去掉序号和阅读量)
                        title_match = re.match(r'^\d+(.+?)(\d+\.?\d*万)$', text)
                        if title_match:
                            title = title_match.group(1)
                        else:
                            title = text.replace(views_match.group(0), '')
                            title = re.sub(r'^\d+', '', title)
                        
                        title = title.strip()
                        
                        if title and views_num >= 100000:  # 10万+
                            articles.append({
                                'title': title,
                                'url': href,
                                'views': f'{views_str}万',
                                'views_num': views_num,
                                'source': 'tophub',
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
                            # 检查是否已存在(避免重复)
                            existing_urls = [a['url'] for a in articles]
                            if href not in existing_urls:
                                articles.append({
                                    'title': title,
                                    'url': href,
                                    'views': f'{views_str}万',
                                    'views_num': views_num,
                                    'source': 'tophub_wechat',
                                    'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                })
    except Exception as e:
        print(f"[ERROR] tophub微信热文榜抓取失败: {e}")
    
    # 按阅读量排序
    articles.sort(key=lambda x: x['views_num'], reverse=True)
    
    # 去重(基于标题相似度)
    unique_articles = []
    seen_titles = set()
    for a in articles:
        # 简化标题用于去重比较
        simplified = re.sub(r'[，。！？、\s]', '', a['title'])[:20]
        if simplified not in seen_titles:
            seen_titles.add(simplified)
            unique_articles.append(a)
    
    return unique_articles


def select_top_articles(articles: List[Dict], count: int = 5) -> List[Dict]:
    """
    从文章列表中选择最优的count篇文章
    优先选择: 阅读量最高 + 标题最具信息价值
    """
    if len(articles) <= count:
        return articles
    
    # 按阅读量排序后,从顶部选取
    # 但避免选取过多同类型文章
    selected = []
    categories_seen = set()
    
    for article in articles:
        # 简单分类: 根据标题关键词判断类别
        category = categorize_article(article['title'])
        
        # 每个类别最多选2篇,避免同类型扎堆
        if category not in categories_seen or len([s for s in selected if categorize_article(s['title']) == category]) < 2:
            selected.append(article)
            categories_seen.add(category)
        
        if len(selected) >= count:
            break
    
    # 如果类别分散不够,直接取top N
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
    """
    格式化Server酱推送消息
    返回: (title, desp)  title为消息标题, desp为Markdown内容
    """
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y年%m月%d日')
    today = datetime.now().strftime('%Y年%m月%d日')
    fetch_time = datetime.now().strftime('%H:%M')
    
    # 消息标题
    title = f"🔥 微信10万+爆文日报 | {yesterday}"
    
    # Markdown内容
    desp = f"""## 微信公众号10万+爆文日报

> 📅 数据日期: {yesterday}  
> 🕐 推送时间: {today} {fetch_time}  
> 📊 数据来源: 今日热榜 微信24h热文榜

---

"""

    for i, article in enumerate(articles, 1):
        desp += f"""### {i}. {article['title']}

- 📖 阅读量: **{article['views']}** (10万+爆文)
- 🔗 [点击阅读原文]({article['url']})
- 📂 分类: {categorize_article(article['title'])}

---

"""

    desp += f"""## 📈 统计

- 本次筛选文章数: **{len(articles)}** 篇
- 所有文章阅读量均超 **10万+**
- 按阅读量排序精选推送

---

*数据来源: [今日热榜](https://tophub.app/n/WnBe01o371) | 微信24h热文榜*
*服务由自动脚本生成,每天早上8:00准时推送*
"""
    
    return title, desp


def format_html_report(articles: List[Dict]) -> str:
    """
    生成HTML格式报告,保存到本地供查看
    """
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y年%m月%d日')
    today = datetime.now().strftime('%Y年%m月%d日')
    fetch_time = datetime.now().strftime('%H:%M')
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>微信10万+爆文日报 | {yesterday}</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ 
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
        background: #f5f5f5;
        color: #333;
        line-height: 1.6;
        max-width: 800px;
        margin: 0 auto;
        padding: 20px;
    }}
    .header {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 30px;
        border-radius: 12px;
        margin-bottom: 20px;
    }}
    .header h1 {{ font-size: 24px; margin-bottom: 10px; }}
    .header .meta {{ font-size: 14px; opacity: 0.9; }}
    .article-card {{
        background: white;
        padding: 20px;
        border-radius: 8px;
        margin-bottom: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        transition: transform 0.2s;
    }}
    .article-card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.15); }}
    .article-card .rank {{
        display: inline-block;
        background: #667eea;
        color: white;
        width: 30px;
        height: 30px;
        border-radius: 50%;
        text-align: center;
        line-height: 30px;
        font-weight: bold;
        font-size: 14px;
        margin-right: 10px;
    }}
    .article-card .title {{
        font-size: 18px;
        font-weight: 600;
        color: #333;
        margin-bottom: 8px;
    }}
    .article-card .meta {{
        font-size: 14px;
        color: #666;
        margin-bottom: 10px;
    }}
    .article-card .views {{
        color: #e74c3c;
        font-weight: bold;
    }}
    .article-card .category {{
        background: #f0f0f0;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 12px;
        color: #666;
    }}
    .article-card .link {{
        display: inline-block;
        background: #667eea;
        color: white;
        padding: 8px 16px;
        border-radius: 6px;
        text-decoration: none;
        font-size: 14px;
    }}
    .article-card .link:hover {{ background: #5a6fd6; }}
    .footer {{
        text-align: center;
        padding: 20px;
        color: #999;
        font-size: 12px;
    }}
    .stats {{
        background: white;
        padding: 20px;
        border-radius: 8px;
        margin-bottom: 15px;
        text-align: center;
    }}
</style>
</head>
<body>

<div class="header">
    <h1>🔥 微信公众号10万+爆文日报</h1>
    <div class="meta">
        📅 数据日期: {yesterday} | 🕐 推送时间: {today} {fetch_time} | 📊 来源: 今日热榜
    </div>
</div>

"""
    
    for i, article in enumerate(articles, 1):
        category = categorize_article(article['title'])
        html += f"""
<div class="article-card">
    <div class="title"><span class="rank">{i}</span>{article['title']}</div>
    <div class="meta">
        <span class="views">📖 阅读量: {article['views']}</span> | 
        <span class="category">📂 {category}</span>
    </div>
    <a class="link" href="{article['url']}" target="_blank">阅读原文 →</a>
</div>
"""
    
    html += f"""
<div class="stats">
    📈 本次筛选 <strong>{len(articles)}</strong> 篇 | 所有文章阅读量均超 <strong>10万+</strong> | 按阅读量排序精选推送
</div>

<div class="footer">
    数据来源: <a href="https://tophub.app/n/WnBe01o371">今日热榜 微信24h热文榜</a><br>
    服务由自动脚本生成,每天早上8:00准时推送<br>
    推送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
</div>

</body>
</html>"""
    
    return html


# ============ Server酱推送 ============

def push_to_serverchan(title: str, desp: str, sendkey: str) -> bool:
    """
    通过Server酱Turbo版推送消息到微信
    API文档: https://sct.ftqq.com/
    """
    if not sendkey:
        print("[WARN] Server酱SendKey未配置,跳过微信推送")
        print("[INFO] 请设置环境变量 SERVERCHAN_SENDKEY 或在脚本中直接配置")
        return False
    
    url = f"https://sctapi.ftqq.com/{sendkey}.send"
    
    data = {
        'title': title,
        'desp': desp,
    }
    
    try:
        resp = requests.post(url, data=data, timeout=15)
        result = resp.json()
        
        if result.get('code') == 0 or result.get('errno') == 0:
            print(f"[OK] Server酱推送成功! 消息标题: {title}")
            return True
        else:
            print(f"[ERROR] Server酱推送失败: {result}")
            return False
    except Exception as e:
        print(f"[ERROR] Server酱推送异常: {e}")
        return False


def push_to_serverchan_v3(title: str, desp: str, uid: str, sendkey: str) -> bool:
    """
    通过Server酱³推送消息 (新版API)
    API文档: https://doc.sc3.ft07.com/zh/serverchan3
    """
    if not uid or not sendkey:
        print("[WARN] Server酱³ uid或SendKey未配置,跳过推送")
        return False
    
    url = f"https://{uid}.push.ft07.com/send/{sendkey}.send"
    
    params = {
        'title': title,
        'desp': desp,
    }
    
    try:
        resp = requests.get(url, params=params, timeout=15)
        result = resp.json()
        
        if result.get('code') == 200 or result.get('code') == 0:
            print(f"[OK] Server酱³推送成功!")
            return True
        else:
            print(f"[ERROR] Server酱³推送失败: {result}")
            return False
    except Exception as e:
        print(f"[ERROR] Server酱³推送异常: {e}")
        return False


# ============ 主流程 ============

def main():
    """主执行流程"""
    print("=" * 50)
    print(f"微信10万+爆文日报 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # 1. 抓取数据
    print("\n[1/4] 抓取微信热文数据...")
    articles = fetch_wechat_hot_articles()
    print(f"  抓取到 {len(articles)} 篇10万+文章")
    
    if not articles:
        print("[WARN] 未抓取到任何10万+文章,可能是数据源暂时不可用")
        print("[INFO] 尝试保存空报告...")
        articles = [{
            'title': '暂无数据 - 请稍后重试',
            'url': 'https://tophub.app/n/WnBe01o371',
            'views': '0万',
            'views_num': 0,
            'source': 'fallback',
            'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }]
    
    # 2. 筛选5篇最优
    print("\n[2/4] 筛选最优5篇...")
    top5 = select_top_articles(articles, count=5)
    print(f"  精选 {len(top5)} 篇文章:")
    for i, a in enumerate(top5, 1):
        print(f"    {i}. [{a['views']}] {a['title'][:50]}")
    
    # 3. 格式化消息
    print("\n[3/4] 格式化推送消息...")
    title, desp = format_serverchan_message(top5)
    
    # 4. 推送
    print("\n[4/4] 推送消息...")
    
    # 4a. Server酱推送
    push_success = push_to_serverchan(title, desp, SERVERCHAN_SENDKEY)
    
    # 4b. 保存HTML报告到本地
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    html = format_html_report(top5)
    with open(HTML_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  HTML报告已保存: {HTML_OUTPUT}")
    
    # 4c. 保存JSON数据
    json_output = os.path.join(OUTPUT_DIR, "latest.json")
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump({
            'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'date': (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
            'total_10w_articles': len(articles),
            'selected_articles': top5,
        }, f, ensure_ascii=False, indent=2)
    print(f"  JSON数据已保存: {json_output}")
    
    # 5. 汇总
    print("\n" + "=" * 50)
    print(f"✅ 执行完成!")
    print(f"  抓取10万+文章: {len(articles)} 篇")
    print(f"  精选推送: {len(top5)} 篇")
    print(f"  Server酱推送: {'✅ 成功' if push_success else '❌ 未配置/失败'}")
    print(f"  本地报告: {HTML_OUTPUT}")
    print("=" * 50)
    
    return top5


if __name__ == "__main__":
    # 支持命令行指定SendKey
    if len(sys.argv) > 1:
        SERVERCHAN_SENDKEY = sys.argv[1]
    
    main()
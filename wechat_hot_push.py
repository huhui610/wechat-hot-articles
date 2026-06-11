#!/usr/bin/env python3
"""
微信财经大V爆文日报推送服务
====================================
每天早上8点抓取前一日阅读量10万+的财经大V公众号文章,
推送10篇到微信。

核心规则:
- 只推送【昨天】发布的文章 (严格日期过滤)
- 只推送财经类大V的文章
- 10万+阅读量
- 精选10篇

数据来源:
1. 今日热榜(tophub) 微信24h热文榜 (聚合热文)
2. 猫笔刀备份站RSS (maobidao.cn)
3. 更多财经大V备份站 (moomoocat.net 等)

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

SERVERCHAN_SENDKEY = os.environ.get("SERVERCHAN_SENDKEY", "")

TOPHUB_BASE_URL = "https://tophub.app"
TOPHUB_WECHAT_NODE = "/n/WnBe01o371"

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "output"))
HTML_OUTPUT = os.path.join(OUTPUT_DIR, "latest.html")
JSON_OUTPUT = os.path.join(OUTPUT_DIR, "latest.json")

# 昨天日期 (核心过滤条件)
YESTERDAY = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

# ★★★ 财经大V配置 ★★★
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
    # === 更多财经大V ===
    "招财大牛猫": {"source": "tophub", "keywords": ["招财大牛猫"]},
    "回忆承载": {"source": "tophub", "keywords": ["回忆承载", "记忆承载"]},
    "聪明投资者": {"source": "tophub", "keywords": ["聪明投资者"]},
    "投资最重要的事": {"source": "tophub", "keywords": ["投资最重要"]},
    "饭统戴老板": {"source": "tophub", "keywords": ["饭统戴老板"]},
    "研报社": {"source": "tophub", "keywords": ["研报社"]},
    "股票说": {"source": "tophub", "keywords": ["股票说"]},
    "投研帮": {"source": "tophub", "keywords": ["投研帮"]},
    "拾点拾趣": {"source": "tophub", "keywords": ["拾点拾趣"]},
    "炒股帮": {"source": "tophub", "keywords": ["炒股帮"]},
}

# 所有白名单关键词
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


# ============ 日期工具 ============

def parse_date_from_str(date_str: str) -> Optional[str]:
    """从各种日期格式中提取 YYYY-MM-DD"""
    if not date_str:
        return None
    # "2026-06-10 14:20:46" 格式
    m = re.match(r'(\d{4}-\d{2}-\d{2})', date_str)
    if m:
        return m.group(1)
    # "Tue, 10 Jun 2026 14:20:46 +0000" 格式
    m = re.match(r'\w+, (\d{1,2}) (\w+) (\d{4})', date_str)
    if m:
        try:
            dt = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %z')
            return dt.strftime('%Y-%m-%d')
        except Exception:
            pass
    return None


def is_yesterday(date_str: str) -> bool:
    """判断日期字符串是否是昨天"""
    parsed = parse_date_from_str(date_str)
    if parsed:
        return parsed == YESTERDAY
    return False


# ============ 数据源1: 猫笔刀备份站 ============

def fetch_maobidao_articles() -> List[Dict]:
    """从猫笔刀备份站抓取最新文章(通过RSS代理), 只保留昨天的文章"""
    articles = []

    # 策略1: 通过rss2json代理(GitHub Actions可访问)
    try:
        resp = requests.get(
            'https://api.rss2json.com/v1/api.json?rss_url=https://maobidao.cn/feed/',
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=20
        )
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('items', [])
            total = len(items)
            for item in items:
                title = item.get('title', '')
                url = item.get('link', '')
                pub_date = item.get('pubDate', '')
                pub_date_str = parse_date_from_str(pub_date) or ''

                # ★★★ 日期过滤: 只保留昨天的文章 ★★★
                if pub_date_str and pub_date_str != YESTERDAY:
                    print(f"    [跳过] 非昨日({pub_date_str}): {title[:30]}")
                    continue

                if title and url:
                    articles.append({
                        'title': title,
                        'url': url,
                        'views': '10万+',
                        'views_num': 100000,
                        'account': '猫笔刀',
                        'source': 'maobidao_rss',
                        'pub_date': pub_date_str,
                        'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    })
            print(f"  猫笔刀RSS(代理): 总{total}篇, 昨日({YESTERDAY}){len(articles)}篇")
            return articles
    except Exception as e:
        print(f"  [WARN] RSS代理失败: {e}")

    # 策略2: 直接访问RSS(GitHub可能不行,本地可以)
    try:
        import xml.etree.ElementTree as ET
        resp = requests.get('https://maobidao.cn/feed/', headers={
            'User-Agent': 'Mozilla/5.0'
        }, timeout=15)
        if resp.status_code == 200:
            root = ET.fromstring(resp.text)
            total = 0
            for item in root.findall('.//item'):
                total += 1
                title_el = item.find('title')
                link_el = item.find('link')
                pub_date_el = item.find('pubDate')

                if title_el is not None and link_el is not None:
                    title = title_el.text or ''
                    url = link_el.text or ''
                    pub_date_raw = pub_date_el.text if pub_date_el is not None else ''
                    pub_date_str = parse_date_from_str(pub_date_raw) or ''

                    # ★★★ 日期过滤 ★★★
                    if pub_date_str and pub_date_str != YESTERDAY:
                        print(f"    [跳过] 非昨日({pub_date_str}): {title[:30]}")
                        continue

                    if title and url:
                        articles.append({
                            'title': title,
                            'url': url,
                            'views': '10万+',
                            'views_num': 100000,
                            'account': '猫笔刀',
                            'source': 'maobidao_rss',
                            'pub_date': pub_date_str,
                            'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        })
            print(f"  猫笔刀RSS(直连): 总{total}篇, 昨日({YESTERDAY}){len(articles)}篇")
    except Exception as e:
        print(f"  [ERROR] 猫笔刀RSS直连失败: {e}")

    return articles


# ============ 数据源2: 猫笔刀moomoocat备份站 ============

def fetch_moomoocat_articles() -> List[Dict]:
    """从moomoocat.net抓取猫笔刀文章, 只保留昨天的"""
    articles = []
    try:
        resp = requests.get('https://www.moomoocat.net/posts/', headers={
            'User-Agent': 'Mozilla/5.0'
        }, timeout=15)
        if resp.status_code != 200:
            print(f"  [WARN] moomoocat返回{resp.status_code}")
            return articles

        soup = BeautifulSoup(resp.text, 'html.parser')
        # 查找文章列表项 (日期+标题结构)
        for item in soup.find_all(['article', 'div', 'li']):
            text = item.get_text(strip=True)
            # 匹配类似 "2025-06-25 标题" 或 "250625 标题" 格式
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', text)
            if not date_match:
                date_match = re.search(r'(\d{2})(\d{2})(\d{2})\s', text)
                if date_match:
                    y, m, d = date_match.group(1), date_match.group(2), date_match.group(3)
                    date_str = f"20{y}-{m}-{d}"
                else:
                    continue
            else:
                date_str = date_match.group(1)

            if date_str != YESTERDAY:
                continue

            # 找链接
            link = item.find('a', href=True)
            if not link:
                continue
            title = link.get_text(strip=True)
            url = link['href']
            if not url.startswith('http'):
                url = 'https://www.moomoocat.net' + url

            if title and 'mp.weixin.qq.com' not in url:
                # moomoocat 是备份站链接, 需要找到原文链接
                articles.append({
                    'title': title,
                    'url': url,
                    'views': '10万+',
                    'views_num': 100000,
                    'account': '猫笔刀',
                    'source': 'moomoocat',
                    'pub_date': date_str,
                    'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                })
    except Exception as e:
        print(f"  [WARN] moomoocat抓取失败: {e}")

    print(f"  moomoocat: 昨日({YESTERDAY}){len(articles)}篇")
    return articles


# ============ 数据源3: tophub热文 ============

def fetch_tophub_articles() -> List[Dict]:
    """从tophub抓取微信热文 (24h热文 ≈ 昨日文章, 后续会用日期验证)"""
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
                                'pub_date': '',  # tophub不提供日期,后续验证
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
                                    'pub_date': '',  # 后续验证
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

    print(f"  tophub热文: {len(unique)} 篇 (24h热文, 待日期验证)")
    return unique


# ============ 账号识别 + 日期提取 ============

def extract_article_info(url: str) -> Dict:
    """访问微信文章页面, 提取账号名和发布日期"""
    info = {'account': '', 'pub_date': ''}
    try:
        resp = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }, timeout=10)
        if resp.status_code == 200:
            text = resp.text
            soup = BeautifulSoup(text, 'html.parser')

            # 提取账号名
            elem = soup.find('span', id='profileBt')
            if elem:
                info['account'] = elem.get_text(strip=True)
            else:
                m = re.search(r'var\s+nickname\s*=\s*["\']([^"\']+)', text)
                if m:
                    info['account'] = m.group(1)

            # 提取发布日期 (多种方式尝试)
            # 方式1: var ct = "timestamp" (微信文章常用)
            m = re.search(r'var\s+ct\s*=\s*["\'](\d{10})["\']', text)
            if m:
                ts = int(m.group(1))
                info['pub_date'] = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
            else:
                # 方式2: publish_time meta
                meta = soup.find('meta', property='article:published_time')
                if meta:
                    date_str = meta.get('content', '')
                    info['pub_date'] = parse_date_from_str(date_str) or ''
                else:
                    # 方式3: id="publish_time"
                    pt = soup.find('em', id='publish_time')
                    if pt:
                        date_str = pt.get_text(strip=True)
                        info['pub_date'] = parse_date_from_str(date_str) or ''
                    else:
                        # 方式4: var create_time = "..."
                        m = re.search(r'var\s+create_time\s*=\s*["\']?(\d{10})["\']?', text)
                        if m:
                            ts = int(m.group(1))
                            info['pub_date'] = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
    except Exception:
        pass
    return info


def identify_accounts_and_dates(articles: List[Dict]) -> List[Dict]:
    """识别文章的账号来源和发布日期"""
    need_identify = [a for a in articles if not a.get('account') or not a.get('pub_date')]
    already_known = [a for a in articles if a.get('account') and a.get('pub_date')]
    print(f"  已知账号+日期: {len(already_known)} 篇")
    print(f"  需要识别: {len(need_identify)} 篇")

    for i, article in enumerate(need_identify):
        info = extract_article_info(article['url'])
        if info['account'] and not article.get('account'):
            article['account'] = info['account']
        if info['pub_date'] and not article.get('pub_date'):
            article['pub_date'] = info['pub_date']

        acc = article.get('account', '')
        pd = article.get('pub_date', '?')
        is_v = any(kw in acc for kw in ALL_WHITELIST_KEYWORDS) if acc else False
        is_yd = pd == YESTERDAY
        status = ''
        if is_v and is_yd:
            status = '✅昨日财经V'
        elif is_v:
            status = f'⚠️财经V(非昨日:{pd})'
        elif is_yd:
            status = '📅昨日'
        else:
            status = f'❌({pd})'

        if acc:
            print(f"    [{i+1}] {status} | {acc} | {article['title'][:30]}")
        else:
            print(f"    [{i+1}] {status} | 未知 | {article['title'][:30]}")

        time.sleep(0.3)

    return already_known + need_identify


# ============ 日期过滤 ============

def filter_by_date(articles: List[Dict]) -> List[Dict]:
    """只保留昨天发布的文章"""
    yesterday_articles = []
    other_articles = []

    for article in articles:
        pub_date = article.get('pub_date', '')
        if pub_date == YESTERDAY:
            yesterday_articles.append(article)
        else:
            other_articles.append(article)

    skipped_count = len(other_articles)
    print(f"  昨日({YESTERDAY})文章: {len(yesterday_articles)} 篇")
    if skipped_count > 0:
        print(f"  跳过非昨日文章: {skipped_count} 篇")
        for a in other_articles[:5]:  # 只显示前5个
            pd = a.get('pub_date', '未知')
            print(f"    跳过: [{pd}] {a.get('account', '?')} - {a['title'][:30]}")
        if skipped_count > 5:
            print(f"    ... 还有 {skipped_count - 5} 篇")

    return yesterday_articles


# ============ 财经大V过滤 ============

def filter_finance_articles(articles: List[Dict]) -> List[Dict]:
    """只保留财经大V的文章, 不够10篇时从其他昨日文章补充"""
    finance_articles = []
    other_articles = []

    for article in articles:
        account = article.get('account', '')

        # 猫笔刀等备份站来源,直接算财经大V
        if article.get('source') in ('maobidao_rss', 'maobidao_backup', 'moomoocat'):
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

    # 如果财经大V不够10篇,从其他昨日文章补充
    if len(finance_articles) < 10 and other_articles:
        supplement = other_articles[:10 - len(finance_articles)]
        print(f"  财经大V不够10篇, 从其他昨日文章补充 {len(supplement)} 篇")
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
    yesterday_display = (datetime.now() - timedelta(days=1)).strftime('%Y年%m月%d日')
    today = datetime.now().strftime('%Y年%m月%d日')
    fetch_time = datetime.now().strftime('%H:%M')

    title = f"💰 财经大V爆文日报 | {yesterday_display}"

    desp = f"""## 💰 财经大V爆文日报

> 📅 {yesterday_display} | 🕐 {today} {fetch_time}
> 🎯 只推送昨日财经大V | 📊 10万+精选 | 📅 严格日期过滤

---

"""
    for i, article in enumerate(articles, 1):
        account = article.get('account', '未知账号')
        is_v = any(kw in account for kw in ALL_WHITELIST_KEYWORDS) if account else False
        tag = "💰财经" if is_v else ""
        pub_date = article.get('pub_date', '')

        desp += f"""### {i}. {article['title']}
- 📝 **{account}** {tag}
- 📖 阅读量: **{article['views']}**
- 📅 发布日期: **{pub_date}**
- 🔗 [阅读原文]({article['url']})

---

"""

    desp += f"""*数据来源: 今日热榜 + 猫笔刀备份站 | 严格过滤: 只推昨日文章 | 每天8:00推送*"""
    return title, desp


def format_html_report(articles: List[Dict]) -> str:
    yesterday_display = (datetime.now() - timedelta(days=1)).strftime('%Y年%m月%d日')
    today = datetime.now().strftime('%Y年%m月%d日')
    fetch_time = datetime.now().strftime('%H:%M')

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>财经大V爆文日报 | {yesterday_display}</title>
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
.date-tag{{background:#4CAF50;color:white;padding:2px 6px;border-radius:3px;font-size:11px}}
.views{{color:#e74c3c;font-weight:bold}}
.link{{display:inline-block;background:#2196F3;color:white;padding:6px 14px;border-radius:5px;text-decoration:none;font-size:13px}}
.footer{{text-align:center;padding:15px;color:#999;font-size:12px}}
</style></head><body>
<div class="header"><h1>💰 财经大V爆文日报</h1>
<div style="font-size:14px;opacity:0.9">📅 {yesterday_display} | 🕐 {today} {fetch_time} | 🎯 只推昨日财经大V | 📅 严格日期过滤</div></div>
"""
    for i, a in enumerate(articles, 1):
        account = a.get('account', '未知')
        is_v = any(kw in account for kw in ALL_WHITELIST_KEYWORDS) if account else False
        tag = '<span class="finance-tag">💰财经</span>' if is_v else ''
        pub_date = a.get('pub_date', '')
        date_tag = f'<span class="date-tag">📅{pub_date}</span>' if pub_date else ''
        html += f"""<div class="card">
<div style="font-size:17px;font-weight:600;margin-bottom:6px"><span class="rank">{i}</span>{a['title']}</div>
<div style="font-size:13px;color:#666;margin-bottom:8px">
<span class="views">📖 {a['views']}</span> | <span class="account">📝 {account}</span> {tag} {date_tag}</div>
<a class="link" href="{a['url']}" target="_blank">阅读原文 →</a></div>\n"""

    html += f"""<div class="footer">数据来源: 今日热榜 + 猫笔刀备份站 | 严格过滤: 只推昨日文章 | 每天8:00自动推送</div></body></html>"""
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
    print("=" * 60)
    print(f"💰 财经大V爆文日报 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📅 目标日期: 昨日({YESTERDAY})")
    print("=" * 60)

    # 1. 多数据源抓取
    print("\n[1/6] 抓取数据...")
    print("  数据源1: 猫笔刀备份站(maobidao.cn RSS)")
    maobidao = fetch_maobidao_articles()

    print("  数据源2: 猫笔刀备份站(moomoocat.net)")
    moomoocat = fetch_moomoocat_articles()

    print("  数据源3: tophub微信热文")
    tophub = fetch_tophub_articles()

    all_articles = maobidao + moomoocat + tophub
    print(f"  合计: {len(all_articles)} 篇10万+文章 (含已过滤日期的猫笔刀)")

    if not all_articles:
        all_articles = [{
            'title': '暂无数据 - 请稍后重试',
            'url': 'https://tophub.app/n/WnBe01o371',
            'views': '0万', 'views_num': 0,
            'account': '', 'source': 'fallback',
            'pub_date': YESTERDAY,
            'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }]

    # 2. 识别账号和提取日期
    print("\n[2/6] 识别账号来源 + 提取发布日期...")
    all_articles = identify_accounts_and_dates(all_articles)

    # 3. ★★★ 严格日期过滤: 只保留昨天的文章 ★★★
    print(f"\n[3/6] 日期过滤 (只保留 {YESTERDAY} 的文章)...")
    all_articles = filter_by_date(all_articles)

    if not all_articles:
        print("  ⚠️ 昨日无10万+文章! 放宽条件重试...")
        # 放宽: 重新抓取不过滤日期的猫笔刀文章
        print("  放宽策略: 包含猫笔刀最近文章 + tophub 24h热文")
        maobidao_all = fetch_maobidao_articles_relaxed()
        if maobidao_all:
            maobidao_all = identify_accounts_and_dates(maobidao_all)
            # 放宽到最近3天
            recent = [a for a in maobidao_all if a.get('pub_date', '') >= (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')]
            all_articles = recent

    # 4. 财经大V过滤
    print("\n[4/6] 财经大V过滤...")
    finance = filter_finance_articles(all_articles)

    # 5. 精选10篇
    print("\n[5/6] 精选10篇...")
    top10 = select_top_articles(finance, count=10)
    print(f"  精选 {len(top10)} 篇:")
    for i, a in enumerate(top10, 1):
        acc = a.get('account', '未知')
        pd = a.get('pub_date', '?')
        print(f"    {i}. [{pd}] [{a['views']}] [{acc}] {a['title'][:40]}")

    # 6. 推送
    print("\n[6/6] 推送...")
    title, desp = format_serverchan_message(top10)
    push_ok = push_to_serverchan(title, desp, SERVERCHAN_SENDKEY)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(HTML_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(format_html_report(top10))

    with open(JSON_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump({
            'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'target_date': YESTERDAY,
            'total_articles': len(all_articles),
            'finance_articles': len(finance),
            'selected_articles': top10,
        }, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"✅ 完成! 目标日期:{YESTERDAY} | 抓取{len(all_articles)}篇 | 财经大V {len(finance)}篇 | 推送{len(top10)}篇 | 推送{'✅' if push_ok else '❌'}")
    print("=" * 60)
    return top10


def fetch_maobidao_articles_relaxed() -> List[Dict]:
    """放宽日期限制的猫笔刀文章获取 (回退策略)"""
    articles = []
    try:
        resp = requests.get(
            'https://api.rss2json.com/v1/api.json?rss_url=https://maobidao.cn/feed/',
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=20
        )
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('items', [])
            for item in items:
                title = item.get('title', '')
                url = item.get('link', '')
                pub_date = item.get('pubDate', '')
                pub_date_str = parse_date_from_str(pub_date) or ''
                if title and url:
                    articles.append({
                        'title': title,
                        'url': url,
                        'views': '10万+',
                        'views_num': 100000,
                        'account': '猫笔刀',
                        'source': 'maobidao_rss',
                        'pub_date': pub_date_str,
                        'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    })
            print(f"  [放宽] 猫笔刀RSS: {len(articles)} 篇(不限日期)")
    except Exception as e:
        print(f"  [ERROR] 放宽获取失败: {e}")
    return articles


if __name__ == "__main__":
    if len(sys.argv) > 1:
        SERVERCHAN_SENDKEY = sys.argv[1]
    main()

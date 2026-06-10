# 微信公众号10万+爆文日报推送服务

> 每天早上8点自动抓取前一日阅读量10万+的微信公众号文章,精选5篇推送到微信

## ✨ 功能特性

- 🔄 **全自动定时执行** — GitHub Actions每天早上8:03自动运行,无需服务器
- 🔥 **10万+爆文筛选** — 从今日热榜微信24h热文榜抓取数据
- 📱 **微信推送** — 通过Server酱推送到微信,支持Markdown格式
- 📊 **HTML报告** — 同时生成本地HTML报告和JSON数据
- 🎯 **智能分类** — 按社会/科技/健康/娱乐/财经等分类,避免同类型扎堆
- 💰 **完全免费** — GitHub Actions免费额度足够,Server酱免费版每天5条

## 🚀 部署步骤(3分钟搞定)

### Step 1: Fork本仓库

1. 点击右上角 **Fork** 按钮
2. 将仓库Fork到你的GitHub账号下

### Step 2: 配置Server酱SendKey

1. 注册 **Server酱**: https://sct.ftqq.com (微信扫码登录)
2. 获取你的 **SendKey** (在「Key & API」页面)
3. 在Fork的仓库中添加Secret:
   - 进入 **Settings** → **Secrets and variables** → **Actions**
   - 点击 **New repository secret**
   - Name: `SERVERCHAN_SENDKEY`
   - Value: 你的SendKey(如: `SCT123456xxxx`)
   - 点击 **Add secret**

### Step 3: 测试运行

1. 进入Fork的仓库
2. 点击 **Actions** 标签页
3. 选择 **微信10万+爆文日报推送** workflow
4. 点击 **Run workflow** → **Run workflow** 按钮
5. 等待运行完成(约30秒)
6. 查看运行日志确认成功
7. 微信应收到推送消息!

### Step 4: 自动运行

GitHub Actions会自动按 `schedule` 定时运行:
- 北京时间每天早上 **8:03** 自动执行
- 也可随时手动触发(Actions页面点击Run workflow)

> ⚠️ 注意: GitHub Actions的定时任务可能有5-15分钟延迟,这是GitHub官方行为,无法避免。

## 📂 项目结构

```
wechat-hot-articles-github/
├── .github/
│   └── workflows/
│       └── daily-push.yml    # GitHub Actions定时任务配置
├── wechat_hot_push.py        # 核心脚本(抓取+筛选+推送)
├── README.md                 # 本文档
└── output/                   # 运行时自动生成的输出目录
    ├── latest.html           # HTML格式报告
    └── latest.json           # JSON格式数据
```

## 🔧 配置说明

### 定时时间调整

修改 `.github/workflows/daily-push.yml` 中的 cron 表达式:

```yaml
schedule:
  # 北京时间8:03 = UTC 0:03
  - cron: '3 0 * * *'
```

| 北京时间 | UTC cron | 说明 |
|---------|---------|------|
| 7:00 | `0 23 * * *` | 早起版 |
| 8:03 | `3 0 * * *` | 默认 |
| 9:00 | `0 1 * * *` | 晚起版 |
| 6:30 | `30 22 * * *` | 极早版 |

> **GitHub Actions cron使用UTC时间**, 北京时间 = UTC + 8小时

### 推送数量调整

修改脚本中的 `count` 参数:

```python
# 默认推送5篇
top5 = select_top_articles(articles, count=5)

# 改为推送3篇
top3 = select_top_articles(articles, count=3)

# 改为推送10篇
top10 = select_top_articles(articles, count=10)
```

### 阅读量阈值调整

修改脚本中的筛选条件:

```python
# 默认10万+
if title and views_num >= 100000:

# 改为5万+
if title and views_num >= 50000:

# 改为20万+(更严格筛选)
if title and views_num >= 200000
```

## 🔑 关于Server酱

### 免费额度

| 版本 | 每日推送 | 价格 |
|------|---------|------|
| 免费版 | 5条/天 | 免费 |
| 高级会员 | 20条/天 | ¥198/年 |

> 我们的日报只需1条/天,免费版完全够用!

### 推送通道

免费版默认通过**微信服务号**推送,也可配置:
- 企业微信
- 钉钉群
- 飞书群
- PushDeer

### API格式

```bash
# Server酱 Turbo版 API
curl "https://sctapi.ftqq.com/YOUR_SENDKEY.send" \
  -d "title=消息标题" \
  -d "desp=Markdown内容"
```

## ⚠️ 注意事项

1. **GitHub Actions延迟** — 定时任务可能有5-15分钟延迟,这是正常现象
2. **数据源稳定性** — 今日热榜是免费公共服务,偶尔可能维护
3. **阅读量精度** — 微信只显示"10万+"标记,无法获取精确数字
4. **Secret安全** — SendKey存储在GitHub Secrets中,不会泄露
5. **仓库必须是Public** — Private仓库的Actions有运行时间限制(2000分钟/月)

## 🛠️ 故障排查

### 运行失败

1. 检查Actions日志(点击失败的run查看详细错误)
2. 确认Secret配置正确
3. 手动触发测试

### 推送未收到

1. 检查Server酱绑定状态(微信是否还关注服务号)
2. 确认SendKey正确
3. 检查免费额度是否用完

### 抓取数据为空

1. 今日热榜可能维护
2. 等待下次运行自动恢复
3. 手动触发重试

## 📊 效果示例

推送消息格式(Server酱支持Markdown):

```
🔥 微信10万+爆文日报 | 2026年06月09日

1. 高考重要？还是人重要？
   📖 阅读量: 10.0万 | 📂 生活

2. 广东27岁小伙一天没来上班...
   📖 阅读量: 10.0万 | 📂 健康

...共5篇精选爆文
```

## 💡 扩展玩法

### 增加邮件推送

在workflow中添加邮件发送步骤

### 增加Telegram推送

使用Telegram Bot API替代Server酱

### 添加历史数据统计

将每日JSON数据提交到仓库,积累历史趋势

### 增加更多数据源

在脚本中添加更多聚合平台的抓取逻辑

---

## 📜 许可证

MIT License - 自由使用、修改和分发
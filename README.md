# GitHub 热门项目中文邮件

每天自动采集 GitHub 日榜和周榜，保存热门项目、总 Star、近期新增 Star 和每日快照。

## 自动运行

- GitHub Actions：每天北京时间 08:05 生成 `reports/latest.md` 和 `reports/latest.json`。
- Mac 2019 WorkBuddy：每天 08:30 读取最新报告，生成简洁中文解读，通过已授权的 agent-mail 发往指定邮箱。
- GitHub Actions 不保存邮箱密码或 SMTP 授权码。

## 数据口径

GitHub 没有公开 Trending API。本项目读取公开 Trending 页面，并用连续快照计算总 Star 的日间变化。首次运行只建立基线，从第二天开始显示快照增量。

## 本地运行

```bash
python3 scripts/generate_report.py
```

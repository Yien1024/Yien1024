import requests
import os
from datetime import datetime, timedelta
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# ---------------- 自动获取 GitHub 用户名 ----------------
repo_full = os.environ.get('GITHUB_REPOSITORY', '')
if repo_full:
    USERNAME = repo_full.split('/')[0]
else:
    USERNAME = '你的GitHub用户名'

TOKEN = os.environ.get('GH_TOKEN')
if not TOKEN:
    raise RuntimeError('环境变量 GH_TOKEN 未设置')

HEADERS = {'Authorization': f'bearer {TOKEN}'}

# ---------------- GraphQL：获取贡献日历数据（只用于折线图和 streak） ----------------
def get_contribution_calendar():
    query = '''
    query($username: String!) {
      user(login: $username) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
                color
              }
            }
          }
        }
      }
    }
    '''
    res = requests.post('https://api.github.com/graphql',
                        json={'query': query, 'variables': {'username': USERNAME}},
                        headers=HEADERS)
    res.raise_for_status()
    data = res.json()
    return data['data']['user']['contributionsCollection']['contributionCalendar']

# ---------------- REST：近期事件统计（含代码审查） ----------------
def get_recent_stats(days):
    url = f'https://api.github.com/users/{USERNAME}/events/public'
    res = requests.get(url, headers=HEADERS)
    res.raise_for_status()
    events = res.json()

    cutoff = datetime.utcnow() - timedelta(days=days)
    commits = prs = issues = reviews = 0
    for e in events:
        e_date = datetime.strptime(e['created_at'], '%Y-%m-%dT%H:%M:%SZ')
        if e_date < cutoff:
            continue
        t = e['type']
        if t == 'PushEvent':
            commits += len(e['payload'].get('commits', []))
        elif t == 'PullRequestEvent' and e['payload']['action'] == 'opened':
            prs += 1
        elif t == 'IssuesEvent' and e['payload']['action'] == 'opened':
            issues += 1
        elif t == 'PullRequestReviewEvent' and e['payload']['action'] == 'submitted':
            reviews += 1
    return (commits, prs, issues, reviews)

# ---------------- 绘制近 7 天贡献折线图 ----------------
def draw_weekly_line_chart(weeks_data, filename):
    today = datetime.utcnow().date()
    dates = []
    counts = []
    for week in weeks_data:
        for day in week['contributionDays']:
            d = datetime.strptime(day['date'], '%Y-%m-%d').date()
            if 0 <= (today - d).days < 7:
                dates.append(d.strftime('%m-%d'))
                counts.append(day['contributionCount'])
    if not dates:
        plt.figure(figsize=(6, 3))
        plt.text(0.5, 0.5, 'No recent data', ha='center', va='center')
        plt.title('Daily Contributions (Last 7 days)')
        plt.tight_layout()
        plt.savefig(filename, dpi=120)
        plt.close()
        return
    sorted_pairs = sorted(zip(dates, counts))
    dates, counts = zip(*sorted_pairs)

    plt.figure(figsize=(6, 3))
    plt.plot(dates, counts, marker='o', color='#2ea44f', linewidth=2)
    plt.fill_between(range(len(dates)), counts, alpha=0.1, color='#2ea44f')
    plt.title('Daily Contributions (Last 7 days)')
    plt.ylabel('Contributions')
    plt.tight_layout()
    plt.savefig(filename, dpi=120)
    plt.close()

# ---------------- 最活跃仓库 Top 5 ----------------
def top_repos(days=90):
    url = f'https://api.github.com/users/{USERNAME}/events/public?per_page=100'
    res = requests.get(url, headers=HEADERS)
    res.raise_for_status()
    events = res.json()
    cutoff = datetime.utcnow() - timedelta(days=days)

    repo_commits = {}
    for e in events:
        if datetime.strptime(e['created_at'], '%Y-%m-%dT%H:%M:%SZ') < cutoff:
            continue
        if e['type'] == 'PushEvent':
            repo_name = e['repo']['name']
            commits = len(e['payload'].get('commits', []))
            repo_commits[repo_name] = repo_commits.get(repo_name, 0) + commits

    top5 = sorted(repo_commits.items(), key=lambda x: x[1], reverse=True)[:5]
    return top5

def format_top_repos(top5):
    if not top5:
        return "近期暂无提交数据"
    lines = []
    for i, (repo, count) in enumerate(top5, 1):
        lines.append(f"| {i} | **{repo}** | {count} 次提交 |")
    header = "| # | 仓库 | 提交次数 |\n|--|------|--------|\n"
    return header + '\n'.join(lines)

# ---------------- 连续贡献天数 ----------------
def calculate_streak(weeks_data):
    daily = {}
    for week in weeks_data:
        for day in week['contributionDays']:
            daily[datetime.strptime(day['date'], '%Y-%m-%d').date()] = day['contributionCount']

    today = datetime.utcnow().date()
    streak = 0
    check_date = today
    if daily.get(check_date, 0) == 0:
        check_date -= timedelta(days=1)

    while daily.get(check_date, 0) > 0:
        streak += 1
        check_date -= timedelta(days=1)
    return streak

# ---------------- 生成 README.md（移除日历图，保留文字表格和折线图） ----------------
def generate_readme(monthly, yearly, streak, top_repos_md):
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    readme = f"""# Hi there 👋

## 📊 GitHub 活动报告
> 自动更新于 {now}

### 🔥 连续贡献
当前连续 **{streak}** 天

### 📈 近 7 天贡献趋势
![近7天趋势](weekly_line.png)

### 🏆 最近活跃仓库 Top 5
{top_repos_md}

### 📅 月报（近 30 天）
| 代码提交 | 发起 PR | 新建 Issue | 代码审查 |
|--------|--------|----------|--------|
| **{monthly[0]}** 次 | **{monthly[1]}** 个 | **{monthly[2]}** 个 | **{monthly[3]}** 次 |

### 📅 年报（近 365 天）
| 代码提交 | 发起 PR | 新建 Issue | 代码审查 |
|--------|--------|----------|--------|
| **{yearly[0]}** 次 | **{yearly[1]}** 个 | **{yearly[2]}** 个 | **{yearly[3]}** 次 |

---

### ✨ GitHub 统计
![GitHub stats](https://github-readme-stats.vercel.app/api?username={USERNAME}&show_icons=true&theme=github&hide_border=true)
![Top Langs](https://github-readme-stats.vercel.app/api/top-langs/?username={USERNAME}&layout=compact&theme=github&hide_border=true)
![GitHub streak](https://github-readme-streak-stats.herokuapp.com/?user={USERNAME}&theme=github&hide_border=true)

---
*✨ 此报告由 GitHub Actions 每天自动生成*
"""
    return readme

# ---------------- 主流程 ----------------
def main():
    print('🚀 开始生成报告...')

    calendar = get_contribution_calendar()

    # 近7天折线图
    draw_weekly_line_chart(calendar['weeks'], 'weekly_line.png')
    print('✅ 近7天趋势图已生成')

    # 连续贡献
    streak = calculate_streak(calendar['weeks'])
    print(f'🔥 当前连续贡献 {streak} 天')

    # 月报/年报
    m = get_recent_stats(30)
    y = get_recent_stats(365)

    # 活跃仓库
    top5 = top_repos(days=90)
    top_repos_md = format_top_repos(top5)

    # 生成 README
    readme = generate_readme(m, y, streak, top_repos_md)
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(readme)
    print('✅ README.md 已更新')

    with open('stats.txt', 'w') as f:
        f.write(f'Monthly: {m}\nYearly: {y}\nStreak: {streak}\n')

if __name__ == '__main__':
    main()

import requests
import os
from datetime import datetime, timedelta
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ---------------- 自动获取 GitHub 用户名 ----------------
repo_full = os.environ.get('GITHUB_REPOSITORY', '')
if repo_full:
    USERNAME = repo_full.split('/')[0]
else:
    USERNAME = '你的GitHub用户名'   # 本地测试时可手动填写

TOKEN = os.environ.get('GH_TOKEN')
if not TOKEN:
    raise RuntimeError('环境变量 GH_TOKEN 未设置')

HEADERS = {'Authorization': f'bearer {TOKEN}'}

# ---------------- GraphQL：获取贡献日历 ----------------
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

# ---------------- 绘制日历热力图（GitHub 风格，无数字，有图例） ----------------
def draw_calendar_heatmap(weeks_data, filename):
    """
    周一起始（周一=1 ... 周日=7）的贡献日历热力图。
    格子颜色深度表示贡献量，不显示数字，右下角添加颜色图例。
    """
    num_weeks = len(weeks_data)
    grid = np.zeros((7, num_weeks), dtype=int)
    all_dates = []
    for col, week in enumerate(weeks_data):
        for day in week['contributionDays']:
            date_obj = datetime.strptime(day['date'], '%Y-%m-%d')
            row = date_obj.weekday()  # 0=Monday, 6=Sunday
            grid[row, col] = day['contributionCount']
            all_dates.append(date_obj)

    fig, ax = plt.subplots(figsize=(12, 4))  # 高度稍增加，给图例留空间

    # GitHub 颜色梯度（从浅到深）
    color_map = ['#ebedf0', '#9be9a8', '#40c463', '#30a14e', '#216e39']
    def get_color(count):
        if count <= 0: return color_map[0]
        elif count <= 4: return color_map[1]
        elif count <= 9: return color_map[2]
        elif count <= 19: return color_map[3]
        else: return color_map[4]

    # 绘制格子（无数字）
    for r in range(7):
        for c in range(num_weeks):
            count = grid[r, c]
            color = get_color(count)
            rect = mpatches.Rectangle((c, 6 - r), 1, 1,
                                      linewidth=1, edgecolor='#d0d7de',
                                      facecolor=color)
            ax.add_patch(rect)

    # 月份标签
    month_positions = {}
    for date in all_dates:
        month_key = date.strftime('%Y-%m')
        if month_key not in month_positions:
            for col, week in enumerate(weeks_data):
                for day in week['contributionDays']:
                    if day['date'] == date.strftime('%Y-%m-%d'):
                        month_positions[month_key] = (col, date.strftime('%b'))
                        break
                if month_key in month_positions:
                    break
    for col, month_label in month_positions.values():
        ax.text(col + 0.5, -0.5, month_label, ha='center', fontsize=8)

    # 星期标签（左侧）：周一 = 1, ..., 周日 = 7
    week_labels = ['1', '2', '3', '4', '5', '6', '7']  # 周一~周日
    for r, label in enumerate(week_labels):
        ax.text(-0.5, 6 - r + 0.5, label, va='center', ha='right', fontsize=7)

    ax.set_xlim(0, num_weeks)
    ax.set_ylim(0, 7)
    ax.set_aspect('equal')
    ax.axis('off')

    # 标题（包含年份）
    if all_dates:
        latest_year = max(d.year for d in all_dates)
    else:
        latest_year = datetime.utcnow().year
    plt.title(f'Contribution Calendar ({latest_year})', fontsize=12, pad=10)

    # ---- 添加右下角图例 ----
    legend_labels = ['0', '1-4', '5-9', '10-19', '20+']
    legend_colors = color_map
    # 在图右侧下方位置添加小方块
    for i, (color, label) in enumerate(zip(legend_colors, legend_labels)):
        rect = mpatches.Rectangle((num_weeks - 2 + i * 1.2, -1.8), 0.8, 0.8,
                                  linewidth=1, edgecolor='#d0d7de',
                                  facecolor=color)
        ax.add_patch(rect)
        ax.text(num_weeks - 2 + i * 1.2 + 0.4, -2.4, label,
                ha='center', va='top', fontsize=7)
    # “Less” 和 “More” 文字
    ax.text(num_weeks - 2, -1.2, 'Less', ha='center', fontsize=7, color='#586069')
    ax.text(num_weeks - 2 + (len(legend_labels)-1)*1.2, -1.2, 'More', ha='center', fontsize=7, color='#586069')

    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close()

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
        lines.append(f"{i}. **{repo}** - {count} 次提交")
    return '\n'.join(lines)

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

# ---------------- 生成 README.md ----------------
def generate_readme(monthly, yearly, streak, top_repos_md):
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    readme = f"""# Hi there 👋

## 📊 GitHub 活动报告
> 自动更新于 {now}

### 🔥 贡献日历
![贡献日历](calendar.png)

### 🏆 最近活跃仓库 Top 5
{top_repos_md}

### 📈 近 7 天贡献趋势
![近7天趋势](weekly_line.png)

### 🔥 连续贡献
当前连续 **{streak}** 天

### 📅 月报（近 30 天）
代码提交：**{monthly[0]}** 次　|　发起 PR：**{monthly[1]}** 个　|　新建 Issue：**{monthly[2]}** 个　|　代码审查：**{monthly[3]}** 次

### 📅 年报（近 365 天）
代码提交：**{yearly[0]}** 次　|　发起 PR：**{yearly[1]}** 个　|　新建 Issue：**{yearly[2]}** 个　|　代码审查：**{yearly[3]}** 次

---

### ✨ GitHub 统计
![GitHub stats](https://github-readme-stats.vercel.app/api?username={USERNAME}&show_icons=true&theme=radical)
![Top Langs](https://github-readme-stats.vercel.app/api/top-langs/?username={USERNAME}&layout=compact&theme=radical)
![GitHub streak](https://github-readme-streak-stats.herokuapp.com/?user={USERNAME}&theme=radical)

---
*✨ 此报告由 GitHub Actions 每天自动生成*
"""
    return readme

# ---------------- 主流程 ----------------
def main():
    print('🚀 开始生成报告...')

    calendar = get_contribution_calendar()
    draw_calendar_heatmap(calendar['weeks'], 'calendar.png')
    print('✅ 日历热力图已生成')

    draw_weekly_line_chart(calendar['weeks'], 'weekly_line.png')
    print('✅ 近7天趋势图已生成')

    streak = calculate_streak(calendar['weeks'])
    print(f'🔥 当前连续贡献 {streak} 天')

    m = get_recent_stats(30)
    y = get_recent_stats(365)

    top5 = top_repos(days=90)
    top_repos_md = format_top_repos(top5)
    print('✅ 活跃仓库 Top 5 已统计')

    readme = generate_readme(m, y, streak, top_repos_md)
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(readme)
    print('✅ README.md 已更新')

    with open('stats.txt', 'w') as f:
        f.write(f'Monthly: {m}\nYearly: {y}\nStreak: {streak}\n')

if __name__ == '__main__':
    main()

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
    USERNAME = '你的GitHub用户名'

TOKEN = os.environ.get('GH_TOKEN')
if not TOKEN:
    raise RuntimeError('环境变量 GH_TOKEN 未设置')

HEADERS = {'Authorization': f'bearer {TOKEN}'}

# ---------------- 官方 API：最近 365 天贡献日历 ----------------
def get_recent_365_calendar():
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

# ---------------- 第三方 API：获取完整年份的贡献日历 ----------------
def get_contribution_calendar_for_year(year):
    url = f'https://github-contributions-api.deno.dev/{USERNAME}.json?year={year}'
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        if 'weeks' in data:
            return data['weeks']
        elif isinstance(data, list):
            return data
        else:
            return None
    except Exception as e:
        print(f'⚠️ 无法获取 {year} 年数据: {e}')
        return None

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

# ---------------- 绘制日历热力图（圆角、图例右对齐、Less/More 加大） ----------------
def draw_calendar_heatmap(weeks_data, year_label, filename):
    num_weeks = len(weeks_data)
    grid = np.zeros((7, num_weeks), dtype=int)
    all_dates = []
    for col, week in enumerate(weeks_data):
        for day in week['contributionDays']:
            date_obj = datetime.strptime(day['date'], '%Y-%m-%d')
            row = date_obj.weekday()  # 0=Monday, 6=Sunday
            grid[row, col] = day['contributionCount']
            all_dates.append(date_obj)

    title_text = f'Contributions {year_label}'

    fig, ax = plt.subplots(figsize=(12, 4.5))

    color_map = ['#ebedf0', '#9be9a8', '#40c463', '#30a14e', '#216e39']
    def get_color(count):
        if count <= 0: return color_map[0]
        elif count <= 4: return color_map[1]
        elif count <= 9: return color_map[2]
        elif count <= 19: return color_map[3]
        else: return color_map[4]

    # 圆角方格（环境不支持时退化为普通矩形，不影响运行）
    for r in range(7):
        for c in range(num_weeks):
            count = grid[r, c]
            color = get_color(count)
            rect = mpatches.FancyBboxPatch(
                (c, 6 - r), 1, 1,
                boxstyle="round,pad=0.12",
                linewidth=1, edgecolor='#d0d7de',
                facecolor=color
            )
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
        ax.text(col + 0.5, -0.8, month_label, ha='center', fontsize=8)

    # 星期标签（1~7）
    week_labels = ['1', '2', '3', '4', '5', '6', '7']
    for r, label in enumerate(week_labels):
        ax.text(-0.5, 6 - r + 0.5, label, va='center', ha='right', fontsize=7)

    ax.set_xlim(0, num_weeks)
    ax.set_ylim(-3, 7)
    ax.set_aspect('equal')
    ax.axis('off')

    # 标题
    plt.title(title_text, fontsize=16, fontweight='bold', pad=15)

    # ========== 图例（右对齐，紧凑间距，字体加大） ==========
    legend_labels = ['0', '1-4', '5-9', '10-19', '20+']
    legend_colors = color_map
    block_size = 0.8
    spacing = 1.2               # 紧凑间距
    legend_width = len(legend_labels) * block_size + (len(legend_labels) - 1) * spacing
    start_x = num_weeks - legend_width   # 右对齐网格右边界

    y_blocks = -2.2
    y_labels = -3.1
    y_lessmore = -1.8

    for i, (color, label) in enumerate(zip(legend_colors, legend_labels)):
        x = start_x + i * (block_size + spacing)
        rect = mpatches.FancyBboxPatch(
            (x, y_blocks), block_size, block_size,
            boxstyle="round,pad=0.1",
            linewidth=1, edgecolor='#d0d7de',
            facecolor=color
        )
        ax.add_patch(rect)
        ax.text(x + block_size/2, y_labels, label,
                ha='center', va='top', fontsize=9)

    # Less / More 字体 9
    ax.text(start_x, y_lessmore, 'Less', ha='left', fontsize=9, color='#586069')
    ax.text(start_x + legend_width, y_lessmore, 'More', ha='right', fontsize=9, color='#586069')

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

# ---------------- 生成 README.md（包含贡献日历） ----------------
def generate_readme(monthly, yearly, streak, top_repos_md, years_with_calendar):
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    calendar_imgs = ""
    for yr_label in years_with_calendar:
        file_suffix = yr_label.replace(' ', '_')
        calendar_imgs += f"### 📅 {yr_label}\n![{yr_label}贡献日历](calendar_{file_suffix}.png)\n\n"

    readme = f"""# Hi there 👋

## 📊 GitHub 活动报告
> 自动更新于 {now}

### 🔥 贡献日历
{calendar_imgs}
### 🏆 最近活跃仓库 Top 5
{top_repos_md}

### 📈 近 7 天贡献趋势
![近7天趋势](weekly_line.png)

### 🔥 连续贡献
当前连续 **{streak}** 天

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

    current_year = datetime.utcnow().year
    years_with_calendar = []

    # 今年日历
    weeks_this_year = get_contribution_calendar_for_year(current_year)
    if weeks_this_year:
        draw_calendar_heatmap(weeks_this_year, str(current_year), f'calendar_{current_year}.png')
        years_with_calendar.append(str(current_year))
        print(f'✅ {current_year} 年完整日历已生成')
        calendar_recent = weeks_this_year
    else:
        calendar_recent_data = get_recent_365_calendar()
        weeks_recent = calendar_recent_data['weeks']
        draw_calendar_heatmap(weeks_recent, str(current_year), f'calendar_{current_year}.png')
        years_with_calendar.append(str(current_year))
        print('⚠️ 今年完整数据获取失败，已使用最近365天数据')
        calendar_recent = weeks_recent

    # 过去两年
    for yr in [current_year-1, current_year-2]:
        weeks_past = get_contribution_calendar_for_year(yr)
        if weeks_past:
            draw_calendar_heatmap(weeks_past, str(yr), f'calendar_{yr}.png')
            years_with_calendar.append(str(yr))
            print(f'✅ {yr} 年日历已生成')
        else:
            print(f'⚠️ 跳过 {yr} 年（无数据）')

    draw_weekly_line_chart(calendar_recent, 'weekly_line.png')
    print('✅ 近7天趋势图已生成')

    streak = calculate_streak(calendar_recent)
    print(f'🔥 当前连续贡献 {streak} 天')

    m = get_recent_stats(30)
    y = get_recent_stats(365)

    top5 = top_repos(days=90)
    top_repos_md = format_top_repos(top5)

    readme = generate_readme(m, y, streak, top_repos_md, years_with_calendar)
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(readme)
    print('✅ README.md 已更新')

    with open('stats.txt', 'w') as f:
        f.write(f'Monthly: {m}\nYearly: {y}\nStreak: {streak}\n')

if __name__ == '__main__':
    main()

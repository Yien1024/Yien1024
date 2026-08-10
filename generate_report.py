import requests
import os
from datetime import datetime, timedelta, timezone
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

# ======================== API 数据获取 ========================

def get_recent_365_calendar():
    """官方 GraphQL API：最近 365 天贡献日历"""
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

def get_contribution_calendar_for_year(year):
    """第三方 API：获取指定年份的贡献日历"""
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

def get_recent_stats(days):
    """REST API：获取指定天数内的统计（含代码审查）"""
    url = f'https://api.github.com/users/{USERNAME}/events/public?per_page=100'
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

def top_repos(days=90):
    """获取最活跃仓库 Top 5"""
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
    """格式化仓库列表为 Markdown"""
    if not top5:
        return "> 🌱 近期暂无提交数据，继续加油！"
    lines = []
    for i, (repo, count) in enumerate(top5, 1):
        lines.append(f"{i}. **[{repo}](https://github.com/{repo})** — {count} 次提交")
    return '\n'.join(lines)

def calculate_streak(weeks_data):
    """计算当前连续贡献天数"""
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

def calculate_longest_streak(weeks_data):
    """计算最长连续贡献天数"""
    daily = {}
    for week in weeks_data:
        for day in week['contributionDays']:
            daily[datetime.strptime(day['date'], '%Y-%m-%d').date()] = day['contributionCount']
    if not daily:
        return 0
    sorted_dates = sorted(daily.keys())
    longest = current = 0
    for date in sorted_dates:
        if daily[date] > 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest

# ======================== 图表绘制 ========================

def draw_calendar_heatmap(weeks_data, year_label, filename):
    """绘制日历热力图（圆角、渐变、精美排版）"""
    num_weeks = len(weeks_data)
    grid = np.zeros((7, num_weeks), dtype=int)
    all_dates = []
    for col, week in enumerate(weeks_data):
        for day in week['contributionDays']:
            date_obj = datetime.strptime(day['date'], '%Y-%m-%d')
            row = date_obj.weekday()
            grid[row, col] = day['contributionCount']
            all_dates.append(date_obj)

    # 使用 GitHub 暗色主题配色
    color_map = ['#161b22', '#0e4429', '#006d32', '#26a641', '#39d353']
    
    fig, ax = plt.subplots(figsize=(14, 5))
    fig.patch.set_facecolor('#0d1117')
    ax.set_facecolor('#0d1117')

    def get_color(count):
        if count <= 0: return color_map[0]
        elif count <= 4: return color_map[1]
        elif count <= 9: return color_map[2]
        elif count <= 19: return color_map[3]
        else: return color_map[4]

    # 绘制圆角方格
    for r in range(7):
        for c in range(num_weeks):
            count = grid[r, c]
            color = get_color(count)
            rect = mpatches.FancyBboxPatch(
                (c, 6 - r), 1, 1,
                boxstyle="round,pad=0.15",
                linewidth=0.5, edgecolor='#30363d',
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
        ax.text(col + 0.5, -0.8, month_label, ha='center', fontsize=9, color='#8b949e')

    # 星期标签
    week_labels = ['Mon', '', 'Wed', '', 'Fri', '', 'Sun']
    for r, label in enumerate(week_labels):
        ax.text(-0.5, 6 - r + 0.5, label, va='center', ha='right', fontsize=7, color='#8b949e')

    ax.set_xlim(0, num_weeks)
    ax.set_ylim(-4, 7.5)
    ax.set_aspect('equal')
    ax.axis('off')

    # 标题
    plt.title(f'📅 {year_label}', fontsize=18, fontweight='bold', 
              color='#c9d1d9', pad=18)

    # 图例
    legend_labels = ['0', '1-4', '5-9', '10-19', '20+']
    legend_colors = color_map
    block_size = 0.8
    spacing = 1.2
    legend_width = len(legend_labels) * block_size + (len(legend_labels) - 1) * spacing
    start_x = num_weeks - legend_width
    y_blocks = -2.2
    y_labels = -3.1
    y_lessmore = -3.5

    for i, (color, label) in enumerate(zip(legend_colors, legend_labels)):
        x = start_x + i * (block_size + spacing)
        rect = mpatches.FancyBboxPatch(
            (x, y_blocks), block_size, block_size,
            boxstyle="round,pad=0.1",
            linewidth=0.5, edgecolor='#30363d',
            facecolor=color
        )
        ax.add_patch(rect)
        ax.text(x + block_size/2, y_labels, label,
                ha='center', va='top', fontsize=9, color='#8b949e')

    ax.text(start_x, y_lessmore, 'Less', ha='left', fontsize=9, color='#8b949e')
    ax.text(num_weeks, y_lessmore, 'More', ha='right', fontsize=9, color='#8b949e')

    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches='tight', facecolor='#0d1117')
    plt.close()

def draw_weekly_line_chart(weeks_data, filename):
    """绘制近 7 天贡献折线图（暗色主题）"""
    today = datetime.utcnow().date()
    dates = []
    counts = []
    for week in weeks_data:
        for day in week['contributionDays']:
            d = datetime.strptime(day['date'], '%Y-%m-%d').date()
            if 0 <= (today - d).days < 7:
                dates.append(d.strftime('%m-%d'))
                counts.append(day['contributionCount'])

    fig, ax = plt.subplots(figsize=(8, 3.5))
    fig.patch.set_facecolor('#0d1117')
    ax.set_facecolor('#0d1117')

    if not dates:
        ax.text(0.5, 0.5, 'No recent data', ha='center', va='center',
                color='#8b949e', fontsize=14, transform=ax.transAxes)
        ax.set_title('📈 Daily Contributions (Last 7 days)', color='#c9d1d9', fontsize=14)
        ax.axis('off')
        plt.tight_layout()
        plt.savefig(filename, dpi=120, bbox_inches='tight', facecolor='#0d1117')
        plt.close()
        return

    sorted_pairs = sorted(zip(dates, counts))
    dates, counts = zip(*sorted_pairs)

    ax.plot(dates, counts, marker='o', color='#58a6ff', linewidth=2.5, markersize=8, 
            markerfacecolor='#58a6ff', markeredgecolor='#0d1117', markeredgewidth=2)
    ax.fill_between(range(len(dates)), counts, alpha=0.15, color='#58a6ff')

    # 设置样式
    ax.set_title('📈 Daily Contributions (Last 7 days)', color='#c9d1d9', fontsize=14, fontweight='bold')
    ax.set_ylabel('Contributions', color='#8b949e', fontsize=10)
    ax.tick_params(colors='#8b949e', labelsize=9)
    ax.spines['bottom'].set_color('#30363d')
    ax.spines['left'].set_color('#30363d')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_ylim(bottom=0)

    # 在数据点上显示数值
    for i, (d, c) in enumerate(zip(dates, counts)):
        ax.annotate(str(c), (i, c), textcoords="offset points", xytext=(0, 8),
                    ha='center', fontsize=9, color='#58a6ff')

    ax.grid(axis='y', alpha=0.1, color='#8b949e')
    plt.tight_layout()
    plt.savefig(filename, dpi=120, bbox_inches='tight', facecolor='#0d1117')
    plt.close()

# ======================== 时间工具 ========================

def get_timezone_times():
    """获取各时区当前时间"""
    utc_now = datetime.now(timezone.utc)
    timezones = {
        'utc': utc_now,
        'cst': utc_now + timedelta(hours=8),
        'jst': utc_now + timedelta(hours=9),
        'est': utc_now + timedelta(hours=-5),
        'bst': utc_now + timedelta(hours=1),
    }
    result = {}
    for key, dt in timezones.items():
        result[key] = dt.strftime('%H:%M')
    return result

# ======================== README 生成 ========================

def generate_readme(stats, streak, longest_streak, top_repos_md, years_with_calendar, time_times):
    """生成带时间调节的完整 README"""
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')

    # 日历图片
    calendar_imgs = ""
    for yr_label in years_with_calendar:
        file_suffix = yr_label.replace(' ', '_')
        calendar_imgs += f"![{yr_label}贡献日历](calendar_{file_suffix}.png)\n\n"

    # 多个时间段的统计
    stats_map = {}
    for period_label, (commits, prs, issues, reviews) in stats.items():
        stats_map[f'{period_label}_commits'] = commits
        stats_map[f'{period_label}_prs'] = prs
        stats_map[f'{period_label}_issues'] = issues
        stats_map[f'{period_label}_reviews'] = reviews

    readme = f"""<div align="center">
  
# ✨ Yien1024 ✨

<!-- 打字效果动画 -->
<a href="https://git.io/typing-svg">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=28&duration=3000&pause=500&color=58A6FF&center=true&vCenter=true&width=435&lines=Hi+there!+%F0%9F%91%8B;Welcome+to+my+profile;Code+%7C+Create+%7C+Explore" alt="Typing SVG" />
</a>

<!-- 社交徽章 -->
<p>
  <a href="https://github.com/Yien1024">
    <img src="https://img.shields.io/badge/GitHub-Yien1024-181717?style=flat-square&logo=github" alt="GitHub" />
  </a>
  <a href="https://github.com/Yien1024/Yien1024">
    <img src="https://img.shields.io/github/followers/Yien1024?style=flat-square&logo=github&label=Followers" alt="Followers" />
  </a>
  <a href="https://github.com/Yien1024/Yien1024">
    <img src="https://img.shields.io/github/stars/Yien1024?style=flat-square&logo=github&label=Stars" alt="Stars" />
  </a>
  <img src="https://komarev.com/ghpvc/?username=Yien1024&style=flat-square&color=blue" alt="Profile Views" />
  <img src="https://img.shields.io/badge/Last%20Updated-{now.replace(' ', '%20').replace(':', '%3A')}-brightgreen?style=flat-square" alt="Last Updated" />
</p>

<img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/colored.png" width="100%" />

</div>

## 👨‍💻 About Me

```yaml
name: Yien
location: 🌏
languages: [Python, JavaScript, HTML, CSS]
interests: [Coding, Open Source, AI]
```

---

## 🛠️ Tech Stack

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black" />
  <img src="https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white" />
  <img src="https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white" />
  <img src="https://img.shields.io/badge/Git-F05032?style=for-the-badge&logo=git&logoColor=white" />
  <img src="https://img.shields.io/badge/VS_Code-007ACC?style=for-the-badge&logo=visual-studio-code&logoColor=white" />
  <img src="https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black" />
  <img src="https://img.shields.io/badge/Markdown-000000?style=for-the-badge&logo=markdown&logoColor=white" />
</p>

---

## 📊 GitHub Activity Report

> ⏱️ 自动更新于 `{now}`

<div align="center">

### 🔥 Contribution Calendar

{calendar_imgs}

### 📈 Multi-Time Range Activity Overview

| Period | Commits | PRs | Issues | Reviews |
|--------|:-------:|:---:|:------:|:-------:|
| 📅 **Last 7 days** | **{stats_map['weekly_commits']}** | **{stats_map['weekly_prs']}** | **{stats_map['weekly_issues']}** | **{stats_map['weekly_reviews']}** |
| 📅 **Last 14 days** | **{stats_map['biweekly_commits']}** | **{stats_map['biweekly_prs']}** | **{stats_map['biweekly_issues']}** | **{stats_map['biweekly_reviews']}** |
| 📅 **Last 30 days** | **{stats_map['monthly_commits']}** | **{stats_map['monthly_prs']}** | **{stats_map['monthly_issues']}** | **{stats_map['monthly_reviews']}** |
| 📅 **Last 90 days** | **{stats_map['quarterly_commits']}** | **{stats_map['quarterly_prs']}** | **{stats_map['quarterly_issues']}** | **{stats_map['quarterly_reviews']}** |
| 📅 **Last 365 days** | **{stats_map['yearly_commits']}** | **{stats_map['yearly_prs']}** | **{stats_map['yearly_issues']}** | **{stats_map['yearly_reviews']}** |

</div>

### 🏆 Top Active Repositories (Last 90 Days)

{top_repos_md}

### 📈 7-Day Trend

![7-Day Trend](weekly_line.png)

### 🔥 Contribution Streak

<div align="center">

| Current Streak | Longest Streak |
|:--------------:|:--------------:|
| **{streak}** days 🔥 | **{longest_streak}** days 🏆 |

</div>

---

## 🏆 GitHub Trophies

<div align="center">

![Trophies](https://github-profile-trophy.vercel.app/?username=Yien1024&theme=flat&no-frame=true&no-bg=true&margin-w=15&row=2&column=4)

</div>

---

## ⏰ Live Time Zone Clock

<div align="center">

| 🌍 UTC | 🇨🇳 Beijing (CST) | 🇯🇵 Tokyo (JST) | 🇺🇸 New York (EST) | 🇬🇧 London (BST) |
|:------:|:-----------------:|:---------------:|:------------------:|:----------------:|
| {time_times['utc']} | {time_times['cst']} | {time_times['jst']} | {time_times['est']} | {time_times['bst']} |

</div>

---

## 📊 GitHub Stats

<div align="center">

| Stats | Languages | Streak |
|:-----:|:---------:|:------:|
| ![GitHub Stats](https://github-readme-stats.vercel.app/api?username=Yien1024&show_icons=true&theme=github&hide_border=true&count_private=true&include_all_commits=true) | ![Top Langs](https://github-readme-stats.vercel.app/api/top-langs/?username=Yien1024&layout=compact&theme=github&hide_border=true) | ![GitHub Streak](https://github-readme-streak-stats.herokuapp.com/?user=Yien1024&theme=github&hide_border=true) |

</div>

---

## 🐍 Contribution Snake

<div align="center">

![snake](https://github.com/Yien1024/Yien1024/blob/output/github-contribution-grid-snake.svg)

</div>

---

<div align="center">

### 💡 "Code is like humor. When you have to explain it, it's bad." — Cory House

*✨ This profile README is auto-generated by GitHub Actions ✨*

</div>"""
    return readme

# ======================== 主流程 ========================

def main():
    print('🚀 开始生成报告...')

    # ---- 步骤 1: 获取贡献日历 ----
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
    for yr in [current_year - 1, current_year - 2]:
        weeks_past = get_contribution_calendar_for_year(yr)
        if weeks_past:
            draw_calendar_heatmap(weeks_past, str(yr), f'calendar_{yr}.png')
            years_with_calendar.append(str(yr))
            print(f'✅ {yr} 年日历已生成')
        else:
            print(f'⚠️ 跳过 {yr} 年（无数据）')

    # ---- 步骤 2: 近 7 天折线图 ----
    draw_weekly_line_chart(calendar_recent, 'weekly_line.png')
    print('✅ 近7天趋势图已生成')

    # ---- 步骤 3: 连续贡献 ----
    streak = calculate_streak(calendar_recent)
    longest_streak = calculate_longest_streak(calendar_recent)
    print(f'🔥 当前连续贡献 {streak} 天，最长连续 {longest_streak} 天')

    # ---- 步骤 4: 多时间范围统计（时间调节核心） ----
    stats = {}
    time_ranges = [
        ('weekly', 7),
        ('biweekly', 14),
        ('monthly', 30),
        ('quarterly', 90),
        ('yearly', 365),
    ]
    for label, days in time_ranges:
        stats[label] = get_recent_stats(days)
        print(f'📊 {label} ({days}d): {stats[label]}')

    # ---- 步骤 5: 活跃仓库 ----
    top5 = top_repos(days=90)
    top_repos_md = format_top_repos(top5)
    print(f'🏆 Top 仓库: {len(top5)} 个')

    # ---- 步骤 6: 时区时间 ----
    time_times = get_timezone_times()
    print(f'⏰ 时区时间: {time_times}')

    # ---- 步骤 7: 生成 README ----
    readme = generate_readme(stats, streak, longest_streak, top_repos_md, years_with_calendar, time_times)
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(readme)
    print('✅ README.md 已更新')

    # ---- 步骤 8: 保存统计数据供徽章使用 ----
    stats_text = {
        'updated_at': datetime.utcnow().isoformat(),
        'streak': streak,
        'longest_streak': longest_streak,
        'weekly': list(stats['weekly']),
        'monthly': list(stats['monthly']),
        'yearly': list(stats['yearly']),
        'timezones': time_times,
    }
    with open('stats.txt', 'w', encoding='utf-8') as f:
        import json
        f.write(json.dumps(stats_text, ensure_ascii=False, indent=2))
    print('✅ stats.txt 已更新')

    print('🎉 报告生成完成！')

if __name__ == '__main__':
    main()

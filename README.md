# 📊 GitHub 活动报告生成器

将你的 GitHub 个人主页变成一个自动更新的数据看板，包含：

- 🔥 **贡献日历**（过去三年的热力图，圆角方格，自动对齐）
- 📈 **近 7 天贡献趋势**（折线图）
- 🏆 **最近活跃仓库 Top 5**
- 🔥 **连续贡献天数**
- 📅 **月报 / 年报**（表格形式，含提交、PR、Issue、代码审查）
- ✨ **GitHub 统计徽章**（总览、常用语言、连续打卡）

> 所有图表每天自动刷新，无需手动操作。

---

## 🚀 快速部署（仅需 3 步）

### 1️⃣ 使用本模板创建你的个人主页仓库
- 点击右上角 **Use this template** → **Create a new repository**
- **仓库名必须和你的 GitHub 用户名完全一致**（例如你的用户名是 `octocat`，仓库名就是 `octocat`）
- 勾选 **Public**，点击 **Create repository**

### 2️⃣ 创建个人访问令牌并设置为 Secret
- 前往 [GitHub Tokens 设置](https://github.com/settings/tokens) 生成一个 **classic token**
  - 权限至少勾选 `repo` 和 `user`
- 复制生成的 token（只显示一次！）
- 在新仓库中，进入 **Settings** → **Secrets and variables** → **Actions**
- 点击 **New repository secret**
  - Name 填写：`GH_TOKEN`
  - Value 粘贴你刚才复制的 token
- 点击 **Add secret**

### 3️⃣ 启动自动生成
- 进入仓库的 **Actions** 标签页
- 左侧点击 **Update GitHub Report** 工作流
- 右侧点击 **Run workflow** → **Run workflow**（手动触发一次）
- 等待约 1～2 分钟，工作流运行成功后，刷新你的 GitHub 个人主页即可看到完整的活动报告！

✅ 之后报告会在每天 **UTC 2:00** 自动更新，完全不用管。

---

## 🛠 如果你想自己修改
- 所有逻辑在 `generate_report.py` 中，你可以自由调整图表样式、统计维度、布局。
- 工作流文件在 `.github/workflows/update-readme.yml`，可以修改定时运行时间。
- 如果只想保留部分模块（例如去掉日历、只保留表格），直接编辑 `generate_readme` 函数即可。

---

## ❓ 常见问题

**Q: 为什么 Actions 运行失败？**  
A: 请检查：
1. `GH_TOKEN` 是否已正确设置，且权限包含 `repo` 和 `user`。
2. 仓库名是否与你的 GitHub 用户名完全一致。
3. 如果报错 `Permission denied`，请确认 Settings → Actions → General → Workflow permissions 已勾选 **Read and write permissions**。

**Q: 贡献日历为什么没有圆角？**  
A: GitHub Actions 的 `ubuntu-latest` 环境可能使用旧版 matplotlib，不影响使用，只是无圆角。升级 matplotlib 到 3.5+ 即可支持圆角，但不影响功能。

**Q: 过去两年的日历为什么有时候不显示？**  
A: 过去年份的数据依赖第三方 API，如果它临时不可用会自动跳过，至少今年的日历一定会生成。

**Q: 能添加其他统计吗（如总星数、Fork 数）？**  
A: 完全可以，只需修改 `generate_report.py` 中的 API 调用和 README 生成部分即可。

---

## 📁 项目文件说明
- `generate_report.py`：核心脚本，拉取数据、画图、生成 README
- `requirements.txt`：Python 依赖
- `.github/workflows/update-readme.yml`：GitHub Actions 工作流，定时执行脚本

---

**如果觉得有用，欢迎 Star ⭐️ 支持！**

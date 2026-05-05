# UN Internship Monitor

一个用于监控 UN 相关机构实习岗位的 Python 工具。脚本会抓取多个招聘网站的 internship 岗位，保存到 SQLite，同步到 Notion，并通过 ServerChan 推送每日摘要。

## 功能

- 抓取多个 UN 相关招聘来源的 internship 岗位：
  - UN Careers
  - UNHCR
  - UNDP
  - UNIDO
  - WFP
  - UNICEF
- 提取岗位名、Job ID、部门、地点、发布日期、截止日期和申请链接。
- 生成两类提醒：
  - A. 今日发布岗位
  - B. 明天截止岗位
- 保存岗位数据到 SQLite。
- 可选同步每日更新到 Notion 表格。
- 通过 ServerChan 推送到微信。
- 支持 Windows 计划任务每日自动运行。

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
Copy-Item .env.example .env
```

## 配置

编辑 `.env`：

```dotenv
PUSH_CHANNEL=serverchan
SERVERCHAN_SENDKEY=你的ServerChanSendKey
```

不要把 `.env` 上传到 GitHub。它包含你的微信推送密钥和 Notion token。

## Notion 同步

如果想把每日更新自动写入 Notion，先在 Notion 里建一个 database。脚本会自动补齐需要的字段：

| 列名 | 类型 |
| --- | --- |
| Job ID | Text |
| Alert Type | Select |
| Department | Text |
| Location | Text |
| Posted Date | Date |
| Deadline Date | Date |
| URL | URL |
| Sync Date | Date |

然后在 `.env` 填：

```dotenv
NOTION_TOKEN=你的NotionIntegrationToken
NOTION_DATABASE_ID=你的NotionDatabaseID
```

不填写 Notion 配置时，脚本只会微信推送，不会同步 Notion。

## 运行

只抓取并打印摘要，不推送：

```powershell
python -m un_intern_monitor.main --no-push
```

抓取并推送到微信：

```powershell
python -m un_intern_monitor.main
```

## 网站 Dashboard

启动本地作品集网站：

```powershell
python -m un_intern_monitor.web
```

然后打开：

```text
http://127.0.0.1:8000
```

网站会读取本地 SQLite，展示统计卡片、来源筛选、关键词搜索、今日发布岗位和明天截止岗位。

## GitHub Pages 静态网站

生成可上传到 GitHub Pages 的静态页面：

```powershell
python -m un_intern_monitor.static_site
```

生成结果在：

```text
docs/index.html
docs/dashboard.css
```

在 GitHub 仓库里进入 `Settings` -> `Pages`，选择：

```text
Source: Deploy from a branch
Branch: main
Folder: /docs
```

保存后，GitHub 会生成一个公开访问链接。

## 自动推送

Windows 可以使用计划任务每天运行：

```powershell
$project = "D:\儿童医保\Pythonproject"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File `"$project\scripts\run_monitor.ps1`""
$trigger = New-ScheduledTaskTrigger -Daily -At 09:00
Register-ScheduledTask -TaskName "UNInternshipMonitor" -Action $action -Trigger $trigger -Description "Daily UN internship monitor"
```

## 数据

岗位数据保存在：

```text
data/un_internships.sqlite
```

数据库文件是本地运行数据，不建议上传到 GitHub。

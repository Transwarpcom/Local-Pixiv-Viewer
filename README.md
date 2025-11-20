# Local Pixiv Viewer

一个功能强大的本地 Pixiv 镜像站/浏览器。基于 Python Flask + SQLite + Nginx 构建，支持响应式布局、PWA、多语言及完整的社区互动功能（点赞、收藏、评论）。

专为管理和浏览海量本地 Pixiv 收藏而设计。

## ✨ 功能特性 (Features)

* **📱 全平台响应式设计**：完美适配桌面、平板和移动端，支持 PWA 安装。
* **📚 全类型支持**：完美展示插画 (Illustrations)、漫画 (Manga) 和 **小说 (Novels)**。
* **🔍 强大的元数据索引**：自动解析文件名中的标签、系列、作者信息，支持标签搜索。
* **🔄 自动后台索引**：文件放入硬盘即可自动扫描入库，无需手动干预。
* **👥 用户系统**：
    * 注册/登录 (首个注册用户自动成为管理员)。
    * 个人中心、浏览历史、关注作者、关注动态 (Feed)。
    * 点赞、收藏、评论功能。
* **🛡️ 内容管理**：
    * 后台管理面板 (Dashboard) 查看系统状态和管理用户/评论。
    * **R-18 模糊开关**：一键切换敏感内容模糊显示。
* **🌙 个性化**：支持深色模式 (Dark Mode) 和 国际化 (i18n, 中/英切换)。

---

## 🚀 前置步骤：数据获取 (Data Preparation)

本项目不提供爬虫功能，依赖于本地已有的数据文件。请使用 Chrome/Edge 扩展程序 **Powerful Pixiv Downloader (PPD)** 进行下载。

### 1. 安装插件
在浏览器扩展商店搜索并安装 **Powerful Pixiv Downloader**。

### 2. 配置命名规则 (关键)
为了让索引器正确识别作者、ID、标签和系列信息，**必须**严格按照以下规则设置下载路径。

1.  打开 Pixiv 页面，点击 PPD 图标进入 **控制面板 (Dashboard)**。
2.  进入 **下载 (Downloads)** 设置页。
3.  找到 **文件名设置 (Filename settings)** 或 **重命名规则**。
4.  将路径规则设置为：

    ```text
    pixiv/{user}-{user_id}/{id}-{title}_{tags}-{series_title}_{series_order}-{series_id}
    ```

### 3. 传输文件
将下载好的 `pixiv` 文件夹复制到服务器的数据盘挂载点（例如 `/mnt/data`）。
目录结构应如下所示：

```text
/mnt/data/pixiv/
├── 某画师A-123456/
│   ├── 88888888_p0-作品标题_标签1,标签2...jpg
│   └── ...
└── 某作者B-654321/
    ├── 99999999-小说标题_标签...-系列名_#1-系列ID.txt
    └──...
```

🛠️ 部署指南 (Deployment)
环境要求
 * Ubuntu / Debian
 * Python 3.8+
 * Nginx
 * SQLite3
1. 安装依赖
```text
sudo apt update
sudo apt install -y python3-pip python3-venv nginx ffmpeg sqlite3
```

2. 项目初始化
假设你的部署目录为 /path/to/project：
```text
mkdir -p /path/to/project
cd /path/to/project
```

# 创建虚拟环境
```text
python3 -m venv venv
source venv/bin/activate
```

# 安装 Python 依赖
```text
pip install flask flask-login flask-babel werkzeug watchdog
```

3. 配置 Systemd 服务
本项目包含两个核心服务：Web 服务和自动索引服务。
Web 服务 (pixiv_web.service):
请将 User, Group 和 WorkingDirectory 替换为你实际的用户和路径。
```text
[Unit]
Description=Pixiv Clone Web App
After=network.target

[Service]
User=your_user
Group=your_user
WorkingDirectory=/path/to/project
Environment="PATH=/path/to/project/venv/bin"
ExecStart=/path/to/project/venv/bin/python app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

自动索引服务 (pixiv_indexer.service):
```text
[Unit]
Description=Pixiv Auto Indexer
After=network.target

[Service]
User=your_user
Group=your_user
WorkingDirectory=/path/to/project
Environment="PATH=/path/to/project/venv/bin"
ExecStart=/path/to/project/venv/bin/python -u auto_indexer.py
Restart=always

[Install]
WantedBy=multi-user.target
```

4. 配置 Nginx
```text
server {
    listen 80;
    server_name your-domain.com; # 替换为你的域名
    charset utf-8;
    root /path/to/project;

    # 核心：直接通过 Nginx 高效分发图片文件
    location ^~ /files/ {
        alias /mnt/data/; # 指向你的数据盘挂载点
        autoindex off;
        expires 30d;
        charset utf-8;
    }

    # 核心：反向代理到 Flask 应用
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

📖 使用说明
 * 首次访问：打开网站，点击 Register 注册账号。
 * 管理员权限：数据库中的第一个注册用户将自动获得 Admin 权限。
 * 数据更新：只需将新下载的文件通过 FTP/SFTP 上传到 /mnt/data/pixiv/ 下对应的作者目录，后台索引器会在 15 秒内自动发现并入库。
 * 权限修复：如果遇到 403 错误，请检查文件权限是否为 644，目录是否为 755。
📄 License
MIT License


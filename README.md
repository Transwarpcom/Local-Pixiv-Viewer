Local Pixiv Viewer (本地 Pixiv 镜像站)
一个功能强大的本地 Pixiv 浏览器/镜像站。基于 Python Flask + SQLite + Nginx 构建。
完美支持响应式布局 (移动端/桌面端)、PWA 安装、多语言 (中/英) 以及完整的社区互动功能（点赞、收藏、评论、关注）。
专为管理和浏览海量本地 Pixiv 收藏而设计，支持 插画、漫画 和 小说。
✨ 核心功能 (Features)
 * 📱 全平台响应式设计：移动端优先设计，支持 PWA 添加到主屏幕，体验接近原生 App。
 * 📚 全类型支持：完美展示插画、漫画图包，以及 小说 (TXT) 的排版阅读。
 * 🔍 智能元数据索引：自动解析文件名中的标签、系列、作者信息，支持标签搜索和相关推荐。
 * 🔄 自动后台同步：只需将文件存入硬盘，后台服务会在 15 秒内自动发现并入库，无需人工干预。
 * 👥 完整用户系统：
   * 注册/登录 (首个注册用户自动获取 管理员 权限)。
   * 个人中心、浏览历史、关注作者、关注动态 (Feed)。
   * 点赞、收藏、评论互动功能。
 * 🛡️ 内容管理：
   * 后台管理面板 (Dashboard)：查看系统状态、磁盘用量，管理用户和评论。
   * R-18 模糊开关：一键切换敏感内容模糊显示/隐藏。
   * 夜间模式：支持深色/浅色主题切换。
🚀 前置步骤：数据获取
本项目依赖本地数据文件，请使用 Chrome/Edge 扩展程序 Powerful Pixiv Downloader (PPD) 进行下载。
 * 安装 Powerful Pixiv Downloader 扩展。
 * 进入 PPD 的 控制面板 -> 下载 (Downloads) 设置。
 * [关键] 将 文件名设置 (Filename format) 修改为以下规则：
```text
   pixiv/{user}-{user_id}/{id}-{title}_{tags}-{series_title}_{series_order}-{series_id}
```

 * 下载完成后，将 pixiv 文件夹复制到服务器的数据盘挂载点（例如 /mnt/data）。
🛠️ 部署指南
1. 环境准备
# 更新源并安装基础依赖
```text
sudo apt update
sudo apt install -y python3-pip python3-venv nginx ffmpeg sqlite3
```

2. 项目初始化
假设部署目录为 /path/to/project：
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

3. 编译翻译文件
# 编译语言包 (.po -> .mo)
```text
pybabel compile -d translations
```

4. 配置 Systemd 服务
我们需要配置两个后台服务：一个是 Web 服务器，一个是后台自动索引器。
Web 服务 (/etc/systemd/system/pixiv_web.service):
(请修改 User, Group 和 WorkingDirectory 为实际值)
```text
[Unit]
Description=Pixiv Clone Web App
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=/path/to/project
Environment="PATH=/path/to/project/venv/bin"
# 生产环境建议使用 gunicorn，此处使用 flask run 演示
ExecStart=/path/to/project/venv/bin/python app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

索引服务 (/etc/systemd/system/pixiv_indexer.service):
```text
[Unit]
Description=Pixiv Auto Indexer
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=/path/to/project
Environment="PATH=/path/to/project/venv/bin"
# -u 参数用于实时输出日志
ExecStart=/path/to/project/venv/bin/python -u auto_indexer.py
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：
```text
sudo systemctl daemon-reload
sudo systemctl enable pixiv_web pixiv_indexer
sudo systemctl start pixiv_web pixiv_indexer
```

5. 配置 Nginx 反向代理
创建配置文件 /etc/nginx/sites-available/pixiv：
```text
server {
    listen 80;
    server_name your-domain.com; # 替换为你的域名或IP
    charset utf-8;
    root /path/to/project;

    # [核心优化] 图片/视频文件直接由 Nginx 读取硬盘，不经过 Python
    # 请将 /mnt/data/ 替换为你实际存放 pixiv 文件夹的路径
    location ^~ /files/ {
        alias /mnt/data/;
        autoindex off;
        expires 30d;
        charset utf-8;
    }

    # 核心应用代理
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

启用配置：
```text
sudo ln -s /etc/nginx/sites-available/pixiv /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

📖 使用说明
 * 管理员账号：
   * 访问网站，点击 注册 (Register)。
   * 注意：数据库中的第一个注册用户将自动获得 管理员 (Admin) 权限。
 * 后台管理：
   * 管理员登录后，点击导航栏右上角用户名 -> 管理面板 (Admin Panel)。
   * 可以查看磁盘用量、管理所有用户和评论。
 * 权限修复：
   * 如果遇到图片加载 403 Forbidden 错误，请确保 Nginx 用户有权读取数据目录。
   * chmod -R 755 /mnt/data

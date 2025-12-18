# Deployment Guide

This guide describes how to deploy the Pixiv Viewer application using Gunicorn and Nginx.

## Prerequisites

- Python 3.8+
- Nginx
- Supervisor (optional, for process management) or Systemd

## 1. Installation

1.  Clone the repository and navigate to the project directory.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## 2. Configuration

Set the following environment variables. You can put them in a `.env` file or export them in your service configuration.

-   `DATA_DIR`: Path to the directory containing your Pixiv data (e.g., `/mnt/data`).
-   `SECRET_KEY`: A long random string for session security.
-   `THUMBS_DIR`: (Optional) Path to store/read thumbnails if different from `DATA_DIR`.

## 3. Running with Gunicorn

Use `gunicorn` to run the application.

```bash
gunicorn -w 4 -b 127.0.0.1:8000 app:app
```

## 4. Nginx Configuration

Nginx acts as a reverse proxy and serves static files (images) efficiently.

Create a configuration file (e.g., `/etc/nginx/sites-available/pixiv_viewer`) with the following content.

**Important:** To fix issues with special characters (like `#`) in filenames, ensure you use `alias` correctly and that `charset utf-8;` is set.

```nginx
server {
    listen 80;
    server_name your_domain.com;

    # Serve static files (CSS, JS)
    location /static/ {
        alias /path/to/your/project/static/;
    }

    # Serve image files
    # The URL /files/ maps to your DATA_DIR on disk
    location /files/ {
        alias /mnt/data/;  # <--- Change this to your actual DATA_DIR
        charset utf-8;     # Ensure UTF-8 encoding for filenames
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    # Proxy everything else to Gunicorn
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site and restart Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/pixiv_viewer /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 5. Systemd Service (Optional)

Create `/etc/systemd/system/pixiv_viewer.service`:

```ini
[Unit]
Description=Gunicorn instance to serve Pixiv Viewer
After=network.target

[Service]
User=your_user
Group=www-data
WorkingDirectory=/path/to/your/project
Environment="PATH=/path/to/your/project/venv/bin"
Environment="DATA_DIR=/mnt/data"
Environment="SECRET_KEY=your_secret_key"
ExecStart=/path/to/your/project/venv/bin/gunicorn --workers 4 --bind 127.0.0.1:8000 app:app

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl start pixiv_viewer
sudo systemctl enable pixiv_viewer
```

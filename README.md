# TCM Tea Studio

中药代茶饮配方管理系统。当前版本包含登录、SQLite 数据库、顾客档案、体质分类、茶包方案生成、计量计算、配方单打印/另存 PDF。

## 本地运行

首次运行先创建管理员账号：

```bash
python3 server.py init-admin admin "请改成强密码"
```

启动服务：

```bash
python3 server.py
```

访问 `http://127.0.0.1:8080`，使用刚创建的账号登录。

数据库默认保存到 `data/tcm_tea_studio.sqlite3`。这个目录已加入 `.gitignore`，避免顾客资料被提交到 GitHub。

## 环境变量

- `TCM_HOST`：监听地址，默认 `127.0.0.1`
- `TCM_PORT`：监听端口，默认 `8080`
- `TCM_DB_PATH`：数据库文件路径，默认 `data/tcm_tea_studio.sqlite3`

## GitHub 推送

```bash
git init
git add .
git commit -m "Build login and database version"
git branch -M main
git remote add origin git@github.com:YOUR_NAME/tcm-tea-studio.git
git push -u origin main
```

## VPS 部署

1. 克隆代码：

```bash
sudo mkdir -p /opt/tcm-tea-studio
sudo chown -R $USER:$USER /opt/tcm-tea-studio
git clone git@github.com:YOUR_NAME/tcm-tea-studio.git /opt/tcm-tea-studio
cd /opt/tcm-tea-studio
python3 server.py init-admin admin "请改成强密码"
```

2. 创建 systemd 服务 `/etc/systemd/system/tcm-tea-studio.service`：

```ini
[Unit]
Description=TCM Tea Studio
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/tcm-tea-studio
Environment=TCM_HOST=127.0.0.1
Environment=TCM_PORT=8080
Environment=TCM_DB_PATH=/opt/tcm-tea-studio/data/tcm_tea_studio.sqlite3
ExecStart=/usr/bin/python3 /opt/tcm-tea-studio/server.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

3. 启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tcm-tea-studio
sudo systemctl status tcm-tea-studio
```

4. Nginx 反向代理：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

5. 更新代码：

```bash
cd /opt/tcm-tea-studio
git pull
sudo systemctl restart tcm-tea-studio
```

## 备份

定期备份数据库文件：

```bash
sqlite3 /opt/tcm-tea-studio/data/tcm_tea_studio.sqlite3 ".backup '/opt/tcm-tea-studio/data/backup-$(date +%F).sqlite3'"
```

## 合规提醒

本系统用于代茶饮配方管理和单据生成，不替代医疗诊断。正式使用前应结合当地监管要求、执业资质、隐私保护和门店合规流程复核。

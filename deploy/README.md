## **Startup App Automatically**
When Raspberry Pi boots up

Steps:

1. Create systemd service:
```
sudo nano /etc/systemd/system/owl_flask.service
```

2. Add file contents:
```
[Unit]
Description=Owl Flask Control Center
After=network.target

[Service]
User=owl
WorkingDirectory=/home/owl/owl_flask
ExecStart=/bin/bash -c 'source /home/owl/owl_flask/venv/bin/activate && exec python3 app.py'
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

3. Enable on boot (reload systemd, enable)

```
sudo systemctl daemon-reload
sudo systemctl enable owl_flask.service
```

4. (Optional) Start manually and check status (should say `active (running)`)
```
sudo systemctl start owl_flask.service
sudo systemctl status owl_flask.service
```

5. (Optional) View logs
```
journalctl -u owl_flask.service -f
```

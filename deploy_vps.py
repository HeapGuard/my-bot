import os
import sys
from pathlib import Path
import paramiko

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "89.169.53.163"
PORT = 22
USER = "root"
PASS = "dq3YPwJwMQ21"

LOCAL_DIR = Path(r"a:\Dev\my-bot")
REMOTE_DIR = "/root/my-bot"

def get_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
    return ssh

def run_cmd(cmd):
    print(f"\n[VPS] Running: {cmd}")
    ssh = get_ssh()
    try:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=300)
        out = stdout.read().decode('utf-8', errors='ignore')
        err = stderr.read().decode('utf-8', errors='ignore')
        if out.strip():
            print(f"[STDOUT]:\n{out.strip()[:1000]}")
        if err.strip():
            print(f"[STDERR]:\n{err.strip()[:1000]}")
        return out, err
    finally:
        ssh.close()

def upload_folder(sftp, local_path, remote_path):
    for item in os.listdir(local_path):
        if item in [".git", "__pycache__", "venv", ".idea", "output", "scratch", ".env.example", "test_direct_ip.py", "deploy_vps.py"]:
            continue
        l_item = local_path / item
        r_item = f"{remote_path}/{item}"
        
        if l_item.is_dir():
            try:
                sftp.mkdir(r_item)
            except Exception:
                pass
            upload_folder(sftp, l_item, r_item)
        else:
            print(f"Uploading {l_item.name} -> {r_item}")
            sftp.put(str(l_item), r_item)

def main():
    print(f"Connecting to VPS at {HOST}...")
    ssh = get_ssh()
    print("Successfully connected via SSH!")

    # 1. Update OS and install system dependencies
    run_cmd("apt-get update && apt-get install -y python3 python3-pip python3-venv git curl fonts-inter fonts-freefont-ttf || true")

    # 2. Prepare remote folder
    run_cmd(f"mkdir -p {REMOTE_DIR}")

    # 3. Upload project files via SFTP
    print("\nUploading project files...")
    sftp = ssh.open_sftp()
    upload_folder(sftp, LOCAL_DIR, REMOTE_DIR)
    sftp.close()
    ssh.close()
    print("File upload complete!")

    # 4. Finish installation and start service via remote script
    remote_script = f"""#!/bin/bash
set -e
cd {REMOTE_DIR}
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
./venv/bin/playwright install chromium
./venv/bin/playwright install-deps chromium || true

cat << 'EOF' > /etc/systemd/system/storieshub.service
[Unit]
Description=StoriesHub Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory={REMOTE_DIR}
ExecStart={REMOTE_DIR}/venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable storieshub
systemctl restart storieshub
"""
    
    ssh = get_ssh()
    sftp = ssh.open_sftp()
    with sftp.file(f"{REMOTE_DIR}/setup.sh", "w") as f:
        f.write(remote_script)
    sftp.chmod(f"{REMOTE_DIR}/setup.sh", 0o755)
    sftp.close()
    ssh.close()

    print("\nRunning remote setup script...")
    run_cmd(f"bash {REMOTE_DIR}/setup.sh")

    # 5. Verify status
    out, err = run_cmd("systemctl status storieshub --no-pager")
    print("\n=== SYSTEMD SERVICE STATUS ===")
    print(out)

    print("\nDeployment completed successfully!")

if __name__ == "__main__":
    main()

import os
import sqlite3
import requests

# 1. Clean local files
g1_dir = r"c:\Users\BHARAT\Downloads\aurahosting-main\aurahosting-main\data\workspace\1\group_1"
for fname in ["group.py", "bot.db", "bot_config.json"]:
    fpath = os.path.join(g1_dir, fname)
    if os.path.exists(fpath):
        os.remove(fpath)
        print(f"Removed local {fpath}")

# Verify only 2 files remain in local group_1
remaining = os.listdir(g1_dir)
print(f"[1] Local group_1 contents ({len(remaining)}):", remaining)

# 2. Update local data/users.db
db_path = r"c:\Users\BHARAT\Downloads\aurahosting-main\aurahosting-main\data\users.db"
conn = sqlite3.connect(db_path)
conn.execute("UPDATE files SET entry_file = 'group_1.py' WHERE id = 12")
conn.execute("DELETE FROM files WHERE id IN (13, 18)")
conn.commit()
print("[2] Updated local data/users.db (file 12 entry_file set to group_1.py, records 13 and 18 removed)")
conn.close()

# 3. Clean live Render server
BASE_URL = 'https://aura-hosting-panel.onrender.com'
s = requests.Session()
s.post(f'{BASE_URL}/login', data={'email': 'admin@example.com', 'password': 'admin123'}, timeout=15)

for rel in ['group_1/group.py', 'group_1/bot.db', 'group_1/bot_config.json']:
    r_del = s.post(f'{BASE_URL}/workspace/delete', data={'path': rel}, timeout=15)
    print(f"    Live delete {rel}: status {r_del.status_code}")

# Update bot config on Render
r_cfg = s.post(f'{BASE_URL}/api/bot_config/12', json={'entry_file': 'group_1.py', 'custom_cmd': ''}, timeout=15)
print("    Bot 12 config update:", r_cfg.status_code, r_cfg.text)

# Restart bot 12
r_restart = s.post(f'{BASE_URL}/api/restart/12', timeout=20)
print("    Bot 12 restart:", r_restart.status_code, r_restart.text)

# Check what files are left in group_1 on Render
r_ws = s.get(f'{BASE_URL}/workspace?path=group_1', timeout=15)
import re
paths = re.findall(r'path=([^"\'&>]+)', r_ws.text)
print("\n[3] Files inside group_1 on Render now:", set(paths))

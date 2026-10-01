import json
import shutil
import requests

# 1. Update local files
src = r"c:\Users\BHARAT\Downloads\group.py"
dest1 = r"c:\Users\BHARAT\Downloads\aurahosting-main\aurahosting-main\data\workspace\1\group_1\group.py"
dest2 = r"c:\Users\BHARAT\Downloads\aurahosting-main\aurahosting-main\data\workspace\1\group_1\group_1.py"
db_json_local = r"c:\Users\BHARAT\Downloads\aurahosting-main\aurahosting-main\data\workspace\1\group_1\database.json"

shutil.copy2(src, dest1)
shutil.copy2(src, dest2)

initial_db = {
    "users": [],
    "groups": [],
    "approved_groups": [],
    "approved_groups_meta": {},
    "official_group_id": None,
    "official_group_link": "",
    "group_alert_msg": "",
    "group_alert_btn_text": "🚀 JOIN OFFICIAL GROUP",
    "group_alert_btn_emoji": "6138734238628845209",
    "disabled_commands": [],
    "leak_approvals": [],
    "trial_usage": {},
    "trial_limit": 2,
    "trial_user_limit": 0,
    "trial_users": [],
    "maintenance_mode": False,
    "blacklisted_numbers": [],
    "bot_offline": False,
    "last_broadcast": [],
    "force_join_targets": []
}

with open(db_json_local, "w", encoding="utf-8") as f:
    json.dump(initial_db, f, indent=4)

print("[1] Local files updated.")

# 2. Push to live server
BASE_URL = 'https://aura-hosting-panel.onrender.com'
s = requests.Session()
s.post(f'{BASE_URL}/login', data={'email': 'admin@example.com', 'password': 'admin123'}, timeout=15)

with open(src, "r", encoding="utf-8") as f:
    group_code = f.read()

r1 = s.post(f'{BASE_URL}/admin/workspace/1/save', data={
    'path': 'group_1/group.py',
    'content': group_code
}, timeout=20)
print("    Saved group.py:", r1.status_code)

r2 = s.post(f'{BASE_URL}/admin/workspace/1/save', data={
    'path': 'group_1/group_1.py',
    'content': group_code
}, timeout=20)
print("    Saved group_1.py:", r2.status_code)

r3 = s.post(f'{BASE_URL}/admin/workspace/1/save', data={
    'path': 'group_1/database.json',
    'content': json.dumps(initial_db, indent=4)
}, timeout=20)
print("    Saved database.json:", r3.status_code)

# 3. Restart Bot 12
r_restart = s.post(f'{BASE_URL}/api/restart/12', timeout=20)
print("    Restart response:", r_restart.status_code, r_restart.text)

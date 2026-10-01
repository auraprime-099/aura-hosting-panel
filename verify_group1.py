import requests
import re

s = requests.Session()
BASE_URL = 'https://aura-hosting-panel.onrender.com'
s.post(f'{BASE_URL}/login', data={'email': 'admin@example.com', 'password': 'admin123'}, timeout=15)

r_ws = s.get(f'{BASE_URL}/workspace?path=group_1', timeout=15)
names = re.findall(r'<div class="workspace-name">([^<]+)</div>', r_ws.text)
print("Items in group_1 on Render:", names)

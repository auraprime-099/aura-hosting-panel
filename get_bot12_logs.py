import requests

BASE_URL = 'https://aura-hosting-panel.onrender.com'
s = requests.Session()
s.post(f'{BASE_URL}/login', data={'email': 'admin@example.com', 'password': 'admin123'}, timeout=15)

# Fetch logs for bot 12
r_logs = s.get(f'{BASE_URL}/api/logs/12', timeout=15)
print("Logs status:", r_logs.status_code)
print("Logs content:\n", r_logs.text)

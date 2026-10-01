import pytest
import os
import sys

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db_session, User, File, PasswordResetOTP, get_user_by_email, get_user_workspace

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        yield client

def test_register_and_login(client):
    import time
    ts = int(time.time() * 1000)
    test_email = f"authtest_{ts}@example.com"
    test_pass = "securepass123"

    # Register
    res = client.post('/register', data={
        'username': f'authtest_{ts}',
        'email': test_email,
        'password': test_pass,
        'confirm_password': test_pass
    }, follow_redirects=True)
    assert res.status_code == 200

    user = get_user_by_email(test_email)
    assert user is not None
    assert user.plain_password == test_pass

    # Login
    res = client.post('/login', data={
        'email': test_email,
        'password': test_pass
    }, follow_redirects=True)
    assert res.status_code == 200

    user_refreshed = get_user_by_email(test_email)
    assert user_refreshed.plain_password == test_pass

def test_workspace_rename(client):
    import time
    ts = int(time.time() * 1000)
    test_email = f'renametest_{ts}@example.com'
    test_pass = 'pass1234'

    # Register & Login
    client.post('/register', data={
        'username': f'renametester_{ts}',
        'email': test_email,
        'password': test_pass,
        'confirm_password': test_pass
    })
    client.post('/login', data={'email': test_email, 'password': test_pass})

    user = get_user_by_email(test_email)
    ws = get_user_workspace(user.id)

    # Create a test file in workspace
    client.post('/workspace/new_file', data={
        'current_path': '',
        'filename': 'original_test_file.txt'
    }, follow_redirects=True)

    orig_path = os.path.join(ws, 'original_test_file.txt')
    assert os.path.exists(orig_path)

    # Rename it
    res = client.post('/workspace/rename', data={
        'old_path': 'original_test_file.txt',
        'new_name': 'renamed_test_file.txt'
    }, follow_redirects=True)

    assert res.status_code == 200
    assert not os.path.exists(orig_path)
    new_path = os.path.join(ws, 'renamed_test_file.txt')
    assert os.path.exists(new_path)

def test_bot_config_api(client):
    import time
    ts = int(time.time() * 1000) + 1
    test_email = f'configtest_{ts}@example.com'
    test_pass = 'pass1234'

    # Register & Login
    client.post('/register', data={
        'username': f'configtester_{ts}',
        'email': test_email,
        'password': test_pass,
        'confirm_password': test_pass
    })
    client.post('/login', data={'email': test_email, 'password': test_pass})

    user = get_user_by_email(test_email)
    ws = get_user_workspace(user.id)
    bot_path = os.path.join(ws, 'test_bot.py')
    with open(bot_path, 'w', encoding='utf-8') as f:
        f.write('print("Hello from test bot")')

    file_rec = File(
        user_id=user.id,
        filename='test_bot.py',
        orig_name='test_bot.py',
        path=bot_path,
        file_type='python',
        status='Stopped'
    )
    db_session.add(file_rec)
    db_session.commit()

    # GET config
    res = client.get(f'/api/bot_config/{file_rec.id}')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['orig_name'] == 'test_bot.py'

    # POST config
    res = client.post(f'/api/bot_config/{file_rec.id}', json={
        'entry_file': 'test_bot.py',
        'custom_cmd': 'python test_bot.py --test-mode',
        'restart': False
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['entry_file'] == 'test_bot.py'
    assert data['custom_cmd'] == 'python test_bot.py --test-mode'

    updated_rec = db_session.get(File, file_rec.id)
    assert updated_rec.custom_cmd == 'python test_bot.py --test-mode'


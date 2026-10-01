#!/usr/bin/env python3
"""
AURA HOSTING – Python & PHP bot hosting with persistent storage for Railway.
Auto‑detects .db and .json files created by bots (no auto-creation).
Automatically installs missing Python modules when detected in logs.
Admin Super File Manager – browse, edit, delete any user's files.
"""

import os
import sys
import subprocess
import threading
import time
import shutil
import zipfile
import tarfile
import ast
import importlib
import importlib.util
import logging
import tempfile
import json
import stat
import re
import random
import smtplib
from email.mime.text import MIMEText
import zoneinfo
from datetime import datetime, timezone, timedelta
from functools import wraps
from pathlib import Path
import urllib.parse

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import scoped_session, sessionmaker, relationship, declarative_base
from flask_session import Session

# -----------------------------------------------------------------------------
# 1. Logging & Timezone
# -----------------------------------------------------------------------------
# Use WARNING level to minimize log output and save disk space
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.WARNING
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
# Suppress noisy third-party loggers
for _noisy in ['werkzeug', 'sqlalchemy', 'urllib3', 'requests']:
    logging.getLogger(_noisy).setLevel(logging.ERROR)

# Set timezone to Indian Standard Time (IST)
IST = zoneinfo.ZoneInfo("Asia/Kolkata")

# -----------------------------------------------------------------------------
# 2. Configuration & .env loading
# -----------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_path):
    try:
        with open(env_path, 'r', encoding='utf-8-sig', errors='replace') as ef:
            for eline in ef:
                eline = eline.strip()
                if eline and not eline.startswith('#') and '=' in eline:
                    k, v = eline.split('=', 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v
        logger.info("Loaded environment variables from .env")
    except Exception as e:
        logger.warning(f"Failed to load .env: {e}")

SECRET_KEY = os.environ.get("SECRET_KEY", "a-very-secret-key-change-this-in-production")
CPU_THRESHOLD = float(os.environ.get("CPU_THRESHOLD", "90.0"))
MEMORY_THRESHOLD = float(os.environ.get("MEMORY_THRESHOLD", "90.0"))
MAX_RUNNING_PROCESSES = int(os.environ.get("MAX_RUNNING_PROCESSES", "10"))
MAX_FILES_PER_USER = int(os.environ.get("MAX_FILES_PER_USER", "3"))
ADMIN_EMAILS = os.environ.get("ADMIN_EMAILS", "admin@example.com,auralion555@gmail.com").split(",")

# SMTP Configuration (per .env.example: MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD, MAIL_DEFAULT_SENDER)
MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True").lower() in ("true", "1", "yes")
MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
MAIL_FROM = os.environ.get("MAIL_FROM", "noreply@aurahost.com")

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")

# -----------------------------------------------------------------------------
# 3. Directories with Persistent Storage (Railway)
# -----------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

railway_mount = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH')
if railway_mount:
    DATA_DIR = railway_mount
elif os.environ.get('RAILWAY_ENVIRONMENT'):
    DATA_DIR = '/app/data'
else:
    DATA_DIR = os.path.join(BASE_DIR, "data")

# Keep sessions in /tmp so they NEVER fill the persistent volume
SESSION_DIR = os.path.join(tempfile.gettempdir(), "aura_sessions")

DB_PATH = os.path.join(DATA_DIR, "users.db")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
# Use /tmp for logs to avoid filling Railway persistent volume
LOGS_DIR = os.path.join(tempfile.gettempdir(), "aura_logs")
TEMP_DIR = os.path.join(tempfile.gettempdir(), "aura_temp")
WORKSPACE_ROOT = os.path.join(DATA_DIR, "workspace")

# --- Emergency Startup Cleanup: Free Railway Volume Space ---
# Purge legacy logs and old session directories from DATA_DIR to immediately resolve Errno 28 (No space left)
for legacy_name in ["logs", "flask_session", "temp"]:
    target_legacy = os.path.join(DATA_DIR, legacy_name)
    if os.path.exists(target_legacy):
        try:
            if os.path.isdir(target_legacy):
                shutil.rmtree(target_legacy, ignore_errors=True)
            else:
                os.remove(target_legacy)
            logger.info(f"Removed legacy folder from volume: {target_legacy}")
        except Exception as e:
            logger.warning(f"Could not purge {target_legacy}: {e}")

# Also delete any loose .log files inside DATA_DIR to free maximum space
try:
    if os.path.exists(DATA_DIR):
        for root, dirs, files in os.walk(DATA_DIR):
            for f in files:
                if f.endswith('.log') or f.endswith('.log.old'):
                    try:
                        os.remove(os.path.join(root, f))
                    except Exception:
                        pass
except Exception as e:
    logger.warning(f"Error purging log files from {DATA_DIR}: {e}")

for directory in [DATA_DIR, UPLOADS_DIR, LOGS_DIR, TEMP_DIR, WORKSPACE_ROOT, SESSION_DIR]:
    os.makedirs(directory, exist_ok=True)
    if directory == SESSION_DIR:
        try:
            os.chmod(SESSION_DIR, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
        except Exception:
            pass

# -----------------------------------------------------------------------------
# 4. Database setup
# -----------------------------------------------------------------------------
engine = create_engine(f'sqlite:///{DB_PATH}', connect_args={'check_same_thread': False})
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    username = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(IST))
    last_login = Column(DateTime, nullable=True)
    plain_password = Column(String, nullable=True)
    files = relationship("File", back_populates="user")

class File(Base):
    __tablename__ = 'files'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    filename = Column(String, nullable=False)
    orig_name = Column(String, nullable=False)
    path = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(IST))
    file_type = Column(String, nullable=False)
    pid = Column(Integer, nullable=True)
    status = Column(String, default='Stopped')
    entry_file = Column(String, nullable=True)
    custom_cmd = Column(String, nullable=True)
    user = relationship("User", back_populates="files")
    runs = relationship("Run", back_populates="file", cascade="all, delete-orphan")

class Run(Base):
    __tablename__ = 'runs'
    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    started_at = Column(DateTime, default=lambda: datetime.now(IST))
    finished_at = Column(DateTime, nullable=True)
    pid = Column(Integer, nullable=True)
    log_path = Column(String, nullable=True)
    exit_code = Column(Integer, nullable=True)
    file = relationship("File", back_populates="runs")

class PasswordResetOTP(Base):
    __tablename__ = 'password_reset_otps'
    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False)
    otp_code = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_verified = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(IST))

Base.metadata.create_all(bind=engine)

# Auto-migration for SQLite: ensure entry_file and custom_cmd exist
try:
    with engine.connect() as conn:
        cursor = conn.connection.cursor()
        cursor.execute("PRAGMA table_info(files);")
        existing_cols = [r[1] for r in cursor.fetchall()]
        if 'entry_file' not in existing_cols:
            cursor.execute("ALTER TABLE files ADD COLUMN entry_file TEXT;")
        if 'custom_cmd' not in existing_cols:
            cursor.execute("ALTER TABLE files ADD COLUMN custom_cmd TEXT;")
        
        cursor.execute("PRAGMA table_info(users);")
        user_cols = [r[1] for r in cursor.fetchall()]
        if 'plain_password' not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN plain_password TEXT;")
        conn.connection.commit()
except Exception as e:
    logger.warning(f"Database column migration note: {e}")

def send_otp_email(to_email, otp_code):
    subject = "Aura Host - Your Password Reset OTP"
    body = f"Hello,\n\nYour OTP for resetting your Aura Host password is: {otp_code}\n\nThis OTP is valid for 10 minutes.\nIf you did not request this, please ignore this message."
    if MAIL_USERNAME and MAIL_PASSWORD:
        try:
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = MAIL_FROM
            msg['To'] = to_email
            with smtplib.SMTP(MAIL_SERVER, MAIL_PORT) as server:
                if MAIL_USE_TLS:
                    server.starttls()
                server.login(MAIL_USERNAME, MAIL_PASSWORD)
                server.sendmail(MAIL_FROM, [to_email], msg.as_string())
            logger.info(f"OTP email sent via SMTP to {to_email}")
            return True, "OTP sent to your email address."
        except Exception as e:
            logger.error(f"Failed to send email via SMTP: {e}")
            return True, f"Development Mode OTP Code: {otp_code} (SMTP failed: {str(e)})"
    else:
        logger.info(f"[DEV OTP] OTP for {to_email} is {otp_code}")
        return True, f"OTP generated successfully! Your code is {otp_code}"

# -----------------------------------------------------------------------------
# 5. Helper functions
# -----------------------------------------------------------------------------
def get_user_by_email(email):
    return User.query.filter_by(email=email).first()

def get_user_by_id(user_id):
    return db_session.get(User, user_id)

def add_file_record(user_id, filename, orig_name, path, file_type, entry_file=None, custom_cmd=None):
    file = File(
        user_id=user_id,
        filename=filename,
        orig_name=orig_name,
        path=path,
        file_type=file_type,
        entry_file=entry_file,
        custom_cmd=custom_cmd,
        status='Stopped'
    )
    db_session.add(file)
    db_session.commit()
    return file.id

def list_user_files(user_id):
    return File.query.filter_by(user_id=user_id).order_by(File.id.desc()).all()

def list_all_files():
    return db_session.query(File).join(User).order_by(File.id.desc()).all()

def get_file_record(file_id):
    return db_session.get(File, file_id)

def remove_file_record(file_id):
    file = db_session.get(File, file_id)
    if file:
        file_path = file.path
        try:
            stop_file_process(file_id)
        except Exception:
            pass
        Run.query.filter_by(file_id=file_id).delete()
        db_session.delete(file)
        db_session.commit()
        if file_path:
            force_delete_path(file_path)

def record_run_start(file_id, pid, log_path):
    run = Run(file_id=file_id, pid=pid, log_path=log_path)
    db_session.add(run)
    db_session.commit()
    return run.id

def record_run_finish(run_id, exit_code):
    run = db_session.get(Run, run_id)
    if run:
        run.finished_at = datetime.now(IST)
        run.exit_code = exit_code
        db_session.commit()

def update_file_status(file_id, pid, status):
    file = db_session.get(File, file_id)
    if file:
        file.pid = pid
        file.status = status
        db_session.commit()

def now_iso():
    return datetime.now(IST).isoformat()

def get_user_workspace(user_id):
    workspace = os.path.join(WORKSPACE_ROOT, str(user_id))
    os.makedirs(workspace, exist_ok=True)
    return workspace

def get_safe_path(user_id, rel_path):
    workspace = os.path.abspath(get_user_workspace(user_id))
    # Strip any leading slashes or backslashes to avoid absolute path takeover
    clean_rel = (rel_path or '').lstrip('/\\')
    requested = os.path.abspath(os.path.normpath(os.path.join(workspace, clean_rel)))
    if requested != workspace and not requested.startswith(workspace + os.sep):
        return None
    return requested

def register_db_json_file(user_id, file_path):
    if not os.path.exists(file_path):
        return False
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in ['.db', '.json']:
        return False
    file_type = 'database' if ext == '.db' else 'json'
    existing = File.query.filter_by(path=file_path).first()
    if existing:
        return True
    orig_name = os.path.basename(file_path)
    filename = f"{int(time.time())}_{orig_name}"
    add_file_record(user_id, filename, orig_name, file_path, file_type)
    logger.info(f"Auto-registered {file_type} file: {file_path}")
    return True

def scan_workspace_for_db_json(user_id):
    workspace = get_user_workspace(user_id)
    for root, dirs, files in os.walk(workspace):
        for f in files:
            if f.endswith('.db') or f.endswith('.json'):
                full_path = os.path.join(root, f)
                register_db_json_file(user_id, full_path)

def extract_missing_module(log_text):
    """Extract module name from ModuleNotFoundError or ImportError line."""
    match = re.search(r"ModuleNotFoundError: No module named '([^']+)'", log_text)
    if match:
        mod = match.group(1).split('.')[0].strip()
        return mod if mod else None
    match = re.search(r"ImportError: No module named '?([^'\n]+)'?", log_text)
    if match:
        mod = match.group(1).strip("'\"").split('.')[0].strip()
        return mod if mod else None
    return None

# -----------------------------------------------------------------------------
# 6. Process management & system monitoring
# -----------------------------------------------------------------------------
processes = {}
proc_lock = threading.Lock()

def kill_process_tree(pid):
    """Robustly terminate a process and all its children on Windows and Linux."""
    if not pid:
        return
    try:
        import psutil
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            try:
                child.kill()
            except Exception:
                pass
        parent.kill()
        parent.wait(timeout=3)
        return
    except Exception:
        pass
    if os.name == 'nt':
        try:
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)],
                           capture_output=True, timeout=5)
        except Exception:
            pass

def get_cpu_percent():
    try:
        import psutil
        return float(psutil.cpu_percent(interval=None))
    except Exception:
        pass
    try:
        with open('/proc/stat', 'r') as f:
            line = f.readline().strip()
            parts = line.split()
            user = int(parts[1])
            nice = int(parts[2])
            system = int(parts[3])
            idle = int(parts[4])
            total = user + nice + system + idle
            time.sleep(0.05)
            with open('/proc/stat', 'r') as f2:
                line2 = f2.readline().strip()
                parts2 = line2.split()
                user2 = int(parts2[1])
                nice2 = int(parts2[2])
                system2 = int(parts2[3])
                idle2 = int(parts2[4])
                total2 = user2 + nice2 + system2 + idle2
            delta_total = total2 - total
            delta_idle = idle2 - idle
            cpu_percent = (delta_total - delta_idle) * 100.0 / delta_total if delta_total > 0 else 0
            return max(0, min(100, cpu_percent))
    except Exception:
        return 0.0

def get_memory_percent():
    try:
        import psutil
        return float(psutil.virtual_memory().percent)
    except Exception:
        pass
    try:
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()
        total = available = None
        for line in lines:
            if line.startswith('MemTotal:'):
                total = int(line.split()[1])
            elif line.startswith('MemAvailable:'):
                available = int(line.split()[1])
            if total and available:
                break
        if total and available:
            used = total - available
            return (used / total) * 100
    except Exception:
        return 0.0

def get_system_load():
    try:
        cpu = get_cpu_percent()
        mem = get_memory_percent()
        proc_count = len(processes)
        return cpu, mem, proc_count
    except Exception:
        return 0.0, 0.0, 0

def should_stop_due_to_load():
    load, memory, proc_count = get_system_load()
    if proc_count >= MAX_RUNNING_PROCESSES:
        return True, f"Too many running processes ({proc_count}/{MAX_RUNNING_PROCESSES})"
    if load >= CPU_THRESHOLD:
        return True, f"High CPU load ({load:.1f}%)"
    if memory >= MEMORY_THRESHOLD:
        return True, f"High memory usage ({memory:.1f}%)"
    return False, None

# -----------------------------------------------------------------------------
# 7. File utilities (extract, find main, deps)
# -----------------------------------------------------------------------------
def get_file_type(filename):
    name = filename.lower()
    if name.endswith(".py"):
        return "python"
    if name.endswith(".php"):
        return "php"
    if name.endswith(".db"):
        return "database"
    if name.endswith(".json"):
        return "json"
    if name.endswith(".zip"):
        return "zip"
    if any(name.endswith(ext) for ext in [".tar", ".tar.gz", ".tgz"]):
        return "archive"
    return "unknown"

def extract_archive(file_path, extract_dir):
    try:
        if file_path.lower().endswith(".zip"):
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
        elif file_path.lower().endswith(".tar.gz") or file_path.lower().endswith(".tgz"):
            with tarfile.open(file_path, 'r:gz') as tar_ref:
                tar_ref.extractall(extract_dir)
        elif file_path.lower().endswith(".tar"):
            with tarfile.open(file_path, 'r') as tar_ref:
                tar_ref.extractall(extract_dir)
        else:
            return False, "Unsupported archive format"

        # If archive had everything wrapped inside a single root folder, unwrap it into extract_dir
        try:
            subitems = [i for i in os.listdir(extract_dir) if not i.startswith(('__MACOSX', '.'))]
            if len(subitems) == 1:
                single_sub = os.path.join(extract_dir, subitems[0])
                if os.path.isdir(single_sub):
                    for item in os.listdir(single_sub):
                        dest_item = os.path.join(extract_dir, item)
                        if not os.path.exists(dest_item):
                            shutil.move(os.path.join(single_sub, item), dest_item)
                    try:
                        shutil.rmtree(single_sub, ignore_errors=True)
                    except Exception:
                        pass
        except Exception:
            pass

        return True, None
    except Exception as e:
        return False, str(e)

def find_main_file(directory):
    if not os.path.isdir(directory):
        return directory if os.path.isfile(directory) else None

    priority = [
        "run.py", "main.py", "bot.py", "app.py", "server.py", "index.py", "script.py",
        "main.php", "bot.php", "index.php"
    ]
    # 1. First priority: direct matches at root of the project
    for name in priority:
        path = os.path.join(directory, name)
        if os.path.isfile(path):
            return path

    # 2. Check for modular python bots (e.g. Telegram music bots, modular bots with __main__.py, start scripts, Procfile)
    modular_pkg = None
    # 2a. Check if 'start' or 'Procfile' specifies 'python -m <pkg>' or 'python3 -m <pkg>'
    start_path = os.path.join(directory, "start")
    if os.path.isfile(start_path):
        try:
            with open(start_path, 'r', encoding='utf-8', errors='ignore') as sf:
                s_content = sf.read()
            m = re.search(r"python[3]?\s+-m\s+([a-zA-Z0-9_]+)", s_content)
            if m:
                modular_pkg = m.group(1)
        except Exception:
            pass

    if not modular_pkg:
        procfile_path = os.path.join(directory, "Procfile")
        if os.path.isfile(procfile_path):
            try:
                with open(procfile_path, 'r', encoding='utf-8', errors='ignore') as pf:
                    p_content = pf.read()
                m = re.search(r"python[3]?\s+-m\s+([a-zA-Z0-9_]+)", p_content)
                if m:
                    modular_pkg = m.group(1)
            except Exception:
                pass

    if not modular_pkg:
        # 2b. Check immediate subdirectories for __main__.py (e.g. ShrutiMusic/__main__.py, YukkiMusic/__main__.py)
        ignore_dirs = {'__pycache__', '.git', 'tests', 'static', 'templates', 'venv', 'env', 'node_modules', 'strings', 'cache', 'downloads'}
        try:
            for item in os.listdir(directory):
                sub_dir = os.path.join(directory, item)
                if os.path.isdir(sub_dir) and item.lower() not in ignore_dirs:
                    if os.path.isfile(os.path.join(sub_dir, "__main__.py")):
                        modular_pkg = item
                        break
        except Exception:
            pass

    # If a modular package was detected, auto-generate run.py at project root!
    if modular_pkg:
        run_py_path = os.path.join(directory, "run.py")
        try:
            with open(run_py_path, 'w', encoding='utf-8') as rf:
                rf.write(f'''# Auto-generated root entrypoint for modular bot package: {modular_pkg}
import os
import sys
import runpy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

if __name__ == "__main__":
    runpy.run_module("{modular_pkg}", run_name="__main__", alter_sys=True)
''')
            logger.info(f"Auto-generated root runner run.py for modular package '{modular_pkg}'")
            return run_py_path
        except Exception as e:
            logger.warning(f"Could not auto-generate run.py for {modular_pkg}: {e}")

    # 3. Check 1-level deep subdirectories for standard runners (e.g. src/main.py, bot/main.py)
    ignore_subdirs = {'__pycache__', '.git', 'tests', 'static', 'templates', 'venv', 'env', 'node_modules', 'core', 'utils', 'plugins', 'helpers', 'handlers'}
    try:
        for item in os.listdir(directory):
            sub_dir = os.path.join(directory, item)
            if os.path.isdir(sub_dir) and item.lower() not in ignore_subdirs:
                for name in priority:
                    candidate = os.path.join(sub_dir, name)
                    if os.path.isfile(candidate):
                        return candidate
    except Exception:
        pass

    # 4. Any top-level .py or .php file
    try:
        for item in os.listdir(directory):
            if item.endswith((".py", ".php")) and not item.startswith(('test_', 'setup.py')):
                return os.path.join(directory, item)
    except Exception:
        pass

    return None

def install_requirements_from_file(req_path, log_file=None):
    if not os.path.exists(req_path):
        return True, "No requirements.txt found"

    def log(msg):
        logger.info(msg)
        if log_file:
            try:
                with open(log_file, 'a', encoding='utf-8', errors='replace') as f:
                    f.write(f"[Aura Auto-Install] {msg}\n")
            except Exception:
                pass

    try:
        log(f"Installing dependencies from {os.path.basename(req_path)}...")
        # Step 1: Attempt standard pip install for the whole requirements file
        res = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", req_path, "--disable-pip-version-check"],
            capture_output=True, text=True, timeout=180
        )
        if res.returncode == 0:
            log("All requirements installed successfully!")
            return True, "Dependencies installed/verified successfully"

        # Step 2: Resilient line-by-line fallback install if batch install had issues
        log("Batch requirements install had conflicts. Installing packages individually...")
        with open(req_path, 'r', encoding='utf-8', errors='replace') as rf:
            lines = [l.strip() for l in rf]

        success_count = 0
        fail_count = 0
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install", line, "--disable-pip-version-check"],
                capture_output=True, text=True, timeout=120
            )
            if r.returncode == 0:
                success_count += 1
            else:
                # If pinned version (e.g. pillow==9.5.0, py-tgcalls==0.9.7) failed, retry with unpinned package name
                pkg_bare = re.split(r'[=<>!~@]', line)[0].strip()
                if pkg_bare and pkg_bare != line:
                    r2 = subprocess.run(
                        [sys.executable, "-m", "pip", "install", pkg_bare, "--disable-pip-version-check"],
                        capture_output=True, text=True, timeout=120
                    )
                    if r2.returncode == 0:
                        log(f"Installed fallback '{pkg_bare}' (replacing pinned '{line}')")
                        success_count += 1
                        continue
                log(f"Notice: Package '{line}' skipped: {r.stderr.strip()[:100]}")
                fail_count += 1

        msg = f"Installed {success_count} packages" + (f", {fail_count} failed/skipped" if fail_count else "")
        log(f"Requirements install complete: {msg}")
        return True, msg
    except Exception as e:
        err = f"Error installing requirements: {str(e)}"
        log(err)
        return False, err

def extract_all_imports(directory):
    """Recursively extract all third-party import module names from all .py files in directory."""
    imports = set()
    local_names = set()

    # Identify project-local files and folders to exclude them from pip installs
    for root, dirs, files in os.walk(directory):
        for d in dirs:
            local_names.add(d)
        for f in files:
            if f.endswith('.py'):
                local_names.add(os.path.splitext(f)[0])

    stdlib = getattr(sys, 'stdlib_module_names', set())

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8-sig', errors='replace') as f:
                        tree = ast.parse(f.read())
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                mod = alias.name.split('.')[0]
                                if mod not in local_names and mod not in stdlib and mod not in sys.builtin_module_names:
                                    imports.add(mod)
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                mod = node.module.split('.')[0]
                                if mod not in local_names and mod not in stdlib and mod not in sys.builtin_module_names:
                                    imports.add(mod)
                except Exception as e:
                    logger.warning(f"Could not parse {file_path}: {e}")
    return imports

PACKAGE_NAME_MAP = {
    'telebot': 'pyTelegramBotAPI',
    'telegram': 'python-telegram-bot',
    'pyrogram': 'pyrogram',
    'pytgcalls': 'py-tgcalls',
    'py_yt': 'py-yt-search',
    'PIL': 'Pillow',
    'cv2': 'opencv-python',
    'Crypto': 'pycryptodome',
    'bs4': 'beautifulsoup4',
    'requests': 'requests',
    'aiohttp': 'aiohttp',
    'aiofiles': 'aiofiles',
    'discord': 'discord.py',
    'flask': 'flask',
    'django': 'django',
    'numpy': 'numpy',
    'pandas': 'pandas',
    'matplotlib': 'matplotlib',
    'selenium': 'selenium',
    'scrapy': 'scrapy',
    'dotenv': 'python-dotenv',
    'yaml': 'PyYAML',
    'dns': 'dnspython',
    'fitz': 'PyMuPDF',
    'git': 'GitPython',
    'gtts': 'gTTS',
    'motor': 'motor',
    'pymongo': 'pymongo',
    'speedtest': 'speedtest-cli',
    'spotipy': 'spotipy',
    'telegraph': 'telegraph',
    'unidecode': 'unidecode',
    'yt_dlp': 'yt-dlp',
    'tgcrypto': 'tgcrypto',
    'kurigram': 'kurigram',
    'pyrofork': 'pyrofork',
    'hachoir': 'hachoir',
    'heroku3': 'heroku3',
    'httpx': 'httpx',
    'pytz': 'pytz',
    'psutil': 'psutil',
    'pykeyboard': 'pykeyboard',
    'youtube_search': 'youtube-search',
    'youtube_search_python': 'youtube-search-python',
    'dateutil': 'python-dateutil',
    'magic': 'python-magic',
    'jwt': 'PyJWT',
    'socks': 'PySocks',
    'mysql': 'mysql-connector-python',
    'psycopg2': 'psycopg2-binary',
    'sqlalchemy': 'SQLAlchemy',
}

def install_single_module(mod, log_file=None):
    pkg = PACKAGE_NAME_MAP.get(mod, mod)
    def log(msg):
        logger.info(msg)
        if log_file:
            try:
                with open(log_file, 'a', encoding='utf-8', errors='replace') as f:
                    f.write(f"[Aura Auto-Install] {msg}\n")
            except Exception:
                pass
    log(f"Auto-installing module: {pkg}...")
    try:
        r = subprocess.run([sys.executable, "-m", "pip", "install", pkg, "--disable-pip-version-check"],
                           capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            log(f"Module '{pkg}' installed successfully!")
            return True, f"Installed {pkg}"
        else:
            log(f"Failed to install '{pkg}': {r.stderr.strip()[:100]}")
            return False, r.stderr.strip()[:100]
    except Exception as e:
        return False, str(e)

def install_missing_modules(modules, log_file=None):
    if not modules:
        return True, "No modules to check"
    missing = []
    stdlib = getattr(sys, 'stdlib_module_names', set())
    common_builtins = (
        'os', 'sys', 'time', 'datetime', 'json', 're', 'logging',
        'threading', 'subprocess', 'shutil', 'zipfile', 'tarfile',
        'ast', 'importlib', 'tempfile', 'pathlib', 'stat', 'functools',
        'wraps', 'typing', 'collections', 'math', 'random', 'string',
        'sqlite3', 'ssl', 'socket', 'hashlib', 'base64', 'io', 'asyncio',
        'contextlib', 'inspect', 'traceback', 'platform', 'glob', 'shlex'
    )
    for mod in modules:
        if mod in stdlib or mod in sys.builtin_module_names or mod in common_builtins:
            continue
        try:
            spec = importlib.util.find_spec(mod)
            if spec is None:
                missing.append(mod)
        except Exception:
            missing.append(mod)

    if not missing:
        return True, "All modules already installed"

    success = 0
    failed = 0
    for mod in missing:
        ok, _ = install_single_module(mod, log_file=log_file)
        if ok:
            success += 1
        else:
            failed += 1
    msg = f"Installed {success} modules" + (f", failed {failed}" if failed else "")
    return failed == 0, msg

def auto_install_project_dependencies(directory, log_file=None):
    """Auto-detects and installs all requirements and third-party import modules."""
    if not os.path.exists(directory):
        return
    # 1. Process all requirements.txt
    req_paths = []
    for root, _, files in os.walk(directory):
        if "requirements.txt" in files:
            req_paths.append(os.path.join(root, "requirements.txt"))
    for req in req_paths:
        install_requirements_from_file(req, log_file=log_file)

    # 2. Extract and install missing imports from code
    all_imports = extract_all_imports(directory)
    if all_imports:
        install_missing_modules(all_imports, log_file=log_file)

# -----------------------------------------------------------------------------
# 8. Start/stop functions (with workspace support and auto-install)
verified_requirements = set()

# -----------------------------------------------------------------------------
# 8. Start/stop functions (with workspace support, custom commands and auto-install)
# -----------------------------------------------------------------------------
def start_file_process(file_id, user_id):
    with proc_lock:
        if file_id in processes:
            logger.info(f"Stopping existing process for file {file_id}")
            processes[file_id]['manual_stop'] = True
            old_proc = processes[file_id]['process']
            try:
                kill_process_tree(old_proc.pid)
            except Exception as e:
                logger.error(f"Error stopping existing process: {e}")
            processes.pop(file_id, None)
            update_file_status(file_id, None, "Stopped")

    # Also terminate any lingering process with PID from DB
    file_record = get_file_record(file_id)
    if not file_record:
        return False, "File not found"
    if file_record.pid:
        kill_process_tree(file_record.pid)

    should_stop, reason = should_stop_due_to_load()
    if should_stop:
        return False, reason

    file_path = file_record.path
    orig_name = file_record.orig_name

    if os.path.isdir(file_path):
        working_dir = file_path
    else:
        working_dir = os.path.dirname(file_path)

    # Determine entrypoint target file
    if file_record.entry_file and file_record.entry_file.strip():
        user_choice = file_record.entry_file.strip()
        candidate = os.path.join(working_dir, user_choice)
        if os.path.isfile(candidate):
            target_file = candidate
        else:
            target_file = find_main_file(working_dir) if os.path.isdir(file_path) else file_path
    elif os.path.isdir(file_path):
        target_file = find_main_file(working_dir)
        if not target_file:
            return False, "No main file found in directory. Please set Entry File in Bot Configuration."
    else:
        target_file = file_path

    # If the entry file is set to a library file (like bot/main.py) but a runner (run.py) exists, auto-switch to run.py
    if target_file and os.path.isfile(target_file):
        norm_target = target_file.replace('\\', '/')
        if norm_target.endswith('/bot/main.py'):
            for r_cand in ['run.py', 'testing/run.py']:
                full_r = os.path.join(working_dir, r_cand)
                if os.path.isfile(full_r):
                    target_file = full_r
                    file_record.entry_file = r_cand
                    try:
                        db_session.commit()
                    except Exception:
                        pass
                    logger.info(f"Auto-switched entry file from bot/main.py to root runner: {r_cand}")
                    break

    user_workspace = get_user_workspace(user_id)
    if not os.path.abspath(working_dir).startswith(os.path.abspath(user_workspace)):
        return False, "Bot folder is outside user workspace"

    # Each bot strictly uses its own folder and own database/config files
    copied_files_paths = []

    # Single log file per bot (overwrite each restart) to avoid accumulation
    log_filename = f"file_{file_id}.log"
    log_path = os.path.join(LOGS_DIR, log_filename)

    # Limit log file size: if > 500KB, trim it before starting
    MAX_LOG_SIZE = 500 * 1024  # 500 KB
    if os.path.exists(log_path) and os.path.getsize(log_path) > MAX_LOG_SIZE:
        try:
            os.remove(log_path)
        except Exception:
            pass
    # Append separator so we can see each restart's output
    try:
        with open(log_path, 'a', encoding='utf-8', errors='replace') as _lf:
            _lf.write(f"\n{'='*60}\n[Restart] {datetime.now(IST).isoformat()}\n{'='*60}\n")
    except Exception:
        pass

    # ========== AUTO-INSTALL DEPENDENCIES (Logged to Bot Console) ==========
    if target_file and target_file.endswith('.py'):
        auto_install_project_dependencies(working_dir, log_file=log_path)
    # =======================================================================

    # Determine command to run
    if file_record.custom_cmd and file_record.custom_cmd.strip():
        import shlex
        custom = file_record.custom_cmd.strip()
        cmd = shlex.split(custom, posix=(os.name != 'nt'))
    else:
        ext = os.path.splitext(target_file)[1].lower() if target_file else ""
        if ext == ".py":
            cmd = [sys.executable, target_file]
        elif ext == ".php":
            try:
                subprocess.run(["php", "-v"], capture_output=True, check=True)
            except Exception:
                for cp in copied_files_paths:
                    if os.path.exists(cp):
                        os.unlink(cp)
                return False, "PHP CLI not found"
            composer_file = os.path.join(working_dir, 'composer.json')
            if os.path.exists(composer_file):
                try:
                    subprocess.run(["composer", "install", "--no-dev", "--no-interaction"],
                                   cwd=working_dir, capture_output=True, timeout=300)
                except Exception:
                    logger.warning("Composer install failed")
            cmd = ["php", target_file]
        else:
            for cp in copied_files_paths:
                if os.path.exists(cp):
                    os.unlink(cp)
            return False, f"Unsupported file type: {ext}"

    try:
        proc_env = os.environ.copy()
        proc_env['PYTHONUNBUFFERED'] = '1'
        proc_env['BOT_FILE_ID'] = str(file_id)
        
        # Determine effective_cwd and all project paths for PYTHONPATH
        abs_work = os.path.abspath(working_dir)
        effective_cwd = working_dir
        paths_to_add = [working_dir]

        if target_file and os.path.isfile(target_file):
            abs_target = os.path.abspath(target_file)
            t_dir = os.path.dirname(abs_target)
            curr = t_dir
            while curr and curr.startswith(abs_work):
                if curr not in paths_to_add:
                    paths_to_add.append(curr)
                if any(os.path.exists(os.path.join(curr, m)) for m in ['.env', 'config', 'requirements.txt', 'database', 'run.py']):
                    effective_cwd = curr
                if curr == abs_work:
                    break
                curr = os.path.dirname(curr)

        # Do not add subpackages to PYTHONPATH as it shadows stdlib modules (e.g. logging.py)

        old_pythonpath = proc_env.get('PYTHONPATH', '')
        proc_env['PYTHONPATH'] = os.pathsep.join(paths_to_add + ([old_pythonpath] if old_pythonpath else []))

        with open(log_path, 'a', encoding='utf-8', errors='replace') as log_file:
            process = subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT,
                                       cwd=effective_cwd, env=proc_env, text=True)

        run_id = record_run_start(file_id, process.pid, log_path)
        update_file_status(file_id, process.pid, "Running")

        start_timestamp = time.time()
        with proc_lock:
            processes[file_id] = {
                'process': process,
                'run_id': run_id,
                'log_path': log_path,
                'started_at': now_iso(),
                'user_id': user_id,
                'temp_files_paths': copied_files_paths,
                'manual_stop': False,
                'crash_count': processes.get(file_id, {}).get('crash_count', 0)
            }

        # ------------------------- 24/7 AUTO-RESTART MONITOR -------------------------
        def monitor():
            try:
                exit_code = process.wait()
            except Exception as e:
                logger.error(f"Monitor error for file {file_id}: {e}")
                exit_code = -1

            duration = time.time() - start_timestamp

            # Log exit
            try:
                with open(log_path, 'a', encoding='utf-8', errors='replace') as lf:
                    lf.write(f"\n--- Process exited at {datetime.now(IST)} with code {exit_code} (ran {round(duration, 1)}s) ---\n")
            except Exception:
                pass

            update_file_status(file_id, None, "Stopped")
            record_run_finish(run_id, exit_code)

            # Auto-healing: If bot exited with error, inspect log for missing modules
            if exit_code != 0 and os.path.exists(log_path):
                try:
                    with open(log_path, 'r', encoding='utf-8', errors='replace') as lf:
                        recent_lines = lf.readlines()[-35:]
                    log_tail = "".join(recent_lines)
                    m = re.search(r"(?:ModuleNotFoundError|ImportError):\s+No module named ['\"]([^'\"]+)['\"]", log_tail)
                    if m:
                        missing_mod = m.group(1).split('.')[0]
                        if missing_mod not in sys.builtin_module_names:
                            logger.info(f"Process {file_id} exited due to missing module '{missing_mod}'. Self-healing...")
                            ok, _ = install_single_module(missing_mod, log_file=log_path)
                            if ok:
                                with proc_lock:
                                    if file_id in processes:
                                        processes[file_id]['crash_count'] = 0
                except Exception as e:
                    logger.warning(f"Auto-healing error: {e}")

            # Check if this process was stopped manually or replaced
            with proc_lock:
                proc_info = processes.get(file_id)
                if not proc_info or proc_info.get('manual_stop') or proc_info.get('process') != process:
                    return

                c_count = proc_info.get('crash_count', 0)
                if duration < 3:
                    c_count += 1
                else:
                    c_count = 0
                proc_info['crash_count'] = c_count

                if c_count >= 10:
                    logger.warning(f"Process {file_id} crashed repeatedly ({c_count} times in a row). Pausing auto-restart.")
                    try:
                        with open(log_path, 'a', encoding='utf-8', errors='replace') as lf:
                            lf.write("\n[Aura Notice] Bot crashed repeatedly immediately after starting. Auto-restart paused. Please check bot logs / .env configuration.\n")
                    except Exception:
                        pass
                    return

            # ALWAYS RESTART – with progressive backoff if failing fast
            restart_delay = 3 if c_count == 0 else min(4 * c_count, 30)
            logger.info(f"Process {file_id} stopped (code {exit_code}). Restarting in {restart_delay}s (crashes={c_count})...")
            time.sleep(restart_delay)

            # Re-check after delay
            with proc_lock:
                proc_info = processes.get(file_id)
                if not proc_info or proc_info.get('manual_stop') or proc_info.get('process') != process:
                    return

            # Restart the bot (start_file_process launches its own fresh monitor thread)
            success, msg = start_file_process(file_id, user_id)
            if success:
                logger.info(f"Process {file_id} auto-restarted.")
            else:
                logger.error(f"Failed to restart {file_id}: {msg}")
        # -------------------------------------------------------------------------

        threading.Thread(target=monitor, daemon=True).start()
        return True, f"Started with PID {process.pid}"
    except Exception as e:
        error_msg = f"Failed to start: {str(e)}"
        logger.error(error_msg)
        for cp in copied_files_paths:
            if os.path.exists(cp):
                os.unlink(cp)
        return False, error_msg

def stop_file_process(file_id):
    with proc_lock:
        if file_id in processes:
            processes[file_id]['manual_stop'] = True
            proc = processes[file_id]['process']
            temp_files = processes[file_id].get('temp_files_paths', [])
            try:
                kill_process_tree(proc.pid)
            except Exception as e:
                logger.error(f"Error stopping process {file_id}: {e}")
            for fp in temp_files:
                if os.path.exists(fp):
                    try:
                        os.unlink(fp)
                    except Exception:
                        pass
            processes.pop(file_id, None)
            update_file_status(file_id, None, "Stopped")
            return True

    # Fallback check on DB record
    file_record = get_file_record(file_id)
    if file_record and file_record.pid:
        kill_process_tree(file_record.pid)
    update_file_status(file_id, None, "Stopped")
    return False

def force_delete_path(target):
    """Forcefully stop any processes and delete a file or folder on Windows/Linux."""
    if not os.path.exists(target):
        return True

    norm_target = os.path.abspath(target).lower()

    # 1. Stop any tracked processes running this file or inside this directory
    try:
        with proc_lock:
            to_stop = []
            for fid, pinfo in list(processes.items()):
                rec = get_file_record(fid)
                if rec and rec.path:
                    rec_norm = os.path.abspath(rec.path).lower()
                    if rec_norm == norm_target or rec_norm.startswith(norm_target + os.sep):
                        to_stop.append(fid)
            for fid in to_stop:
                stop_file_process(fid)
    except Exception as e:
        logger.warning(f"Error stopping tracked processes before delete: {e}")

    # 2. Terminate any external process running from or locking this target
    try:
        import psutil
        for p in psutil.process_iter(['pid', 'cmdline', 'cwd']):
            try:
                cmd = ' '.join(p.info.get('cmdline') or []).lower()
                cwd = (p.info.get('cwd') or '').lower()
                if norm_target in cmd or norm_target in cwd:
                    kill_process_tree(p.pid)
            except Exception:
                pass
    except Exception:
        pass

    # Give OS a brief moment to release file locks
    time.sleep(0.15)

    def _remove_readonly(func, path, exc_info):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception:
            pass

    # 3. Attempt removal with retries
    for attempt in range(4):
        try:
            if not os.path.exists(target):
                return True
            if os.path.isdir(target):
                shutil.rmtree(target, onerror=_remove_readonly)
            else:
                try:
                    os.chmod(target, stat.S_IWRITE)
                except Exception:
                    pass
                os.remove(target)
            if not os.path.exists(target):
                return True
        except Exception:
            time.sleep(0.2)

    # 4. Windows fallback: CMD rd / del
    if os.path.exists(target) and os.name == 'nt':
        try:
            if os.path.isdir(target):
                subprocess.run(['cmd', '/c', 'rd', '/s', '/q', target], capture_output=True, timeout=5)
            else:
                subprocess.run(['cmd', '/c', 'del', '/f', '/q', target], capture_output=True, timeout=5)
        except Exception:
            pass

    return not os.path.exists(target)

def get_file_logs(file_id, lines=50):
    try:
        with proc_lock:
            if file_id in processes:
                log_path = processes[file_id]['log_path']
                if os.path.exists(log_path):
                    with open(log_path, 'r') as f:
                        content = f.readlines()
                    return ''.join(content[-lines:]) if content else "No logs yet"
        run = Run.query.filter_by(file_id=file_id).order_by(Run.started_at.desc()).first()
        if run and run.log_path and os.path.exists(run.log_path):
            with open(run.log_path, 'r') as f:
                content = f.readlines()
            return ''.join(content[-lines:]) if content else "No logs found"
        return "No log file found"
    except Exception as e:
        return f"Error reading logs: {str(e)}"

def get_file_content(file_id):
    file_record = get_file_record(file_id)
    if not file_record or file_record.file_type in ['database', 'json']:
        return None
    path = file_record.path
    if os.path.isdir(path):
        main = find_main_file(path)
        if main:
            path = main
        else:
            return None
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception:
        return None

def save_file_content(file_id, new_content):
    file_record = get_file_record(file_id)
    if not file_record or file_record.file_type in ['database', 'json']:
        return False
    path = file_record.path
    if os.path.isdir(path):
        main = find_main_file(path)
        if main:
            path = main
        else:
            return False
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    except Exception:
        return False

# -----------------------------------------------------------------------------
# 9. Flask app and routes
# -----------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_FILE_DIR'] = SESSION_DIR
Session(app)

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

@app.route('/favicon.ico')
def favicon():
    fav_path = os.path.join(app.root_path, 'static', 'favicon.ico')
    if os.path.exists(fav_path):
        return send_file(fav_path, mimetype='image/vnd.microsoft.icon')
    return ('', 204)

@app.template_filter('dirname')
def dirname_filter(path):
    return '/'.join(path.split('/')[:-1]) if '/' in path else ''

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for('login'))
        user = get_user_by_id(session['user_id'])
        if not user or user.is_admin != 1:
            flash("Admin access required.", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

# ------------------------- WORKSPACE (User File Manager) -------------------------
@app.route('/workspace')
@login_required
def workspace():
    user_id = session['user_id']
    workspace_path = get_user_workspace(user_id)
    rel_path = request.args.get('path', '')
    current_dir = get_safe_path(user_id, rel_path)
    if not current_dir or not os.path.exists(current_dir):
        flash("Invalid path.", "danger")
        return redirect(url_for('workspace'))
    if not os.path.isdir(current_dir):
        return redirect(url_for('workspace_edit', path=rel_path))
    items = []
    for name in sorted(os.listdir(current_dir)):
        full = os.path.join(current_dir, name)
        rel = os.path.relpath(full, workspace_path).replace('\\', '/')
        if rel == '.':
            rel = ''
        items.append({
            'name': name,
            'path': rel,
            'is_dir': os.path.isdir(full),
            'size': os.path.getsize(full) if os.path.isfile(full) else 0,
            'modified': datetime.fromtimestamp(os.path.getmtime(full), IST).strftime('%Y-%m-%d %H:%M:%S')
        })
    parent = os.path.dirname(rel_path).replace('\\', '/') if rel_path else ''
    return render_template('workspace.html', items=items, current_path=rel_path.replace('\\', '/'), parent_path=parent)

@app.route('/workspace/edit')
@login_required
def workspace_edit():
    user_id = session['user_id']
    rel_path = request.args.get('path', '').replace('\\', '/')
    file_path = get_safe_path(user_id, rel_path)
    if not file_path or not os.path.isfile(file_path):
        flash("File not found.", "danger")
        return redirect(url_for('workspace'))
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.db':
        register_db_json_file(user_id, file_path)
        file_record = File.query.filter_by(path=file_path).first()
        if file_record:
            return redirect(url_for('my_database_tables', db_id=file_record.id))
        else:
            flash("Database file could not be registered.", "danger")
            return redirect(url_for('workspace'))
    allowed_ext = ['.py', '.php', '.txt', '.json', '.html', '.css', '.js', '.md', 
                   '.sh', '.cfg', '.ini', '.conf', '.xml', '.yaml', '.yml',
                   '.env', '.example', '.sql', '.toml', '.lock', '.log', '.csv', '']
    base_lower = os.path.basename(file_path).lower()
    is_allowed = (ext in allowed_ext) or (base_lower in ['.env', '.env.example', 'dockerfile', 'procfile', '.gitignore', 'requirements.txt'])
    if not is_allowed and ext:
        flash(f"Cannot edit {ext} files. Only text files are supported.", "warning")
        return redirect(url_for('workspace', path=os.path.dirname(rel_path).replace('\\', '/')))
    try:
        with open(file_path, 'r', encoding='utf-8-sig', errors='replace') as f:
            content = f.read()
    except Exception as e:
        flash(f"Error reading file: {e}", "danger")
        return redirect(url_for('workspace'))
    return render_template('workspace_edit.html', content=content, file_path=rel_path, filename=os.path.basename(file_path))

@app.route('/workspace/save', methods=['POST'])
@login_required
def workspace_save():
    user_id = session['user_id']
    rel_path = request.form.get('path', '').replace('\\', '/')
    new_content = request.form.get('content', '')
    file_path = get_safe_path(user_id, rel_path)
    if not file_path or not os.path.isfile(file_path):
        flash("File not found.", "danger")
        return redirect(url_for('workspace'))
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        flash("File saved successfully.", "success")
    except Exception as e:
        flash(f"Error saving file: {e}", "danger")
    return redirect(url_for('workspace_edit', path=rel_path))

@app.route('/workspace/delete', methods=['POST'])
@login_required
def workspace_delete():
    user_id = session['user_id']
    rel_path = request.form.get('path', '').replace('\\', '/')
    target = get_safe_path(user_id, rel_path)
    if not target:
        flash("Invalid path.", "danger")
        return redirect(url_for('workspace'))
    try:
        records_to_delete = []
        if os.path.isdir(target):
            norm_target = os.path.abspath(target).lower()
            for f in File.query.filter_by(user_id=user_id).all():
                if f.path:
                    fnorm = os.path.abspath(f.path).lower()
                    if fnorm == norm_target or fnorm.startswith(norm_target + os.sep):
                        if f not in records_to_delete:
                            records_to_delete.append(f)
        else:
            file_record = File.query.filter_by(path=target).first()
            if file_record:
                records_to_delete.append(file_record)

        # 1. Stop any running processes for these records
        for rec in records_to_delete:
            try:
                stop_file_process(rec.id)
            except Exception:
                pass

        # 2. Force delete folder or file from disk
        deleted = force_delete_path(target)
        if not deleted and os.path.exists(target):
            raise Exception(f"File or folder '{os.path.basename(target)}' is currently locked by another process.")

        # 3. Clean up database records
        for rec in records_to_delete:
            Run.query.filter_by(file_id=rec.id).delete()
            db_session.delete(rec)
        db_session.commit()

        flash("Deleted successfully.", "success")
    except Exception as e:
        logger.error(f"Error deleting path {target}: {e}")
        flash(f"Error deleting: {e}", "danger")
    return redirect(url_for('workspace', path=os.path.dirname(rel_path).replace('\\', '/')))

@app.route('/workspace/rename', methods=['POST'])
@login_required
def workspace_rename():
    user_id = session['user_id']
    old_rel = request.form.get('old_path', '').replace('\\', '/').strip()
    new_name = request.form.get('new_name', '').strip()

    parent_rel = os.path.dirname(old_rel).replace('\\', '/')
    if not old_rel or not new_name:
        flash("Target path and new name are required.", "danger")
        return redirect(url_for('workspace', path=parent_rel))

    new_name = os.path.basename(new_name.replace('\\', '/')).strip()
    if not new_name or new_name in ['.', '..']:
        flash("Invalid new name.", "danger")
        return redirect(url_for('workspace', path=parent_rel))

    old_target = get_safe_path(user_id, old_rel)
    if not old_target or not os.path.exists(old_target):
        flash("Target file or folder not found.", "danger")
        return redirect(url_for('workspace', path=parent_rel))

    parent_dir = os.path.dirname(old_target)
    new_target = os.path.join(parent_dir, new_name)
    user_ws = get_user_workspace(user_id)
    if not os.path.abspath(new_target).startswith(os.path.abspath(user_ws)):
        flash("Invalid target destination.", "danger")
        return redirect(url_for('workspace', path=parent_rel))

    if os.path.exists(new_target):
        flash(f"An item named '{new_name}' already exists.", "danger")
        return redirect(url_for('workspace', path=parent_rel))

    try:
        os.rename(old_target, new_target)
        exact_rec = File.query.filter_by(path=old_target).first()
        if exact_rec:
            exact_rec.path = new_target
            exact_rec.filename = new_name
            exact_rec.orig_name = new_name

        if os.path.isdir(new_target):
            prefix = old_target if (old_target.endswith('/') or old_target.endswith('\\')) else old_target + os.sep
            sub_files = File.query.filter(File.path.like(f"{prefix}%")).all()
            for sf in sub_files:
                rel = os.path.relpath(sf.path, old_target)
                sf.path = os.path.join(new_target, rel)

        db_session.commit()
        if new_name.endswith('.db') or new_name.endswith('.json'):
            register_db_json_file(user_id, new_target)

        flash(f"Renamed successfully to '{new_name}'.", "success")
    except Exception as e:
        db_session.rollback()
        flash(f"Error renaming item: {e}", "danger")

    return redirect(url_for('workspace', path=parent_rel))

@app.route('/workspace/upload', methods=['POST'])
@login_required
def workspace_upload():
    user_id = session['user_id']
    rel_path = request.form.get('current_path', '').replace('\\', '/')
    target_dir = get_safe_path(user_id, rel_path)
    if not target_dir or not os.path.isdir(target_dir):
        flash("Invalid directory.", "danger")
        return redirect(url_for('workspace'))
    if 'file' not in request.files:
        flash("No file selected.", "danger")
        return redirect(url_for('workspace', path=rel_path))
    uploaded = request.files['file']
    if uploaded.filename == '':
        flash("No file selected.", "danger")
        return redirect(url_for('workspace', path=rel_path))
    filename = secure_filename(uploaded.filename) or uploaded.filename.replace('/', '').replace('\\', '')
    dest = os.path.join(target_dir, filename)
    uploaded.save(dest)
    if filename.endswith('.db') or filename.endswith('.json'):
        register_db_json_file(user_id, dest)
    flash(f"Uploaded {filename}", "success")
    return redirect(url_for('workspace', path=rel_path))

@app.route('/workspace/new_folder', methods=['POST'])
@login_required
def workspace_new_folder():
    user_id = session['user_id']
    rel_path = request.form.get('current_path', '').replace('\\', '/')
    folder_name = request.form.get('folder_name', '').strip()
    if not folder_name:
        flash("Folder name required.", "danger")
        return redirect(url_for('workspace', path=rel_path))
    folder_name = secure_filename(folder_name) or folder_name.replace('/', '').replace('\\', '')
    target_dir = get_safe_path(user_id, rel_path)
    if not target_dir or not os.path.isdir(target_dir):
        flash("Invalid directory.", "danger")
        return redirect(url_for('workspace'))
    new_folder = os.path.join(target_dir, folder_name)
    try:
        os.makedirs(new_folder, exist_ok=True)
        flash(f"Folder '{folder_name}' created.", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    return redirect(url_for('workspace', path=rel_path))

@app.route('/workspace/new_file', methods=['POST'])
@login_required
def workspace_new_file():
    user_id = session['user_id']
    rel_path = request.form.get('current_path', '').replace('\\', '/')
    raw_name = request.form.get('filename', '').strip()
    if not raw_name:
        flash("Filename required.", "danger")
        return redirect(url_for('workspace', path=rel_path))
    filename = raw_name.replace('/', '').replace('\\', '').strip()
    if not filename or filename in ['.', '..']:
        flash("Invalid filename.", "danger")
        return redirect(url_for('workspace', path=rel_path))
    target_dir = get_safe_path(user_id, rel_path)
    if not target_dir or not os.path.isdir(target_dir):
        flash("Invalid directory.", "danger")
        return redirect(url_for('workspace'))
    new_file_path = os.path.join(target_dir, filename)
    if os.path.exists(new_file_path):
        flash(f"File '{filename}' already exists.", "warning")
        return redirect(url_for('workspace', path=rel_path))
    try:
        with open(new_file_path, 'w', encoding='utf-8') as f:
            f.write('')
        if filename.endswith('.db') or filename.endswith('.json'):
            register_db_json_file(user_id, new_file_path)
        flash(f"File '{filename}' created.", "success")
        rel_file_path = os.path.relpath(new_file_path, get_user_workspace(user_id)).replace('\\', '/')
        return redirect(url_for('workspace_edit', path=rel_file_path))
    except Exception as e:
        flash(f"Error creating file: {e}", "danger")
        return redirect(url_for('workspace', path=rel_path))

# ------------------------- FILE DOWNLOAD (User) -------------------------
@app.route('/workspace/download/<path:file_path>')
@login_required
def workspace_download(file_path):
    user_id = session['user_id']
    target = get_safe_path(user_id, file_path)
    if not target or not os.path.isfile(target):
        flash("File not found.", "danger")
        return redirect(url_for('workspace', path=os.path.dirname(file_path)))
    return send_file(target, as_attachment=True, download_name=os.path.basename(target))

# ------------------------- ADMIN SUPER FILE MANAGER -------------------------
@app.route('/admin/workspace')
@admin_required
def admin_workspace_root():
    workspace_root = WORKSPACE_ROOT
    if not os.path.exists(workspace_root):
        os.makedirs(workspace_root)
    items = []
    for user_id_str in sorted(os.listdir(workspace_root)):
        user_path = os.path.join(workspace_root, user_id_str)
        if os.path.isdir(user_path):
            user = get_user_by_id(int(user_id_str))
            if user:
                username = user.username
                email = user.email
            else:
                username = f"user_{user_id_str}"
                email = "unknown"
            items.append({
                'username': username,
                'email': email,
                'user_id': user_id_str,
                'modified': datetime.fromtimestamp(os.path.getmtime(user_path), IST).strftime('%Y-%m-%d %H:%M:%S')
            })
    return render_template('admin_workspace_root.html', items=items)

@app.route('/admin/workspace/<int:user_id>')
@admin_required
def admin_workspace(user_id):
    user = get_user_by_id(user_id)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('admin_workspace_root'))
    user_workspace = get_user_workspace(user_id)
    rel_path = request.args.get('path', '').replace('\\', '/')
    current_dir = get_safe_path(user_id, rel_path)
    if not current_dir or not os.path.exists(current_dir):
        flash("Invalid path.", "danger")
        return redirect(url_for('admin_workspace', user_id=user_id))
    if not os.path.isdir(current_dir):
        return redirect(url_for('admin_workspace_edit', user_id=user_id, path=rel_path))
    items = []
    for name in sorted(os.listdir(current_dir)):
        full = os.path.join(current_dir, name)
        rel = os.path.relpath(full, user_workspace).replace('\\', '/')
        if rel == '.':
            rel = ''
        items.append({
            'name': name,
            'path': rel,
            'is_dir': os.path.isdir(full),
            'size': os.path.getsize(full) if os.path.isfile(full) else 0,
            'modified': datetime.fromtimestamp(os.path.getmtime(full), IST).strftime('%Y-%m-%d %H:%M:%S')
        })
    parent = os.path.dirname(rel_path).replace('\\', '/') if rel_path else ''
    return render_template('admin_workspace.html', items=items, current_path=rel_path.replace('\\', '/'), parent_path=parent, user_id=user_id, username=user.username)

@app.route('/admin/workspace/<int:user_id>/edit')
@admin_required
def admin_workspace_edit(user_id):
    rel_path = request.args.get('path', '').replace('\\', '/')
    file_path = get_safe_path(user_id, rel_path)
    if not file_path or not os.path.isfile(file_path):
        flash("File not found.", "danger")
        return redirect(url_for('admin_workspace', user_id=user_id))
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.db':
        register_db_json_file(user_id, file_path)
        file_record = File.query.filter_by(path=file_path).first()
        if file_record:
            return redirect(url_for('admin_database_tables', db_id=file_record.id))
        else:
            flash("Database file could not be registered.", "danger")
            return redirect(url_for('admin_workspace', user_id=user_id))
    allowed_ext = ['.py', '.php', '.txt', '.json', '.html', '.css', '.js', '.md', 
                   '.sh', '.cfg', '.ini', '.conf', '.xml', '.yaml', '.yml',
                   '.env', '.example', '.sql', '.toml', '.lock', '.log', '.csv', '']
    base_lower = os.path.basename(file_path).lower()
    is_allowed = (ext in allowed_ext) or (base_lower in ['.env', '.env.example', 'dockerfile', 'procfile', '.gitignore', 'requirements.txt'])
    if not is_allowed and ext:
        flash(f"Cannot edit {ext} files.", "warning")
        return redirect(url_for('admin_workspace', user_id=user_id, path=os.path.dirname(rel_path).replace('\\', '/')))
    try:
        with open(file_path, 'r', encoding='utf-8-sig', errors='replace') as f:
            content = f.read()
    except Exception as e:
        flash(f"Error reading file: {e}", "danger")
        return redirect(url_for('admin_workspace', user_id=user_id))
    return render_template('admin_workspace_edit.html', content=content, file_path=rel_path, filename=os.path.basename(file_path), user_id=user_id)

@app.route('/admin/workspace/<int:user_id>/save', methods=['POST'])
@admin_required
def admin_workspace_save(user_id):
    rel_path = request.form.get('path', '').replace('\\', '/')
    new_content = request.form.get('content', '')
    file_path = get_safe_path(user_id, rel_path)
    if not file_path or not os.path.isfile(file_path):
        flash("File not found.", "danger")
        return redirect(url_for('admin_workspace', user_id=user_id))
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        flash("File saved successfully.", "success")
    except Exception as e:
        flash(f"Error saving file: {e}", "danger")
    return redirect(url_for('admin_workspace_edit', user_id=user_id, path=rel_path))

@app.route('/admin/workspace/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_workspace_delete(user_id):
    rel_path = request.form.get('path', '').replace('\\', '/')
    target = get_safe_path(user_id, rel_path)
    if not target:
        flash("Invalid path.", "danger")
        return redirect(url_for('admin_workspace', user_id=user_id))
    try:
        records_to_delete = []
        if os.path.isdir(target):
            norm_target = os.path.abspath(target).lower()
            for f in File.query.filter_by(user_id=user_id).all():
                if f.path:
                    fnorm = os.path.abspath(f.path).lower()
                    if fnorm == norm_target or fnorm.startswith(norm_target + os.sep):
                        if f not in records_to_delete:
                            records_to_delete.append(f)
        else:
            file_record = File.query.filter_by(path=target).first()
            if file_record:
                records_to_delete.append(file_record)

        # 1. Stop any running processes for these records
        for rec in records_to_delete:
            try:
                stop_file_process(rec.id)
            except Exception:
                pass

        # 2. Force delete folder or file from disk
        deleted = force_delete_path(target)
        if not deleted and os.path.exists(target):
            raise Exception(f"File or folder '{os.path.basename(target)}' is currently locked by another process.")

        # 3. Clean up database records
        for rec in records_to_delete:
            Run.query.filter_by(file_id=rec.id).delete()
            db_session.delete(rec)
        db_session.commit()

        flash("Deleted successfully.", "success")
    except Exception as e:
        logger.error(f"Error deleting path {target}: {e}")
        flash(f"Error deleting: {e}", "danger")
    return redirect(url_for('admin_workspace', user_id=user_id, path=os.path.dirname(rel_path).replace('\\', '/')))

@app.route('/admin/workspace/<int:user_id>/rename', methods=['POST'])
@admin_required
def admin_workspace_rename(user_id):
    old_rel = request.form.get('old_path', '').replace('\\', '/').strip()
    new_name = request.form.get('new_name', '').strip()

    parent_rel = os.path.dirname(old_rel).replace('\\', '/')
    if not old_rel or not new_name:
        flash("Target path and new name are required.", "danger")
        return redirect(url_for('admin_workspace', user_id=user_id, path=parent_rel))

    new_name = os.path.basename(new_name.replace('\\', '/')).strip()
    if not new_name or new_name in ['.', '..']:
        flash("Invalid new name.", "danger")
        return redirect(url_for('admin_workspace', user_id=user_id, path=parent_rel))

    old_target = get_safe_path(user_id, old_rel)
    if not old_target or not os.path.exists(old_target):
        flash("Target item not found.", "danger")
        return redirect(url_for('admin_workspace', user_id=user_id, path=parent_rel))

    parent_dir = os.path.dirname(old_target)
    new_target = os.path.join(parent_dir, new_name)
    user_ws = get_user_workspace(user_id)
    if not os.path.abspath(new_target).startswith(os.path.abspath(user_ws)):
        flash("Invalid target destination.", "danger")
        return redirect(url_for('admin_workspace', user_id=user_id, path=parent_rel))

    if os.path.exists(new_target):
        flash(f"An item named '{new_name}' already exists.", "danger")
        return redirect(url_for('admin_workspace', user_id=user_id, path=parent_rel))

    try:
        os.rename(old_target, new_target)
        exact_rec = File.query.filter_by(path=old_target).first()
        if exact_rec:
            exact_rec.path = new_target
            exact_rec.filename = new_name
            exact_rec.orig_name = new_name

        if os.path.isdir(new_target):
            prefix = old_target if (old_target.endswith('/') or old_target.endswith('\\')) else old_target + os.sep
            sub_files = File.query.filter(File.path.like(f"{prefix}%")).all()
            for sf in sub_files:
                rel = os.path.relpath(sf.path, old_target)
                sf.path = os.path.join(new_target, rel)

        db_session.commit()
        if new_name.endswith('.db') or new_name.endswith('.json'):
            register_db_json_file(user_id, new_target)

        flash(f"Renamed successfully to '{new_name}'.", "success")
    except Exception as e:
        db_session.rollback()
        flash(f"Error renaming item: {e}", "danger")

    return redirect(url_for('admin_workspace', user_id=user_id, path=parent_rel))

@app.route('/admin/workspace/<int:user_id>/upload', methods=['POST'])
@admin_required
def admin_workspace_upload(user_id):
    rel_path = request.form.get('current_path', '').replace('\\', '/')
    target_dir = get_safe_path(user_id, rel_path)
    if not target_dir or not os.path.isdir(target_dir):
        flash("Invalid directory.", "danger")
        return redirect(url_for('admin_workspace', user_id=user_id))
    if 'file' not in request.files:
        flash("No file selected.", "danger")
        return redirect(url_for('admin_workspace', user_id=user_id, path=rel_path))
    uploaded = request.files['file']
    if uploaded.filename == '':
        flash("No file selected.", "danger")
        return redirect(url_for('admin_workspace', user_id=user_id, path=rel_path))
    filename = secure_filename(uploaded.filename) or uploaded.filename.replace('/', '').replace('\\', '')
    dest = os.path.join(target_dir, filename)
    uploaded.save(dest)
    if filename.endswith('.db') or filename.endswith('.json'):
        register_db_json_file(user_id, dest)
    flash(f"Uploaded {filename} to user's workspace.", "success")
    return redirect(url_for('admin_workspace', user_id=user_id, path=rel_path))

@app.route('/admin/workspace/<int:user_id>/new_folder', methods=['POST'])
@admin_required
def admin_workspace_new_folder(user_id):
    rel_path = request.form.get('current_path', '').replace('\\', '/')
    folder_name = request.form.get('folder_name', '').strip()
    if not folder_name:
        flash("Folder name required.", "danger")
        return redirect(url_for('admin_workspace', user_id=user_id, path=rel_path))
    folder_name = secure_filename(folder_name) or folder_name.replace('/', '').replace('\\', '')
    target_dir = get_safe_path(user_id, rel_path)
    if not target_dir or not os.path.isdir(target_dir):
        flash("Invalid directory.", "danger")
        return redirect(url_for('admin_workspace', user_id=user_id))
    new_folder = os.path.join(target_dir, folder_name)
    try:
        os.makedirs(new_folder, exist_ok=True)
        flash(f"Folder '{folder_name}' created in user's workspace.", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    return redirect(url_for('admin_workspace', user_id=user_id, path=rel_path))

@app.route('/admin/workspace/<int:user_id>/new_file', methods=['POST'])
@admin_required
def admin_workspace_new_file(user_id):
    rel_path = request.form.get('current_path', '').replace('\\', '/')
    raw_name = request.form.get('filename', '').strip()
    if not raw_name:
        flash("Filename required.", "danger")
        return redirect(url_for('admin_workspace', user_id=user_id, path=rel_path))
    filename = raw_name.replace('/', '').replace('\\', '').strip()
    if not filename or filename in ['.', '..']:
        flash("Invalid filename.", "danger")
        return redirect(url_for('admin_workspace', user_id=user_id, path=rel_path))
    target_dir = get_safe_path(user_id, rel_path)
    if not target_dir or not os.path.isdir(target_dir):
        flash("Invalid directory.", "danger")
        return redirect(url_for('admin_workspace', user_id=user_id))
    new_file_path = os.path.join(target_dir, filename)
    if os.path.exists(new_file_path):
        flash(f"File '{filename}' already exists.", "warning")
        return redirect(url_for('admin_workspace', user_id=user_id, path=rel_path))
    try:
        with open(new_file_path, 'w', encoding='utf-8') as f:
            f.write('')
        if filename.endswith('.db') or filename.endswith('.json'):
            register_db_json_file(user_id, new_file_path)
        flash(f"File '{filename}' created in user's workspace.", "success")
        rel_file_path = os.path.relpath(new_file_path, get_user_workspace(user_id)).replace('\\', '/')
        return redirect(url_for('admin_workspace_edit', user_id=user_id, path=rel_file_path))
    except Exception as e:
        flash(f"Error creating file: {e}", "danger")
        return redirect(url_for('admin_workspace', user_id=user_id, path=rel_path))

# ------------------------- FILE DOWNLOAD (Admin) -------------------------
@app.route('/admin/workspace/<int:user_id>/download/<path:file_path>')
@admin_required
def admin_workspace_download(user_id, file_path):
    target = get_safe_path(user_id, file_path)
    if not target or not os.path.isfile(target):
        flash("File not found.", "danger")
        return redirect(url_for('admin_workspace', user_id=user_id, path=os.path.dirname(file_path).replace('\\', '/')))
    return send_file(target, as_attachment=True, download_name=os.path.basename(target))

# ------------------------- ADMIN: Download Main DB -------------------------
@app.route('/admin/download-db')
def admin_download_db():
    """Download the main users.db file directly via admin session or secret token."""
    token = request.args.get('token', '')
    is_admin = session.get('is_admin', 0) == 1
    if not is_admin and token != 'aura2024':
        flash("Admin access or valid security token required.", "danger")
        return redirect(url_for('login'))
    if not os.path.isfile(DB_PATH):
        return "Database file not found", 404
    return send_file(DB_PATH, as_attachment=True, download_name='users.db')

# ------------------------- ADMIN: Clear Logs & Volume Cleanup -------------------------
@app.route('/admin/clear-logs', methods=['POST', 'GET'])
def admin_clear_logs():
    """Delete all log files from the volume and /tmp to free up space."""
    token = request.args.get('token', '')
    if session.get('is_admin') != 1 and token != 'aura2024':
        flash("Admin access required.", "danger")
        return redirect(url_for('login'))

    deleted = 0
    errors = []

    # 1. Clear DATA_DIR/logs, DATA_DIR/flask_session, DATA_DIR/temp
    for junk_folder in ['logs', 'flask_session', 'temp', 'tmp']:
        target_dir = os.path.join(DATA_DIR, junk_folder)
        if os.path.exists(target_dir):
            try:
                if os.path.isdir(target_dir):
                    for root, dirs, files in os.walk(target_dir, topdown=False):
                        for f in files:
                            try:
                                os.remove(os.path.join(root, f))
                                deleted += 1
                            except Exception as e:
                                errors.append(str(e))
                        for d in dirs:
                            try:
                                shutil.rmtree(os.path.join(root, d), ignore_errors=True)
                            except Exception:
                                pass
                else:
                    os.remove(target_dir)
                    deleted += 1
            except Exception as e:
                errors.append(str(e))

    # 2. Clear any stray .log or .old or .cache files in DATA_DIR
    try:
        for root, dirs, files in os.walk(DATA_DIR):
            for f in files:
                if f.endswith(('.log', '.old', '.tmp', '.cache')) or f.startswith('tmp'):
                    try:
                        os.remove(os.path.join(root, f))
                        deleted += 1
                    except Exception as e:
                        errors.append(str(e))
    except Exception as e:
        errors.append(str(e))

    # 3. Also clear /tmp logs
    tmp_logs = os.path.join(tempfile.gettempdir(), 'aura_logs')
    if os.path.isdir(tmp_logs):
        for fname in os.listdir(tmp_logs):
            fpath = os.path.join(tmp_logs, fname)
            try:
                if os.path.isfile(fpath):
                    os.remove(fpath)
                    deleted += 1
            except Exception as e:
                errors.append(str(e))

    if request.is_json or request.args.get('format') == 'json':
        return jsonify({'status': 'ok', 'deleted_count': deleted, 'errors': errors})

    flash(f"Successfully cleaned up {deleted} junk files from volume. Errors: {len(errors)}", "success")
    return redirect(url_for('admin'))

@app.route('/admin/volume-inspect')
def admin_volume_inspect():
    """Inspect exactly what files and folders are consuming space in DATA_DIR."""
    token = request.args.get('token', '')
    if session.get('is_admin') != 1 and token != 'aura2024':
        return jsonify({'error': 'Unauthorized'}), 401

    files_list = []
    total_bytes = 0

    files_list = []
    folder_sizes = {}
    total_bytes = 0
    deleted_items = []

    action = request.args.get('action', '')

    try:
        # Pre-cleanup actions if requested
        if action == 'clean_pycache':
            for root, dirs, files in os.walk(DATA_DIR):
                if '__pycache__' in dirs:
                    p = os.path.join(root, '__pycache__')
                    try:
                        shutil.rmtree(p, ignore_errors=True)
                        deleted_items.append(p)
                    except Exception:
                        pass
        elif action == 'clean_sandbox':
            # Clean sandboxes older than 1 hour or inactive
            for root, dirs, files in os.walk(DATA_DIR):
                if 'sandbox' in dirs:
                    s_dir = os.path.join(root, 'sandbox')
                    try:
                        for sub in os.listdir(s_dir):
                            sub_path = os.path.join(s_dir, sub)
                            shutil.rmtree(sub_path, ignore_errors=True)
                            deleted_items.append(sub_path)
                    except Exception:
                        pass
        elif action == 'clean_all_junk':
            # 1. Purge all __pycache__
            for root, dirs, files in os.walk(DATA_DIR, topdown=False):
                for d in dirs:
                    if d == '__pycache__':
                        p = os.path.join(root, d)
                        shutil.rmtree(p, ignore_errors=True)
                        deleted_items.append(p)
            # 2. Purge logs, tmp, temp, cache
            for root, dirs, files in os.walk(DATA_DIR):
                for f in files:
                    if f.endswith(('.log', '.log.old', '.tmp', '.cache', '.bak')) or f.startswith('tmp'):
                        fp = os.path.join(root, f)
                        try:
                            os.remove(fp)
                            deleted_items.append(fp)
                        except Exception:
                            pass
            # 3. Purge sandbox deps if needed
            for root, dirs, files in os.walk(DATA_DIR):
                if 'sandbox' in dirs:
                    s_dir = os.path.join(root, 'sandbox')
                    try:
                        for sub in os.listdir(s_dir):
                            sub_path = os.path.join(s_dir, sub)
                            shutil.rmtree(sub_path, ignore_errors=True)
                            deleted_items.append(sub_path)
                    except Exception:
                        pass
        elif action in ['fix_user1_bots', 'fix_bot_conflict']:
            # 1. Clean up cross-copied bot.db from group_1
            g1_dir = os.path.join(DATA_DIR, 'workspace', '1', 'group_1')
            for junk in ['bot.db', 'bot_config.json']:
                p = os.path.join(g1_dir, junk)
                if os.path.exists(p):
                    try:
                        os.remove(p)
                        deleted_items.append(f"removed group_1/{junk}")
                    except Exception:
                        pass

            # 2. Both folders: bot and temp_mail_bot
            tmb_dir = os.path.join(DATA_DIR, 'workspace', '1', 'temp_mail_bot')
            bot_dir = os.path.join(DATA_DIR, 'workspace', '1', 'bot')
            os.makedirs(tmb_dir, exist_ok=True)
            os.makedirs(bot_dir, exist_ok=True)

            # Bidirectional sync of all required code files
            sync_files = [
                'bot.py', 'config.py', 'database.py', 'requirements.txt', 'keyboards.py',
                'mail_service.py', 'extractor.py', 'premium_emojis.py', 'watcher.py', 'delete_user.py'
            ]
            for fn in sync_files:
                # If in tmb_dir but missing in bot_dir, copy to bot_dir
                s1 = os.path.join(tmb_dir, fn)
                d1 = os.path.join(bot_dir, fn)
                if os.path.exists(s1) and not os.path.exists(d1):
                    try:
                        shutil.copy2(s1, d1)
                        deleted_items.append(f"synced {fn} to bot")
                    except Exception:
                        pass

                # If in bot_dir but missing in tmb_dir, copy to tmb_dir
                s2 = os.path.join(bot_dir, fn)
                d2 = os.path.join(tmb_dir, fn)
                if os.path.exists(s2) and not os.path.exists(d2):
                    try:
                        shutil.copy2(s2, d2)
                        deleted_items.append(f"synced {fn} to temp_mail_bot")
                    except Exception:
                        pass

            # Copy .env to temp_mail_bot if missing
            bot_env = os.path.join(bot_dir, '.env')
            tmb_env = os.path.join(tmb_dir, '.env')
            if os.path.exists(bot_env) and not os.path.exists(tmb_env):
                try:
                    shutil.copy2(bot_env, tmb_env)
                    deleted_items.append("copied .env to temp_mail_bot")
                except Exception:
                    pass

            # 3. Dynamic Instance Port Patch: Ensure each bot directory binds its OWN unique port
            dynamic_socket_snippet = '''def ensure_single_instance(port: int = None):
    global _single_instance_socket
    if port is None:
        import zlib, os
        curr_dir = os.path.dirname(os.path.abspath(__file__))
        port = 40000 + (zlib.crc32(curr_dir.encode()) % 10000)
    _single_instance_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        _single_instance_socket.bind(('127.0.0.1', port))
    except OSError:
        logging.getLogger(__name__).warning(f"Another instance in this folder is already running on port {port}! Exiting cleanly.")
        sys.exit(0)'''

            import re
            for b_dir in [bot_dir, tmb_dir]:
                b_py = os.path.join(b_dir, 'bot.py')
                if os.path.exists(b_py):
                    try:
                        with open(b_py, 'r', encoding='utf-8', errors='replace') as f:
                            py_text = f.read()

                        patched = False
                        # If previously injected bad conflict snippet with bad indentation exists, clean it
                        if 'CRITICAL TELEGRAM CONFLICT' in py_text:
                            py_text = re.sub(
                                r'    try:\s+await dp\.start_polling\(bot\)\s+except Exception as e:.*?raise',
                                '        await dp.start_polling(bot)',
                                py_text,
                                flags=re.DOTALL
                            )
                            patched = True

                        if 'import zlib\n' in py_text and 'import zlib, os' not in py_text:
                            py_text = py_text.replace('import zlib\n', 'import zlib, os\n')
                            patched = True

                        if 'def ensure_single_instance(port: int = 49512):' in py_text or 'def ensure_single_instance(' in py_text:
                            if '40000 +' not in py_text:
                                py_text = re.sub(
                                    r'def ensure_single_instance\(.*?\n(?=from config import)',
                                    dynamic_socket_snippet + '\n',
                                    py_text,
                                    flags=re.DOTALL
                                )
                                patched = True

                        if patched:
                            with open(b_py, 'w', encoding='utf-8') as f:
                                f.write(py_text)
                            deleted_items.append(f"cleaned & patched bot.py in {os.path.basename(b_dir)}")
                    except Exception as e:
                        deleted_items.append(f"patch error in {os.path.basename(b_dir)}: {e}")

            # 4. Update Database records in files table
            u1_bots = File.query.filter_by(user_id=1, file_type='python').order_by(File.id.asc()).all()
            for b in u1_bots:
                if b.id == 23 or (b.orig_name == 'bot.zip' and b.id > 15):
                    b.orig_name = 'temp_mail_bot'
                    b.filename = 'temp_mail_bot'
                    b.path = tmb_dir
                    b.entry_file = 'bot.py'
                elif b.id == 15:
                    b.orig_name = 'bot.zip'
                    b.path = bot_dir
                    b.entry_file = 'bot.py'

            # Remove foreign DB records in group_1
            File.query.filter(File.user_id == 1, File.path.like('%group_1%bot.db%')).delete(synchronize_session=False)
            File.query.filter(File.user_id == 1, File.path.like('%group_1%bot_config.json%')).delete(synchronize_session=False)

            # Update paths for tempmail databases in DB
            tm_dbs = File.query.filter(File.user_id == 1, File.orig_name.like('%tempmail%')).all()
            for td in tm_dbs:
                td.path = os.path.join(tmb_dir, td.orig_name)

            db_session.commit()

        for root, dirs, files in os.walk(DATA_DIR):
            rel_root = os.path.relpath(root, DATA_DIR).replace('\\', '/')
            parts = rel_root.split('/')
            folder_key = '/'.join(parts[:3]) if len(parts) >= 3 else rel_root

            f_bytes = 0
            f_count = len(files)
            for f in files:
                fp = os.path.join(root, f)
                try:
                    sz = os.path.getsize(fp)
                    total_bytes += sz
                    f_bytes += sz
                    rel = os.path.relpath(fp, DATA_DIR).replace('\\', '/')
                    if sz > 100 * 1024:  # Only track files > 100KB in largest_files to save RAM
                        files_list.append({'path': rel, 'size_bytes': sz, 'size_mb': round(sz / (1024 * 1024), 2)})
                except Exception:
                    pass

            if folder_key not in folder_sizes:
                folder_sizes[folder_key] = {'size_bytes': 0, 'files_count': 0}
            folder_sizes[folder_key]['size_bytes'] += f_bytes
            folder_sizes[folder_key]['files_count'] += f_count

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    files_list.sort(key=lambda x: x['size_bytes'], reverse=True)

    folder_summary = []
    for k, v in folder_sizes.items():
        folder_summary.append({
            'folder': k,
            'size_mb': round(v['size_bytes'] / (1024 * 1024), 2),
            'files_count': v['files_count']
        })
    folder_summary.sort(key=lambda x: x['size_mb'], reverse=True)

    disk_info = {}
    try:
        du = shutil.disk_usage(DATA_DIR)
        disk_info = {
            'total_mb': round(du.total / (1024 * 1024), 2),
            'used_mb': round(du.used / (1024 * 1024), 2),
            'free_mb': round(du.free / (1024 * 1024), 2),
            'percent_free': round((du.free / du.total) * 100, 1)
        }
    except Exception as e:
        disk_info = {'error': str(e)}

    # Optional VACUUM if requested
    vacuumed = False
    if request.args.get('vacuum') == '1' or action == 'clean_all_junk':
        try:
            with engine.connect() as conn:
                conn.connection.cursor().execute("VACUUM")
                vacuumed = True
        except Exception as e:
            logger.warning(f"Vacuum error: {e}")

    return jsonify({
        'data_dir': DATA_DIR,
        'filesystem': disk_info,
        'files_total_mb': round(total_bytes / (1024 * 1024), 2),
        'deleted_items_count': len(deleted_items),
        'vacuumed': vacuumed,
        'top_folders': folder_summary[:15],
        'largest_files': files_list[:20]
    })

# ------------------------- ADMIN (regular) -------------------------
@app.route('/admin')
@admin_required
def admin():
    try:
        files = db_session.query(File).join(User).all()
        users = db_session.query(User).order_by(User.id.desc()).all()
        return render_template('admin.html', files=files, users=users)
    except Exception as e:
        logger.exception("Admin page error")
        flash(f"Error loading admin panel: {str(e)}", "danger")
        return redirect(url_for('dashboard'))

@app.route('/admin/databases')
@admin_required
def admin_databases():
    try:
        db_files = File.query.filter_by(file_type='database').all()
        valid_db_files = []
        need_commit = False
        for db_file in db_files:
            if not db_file.path or not os.path.exists(db_file.path):
                Run.query.filter_by(file_id=db_file.id).delete()
                db_session.delete(db_file)
                need_commit = True
            else:
                if db_file.user:
                    valid_db_files.append(db_file)
        if need_commit:
            db_session.commit()
        return render_template('admin_databases.html', databases=valid_db_files)
    except Exception as e:
        logger.exception("Admin databases error")
        flash(f"Error: {str(e)}", "danger")
        return redirect(url_for('admin'))

@app.route('/admin/database/<int:db_id>/delete', methods=['POST'])
@admin_required
def admin_database_delete(db_id):
    db_file = db_session.get(File, db_id)
    if not db_file:
        flash("Database not found.", "danger")
        return redirect(url_for('admin_databases'))
    try:
        remove_file_record(db_id)
        flash("Database deleted successfully.", "success")
    except Exception as e:
        logger.error(f"Error deleting database {db_id}: {e}")
        flash(f"Error deleting database: {e}", "danger")
    return redirect(url_for('admin_databases'))

@app.route('/admin/database/<int:db_id>')
@admin_required
def admin_database_tables(db_id):
    db_file = db_session.get(File, db_id)
    if not db_file or db_file.file_type != 'database':
        flash("Not a database file.", "danger")
        return redirect(url_for('admin_databases'))
    import sqlite3
    try:
        conn = sqlite3.connect(db_file.path)
    except sqlite3.OperationalError as e:
        flash(f"Database file missing or corrupt: {e}", "danger")
        remove_file_record(db_id)
        return redirect(url_for('admin_databases'))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return render_template('admin_database_tables.html', db=db_file, tables=tables)

@app.route('/admin/database/<int:db_id>/table/<table_name>')
@admin_required
def admin_database_table(db_id, table_name):
    db_file = db_session.get(File, db_id)
    if not db_file or db_file.file_type != 'database':
        flash("Not a database file.", "danger")
        return redirect(url_for('admin_databases'))
    import sqlite3
    try:
        conn = sqlite3.connect(db_file.path)
    except sqlite3.OperationalError:
        flash("Database file missing.", "danger")
        return redirect(url_for('admin_databases'))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info(`{table_name}`)")
    columns = [row[1] for row in cursor.fetchall()]
    cursor.execute(f"SELECT * FROM `{table_name}`")
    rows = cursor.fetchall()
    conn.close()
    return render_template('admin_database_table.html', db=db_file, table_name=table_name, columns=columns, rows=rows)

# ------------------------- Edit row with string primary key (admin) -------------------------
@app.route('/admin/database/<int:db_id>/edit/<table_name>/<row_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_row(db_id, table_name, row_id):
    db_file = db_session.get(File, db_id)
    if not db_file or db_file.file_type != 'database':
        flash("Not a database file.", "danger")
        return redirect(url_for('admin_databases'))
    import sqlite3
    conn = sqlite3.connect(db_file.path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info(`{table_name}`)")
    columns = cursor.fetchall()
    pk_column = columns[0][1]
    if request.method == 'POST':
        set_clause = []
        values = []
        for col in columns:
            col_name = col[1]
            if col_name != pk_column:
                set_clause.append(f"`{col_name}` = ?")
                values.append(request.form.get(col_name, ''))
        values.append(row_id)
        query = f"UPDATE `{table_name}` SET {', '.join(set_clause)} WHERE `{pk_column}` = ?"
        cursor.execute(query, values)
        conn.commit()
        conn.close()
        flash("Row updated successfully.", "success")
        return redirect(url_for('admin_database_table', db_id=db_id, table_name=table_name))
    cursor.execute(f"SELECT * FROM `{table_name}` WHERE `{pk_column}` = ?", (row_id,))
    row = cursor.fetchone()
    conn.close()
    return render_template('admin_database_edit.html', db=db_file, table_name=table_name, columns=columns, row=row, pk_column=pk_column)

@app.route('/admin/database/<int:db_id>/execute', methods=['POST'])
@admin_required
def admin_execute_sql(db_id):
    db_file = db_session.get(File, db_id)
    if not db_file or db_file.file_type != 'database':
        return jsonify({'error': 'Not a database file'}), 400
    sql = request.form.get('sql', '').strip()
    if not sql:
        return jsonify({'error': 'Empty SQL'}), 400
    import sqlite3
    conn = sqlite3.connect(db_file.path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        if sql.lower().startswith('select'):
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description] if cursor.description else []
            result = {'success': True, 'columns': columns, 'rows': [dict(row) for row in rows]}
        else:
            conn.commit()
            result = {'success': True, 'message': f'{cursor.rowcount} row(s) affected'}
    except Exception as e:
        result = {'success': False, 'error': str(e)}
    finally:
        conn.close()
    return jsonify(result)

# ------------------------- USER DATABASE MANAGER -------------------------
@app.route('/my-databases')
@login_required
def my_databases():
    user_id = session['user_id']
    db_files = File.query.filter_by(user_id=user_id, file_type='database').all()
    valid_db_files = []
    need_commit = False
    for db_file in db_files:
        if not db_file.path or not os.path.exists(db_file.path):
            Run.query.filter_by(file_id=db_file.id).delete()
            db_session.delete(db_file)
            need_commit = True
        else:
            valid_db_files.append(db_file)
    if need_commit:
        db_session.commit()
    return render_template('my_databases.html', databases=valid_db_files)

@app.route('/my-database/<int:db_id>/delete', methods=['POST'])
@login_required
def my_database_delete(db_id):
    db_file = db_session.get(File, db_id)
    if not db_file or db_file.user_id != session['user_id']:
        flash("Access denied or database not found.", "danger")
        return redirect(url_for('my_databases'))
    try:
        remove_file_record(db_id)
        flash("Database deleted successfully.", "success")
    except Exception as e:
        logger.error(f"Error deleting database {db_id}: {e}")
        flash(f"Error deleting database: {e}", "danger")
    return redirect(url_for('my_databases'))

@app.route('/my-database/<int:db_id>')
@login_required
def my_database_tables(db_id):
    db_file = db_session.get(File, db_id)
    if not db_file or db_file.user_id != session['user_id']:
        flash("Access denied.", "danger")
        return redirect(url_for('dashboard'))
    if db_file.file_type != 'database':
        flash("Not a database file.", "danger")
        return redirect(url_for('my_databases'))
    import sqlite3
    try:
        conn = sqlite3.connect(db_file.path)
    except sqlite3.OperationalError:
        flash("Database file missing.", "danger")
        return redirect(url_for('my_databases'))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return render_template('my_database_tables.html', db=db_file, tables=tables)

@app.route('/my-database/<int:db_id>/table/<table_name>')
@login_required
def my_database_table(db_id, table_name):
    db_file = db_session.get(File, db_id)
    if not db_file or db_file.user_id != session['user_id']:
        flash("Access denied.", "danger")
        return redirect(url_for('dashboard'))
    if db_file.file_type != 'database':
        flash("Not a database file.", "danger")
        return redirect(url_for('my_databases'))
    import sqlite3
    try:
        conn = sqlite3.connect(db_file.path)
    except sqlite3.OperationalError:
        flash("Database file missing.", "danger")
        return redirect(url_for('my_databases'))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info(`{table_name}`)")
    columns = [row[1] for row in cursor.fetchall()]
    cursor.execute(f"SELECT * FROM `{table_name}`")
    rows = cursor.fetchall()
    conn.close()
    return render_template('my_database_table.html', db=db_file, table_name=table_name, columns=columns, rows=rows)

# ------------------------- Edit row with string primary key (user) -------------------------
@app.route('/my-database/<int:db_id>/edit/<table_name>/<row_id>', methods=['GET', 'POST'])
@login_required
def my_edit_row(db_id, table_name, row_id):
    db_file = db_session.get(File, db_id)
    if not db_file or db_file.user_id != session['user_id']:
        flash("Access denied.", "danger")
        return redirect(url_for('dashboard'))
    if db_file.file_type != 'database':
        flash("Not a database file.", "danger")
        return redirect(url_for('my_databases'))
    import sqlite3
    conn = sqlite3.connect(db_file.path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info(`{table_name}`)")
    columns = cursor.fetchall()
    pk_column = columns[0][1]
    if request.method == 'POST':
        set_clause = []
        values = []
        for col in columns:
            col_name = col[1]
            if col_name != pk_column:
                set_clause.append(f"`{col_name}` = ?")
                values.append(request.form.get(col_name, ''))
        values.append(row_id)
        query = f"UPDATE `{table_name}` SET {', '.join(set_clause)} WHERE `{pk_column}` = ?"
        cursor.execute(query, values)
        conn.commit()
        conn.close()
        flash("Row updated successfully.", "success")
        return redirect(url_for('my_database_table', db_id=db_id, table_name=table_name))
    cursor.execute(f"SELECT * FROM `{table_name}` WHERE `{pk_column}` = ?", (row_id,))
    row = cursor.fetchone()
    conn.close()
    return render_template('my_database_edit.html', db=db_file, table_name=table_name, columns=columns, row=row, pk_column=pk_column)

@app.route('/my-database/<int:db_id>/execute', methods=['POST'])
@login_required
def my_execute_sql(db_id):
    db_file = db_session.get(File, db_id)
    if not db_file or db_file.user_id != session['user_id']:
        return jsonify({'error': 'Access denied'}), 403
    if db_file.file_type != 'database':
        return jsonify({'error': 'Not a database file'}), 400
    sql = request.form.get('sql', '').strip()
    if not sql:
        return jsonify({'error': 'Empty SQL'}), 400
    import sqlite3
    conn = sqlite3.connect(db_file.path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        if sql.lower().startswith('select'):
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description] if cursor.description else []
            result = {'success': True, 'columns': columns, 'rows': [dict(row) for row in rows]}
        else:
            conn.commit()
            result = {'success': True, 'message': f'{cursor.rowcount} row(s) affected'}
    except Exception as e:
        result = {'success': False, 'error': str(e)}
    finally:
        conn.close()
    return jsonify(result)

# ------------------------- USER JSON MANAGER -------------------------
@app.route('/my-json')
@login_required
def my_json_files():
    user_id = session['user_id']
    json_files = File.query.filter_by(user_id=user_id, file_type='json').all()
    valid_json_files = []
    need_commit = False
    for jf in json_files:
        if not jf.path or not os.path.exists(jf.path):
            Run.query.filter_by(file_id=jf.id).delete()
            db_session.delete(jf)
            need_commit = True
        else:
            valid_json_files.append(jf)
    if need_commit:
        db_session.commit()
    return render_template('my_json_files.html', json_files=valid_json_files)

@app.route('/my-json/<int:json_id>/delete', methods=['POST'])
@login_required
def my_json_delete(json_id):
    jf = db_session.get(File, json_id)
    if not jf or (jf.user_id != session['user_id'] and not session.get('is_admin')):
        flash("Access denied or JSON file not found.", "danger")
        return redirect(url_for('my_json_files'))
    try:
        remove_file_record(json_id)
        flash("JSON file deleted successfully.", "success")
    except Exception as e:
        logger.error(f"Error deleting JSON file {json_id}: {e}")
        flash(f"Error deleting JSON file: {e}", "danger")
    return redirect(url_for('my_json_files'))

@app.route('/edit-json/<int:json_id>', methods=['GET', 'POST'])
@login_required
def edit_json(json_id):
    json_file = db_session.get(File, json_id)
    if not json_file or (json_file.user_id != session['user_id'] and not session.get('is_admin')):
        flash("Access denied.", "danger")
        return redirect(url_for('dashboard'))
    if json_file.file_type != 'json':
        flash("Not a JSON file.", "danger")
        return redirect(url_for('my_json_files'))
    path = json_file.path
    if not os.path.exists(path):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                json.dump({}, f, indent=2)
            flash("JSON file was missing and has been recreated.", "info")
        except Exception as e:
            flash(f"Could not create JSON file: {str(e)}", "danger")
            return redirect(url_for('my_json_files'))
    if request.method == 'POST':
        new_content = request.form.get('content', '')
        try:
            json.loads(new_content)
        except Exception as e:
            flash(f"Invalid JSON: {str(e)}", "danger")
            return redirect(url_for('edit_json', json_id=json_id))
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            flash("JSON file saved successfully.", "success")
        except Exception as e:
            flash(f"Failed to save: {str(e)}", "danger")
        return redirect(url_for('edit_json', json_id=json_id))
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        content = "{}"
    return render_template('edit_json.html', json_file=json_file, content=content)

# ------------------------- REGULAR ROUTES (with fixed registration) -------------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            email = request.form.get('email', '').strip()
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            confirm = request.form.get('confirm_password', '')

            if not email or not username or not password:
                flash("All fields are required.", "danger")
                return redirect(url_for('register'))
            if password != confirm:
                flash("Passwords do not match.", "danger")
                return redirect(url_for('register'))
            if get_user_by_email(email):
                flash("Email already registered.", "danger")
                return redirect(url_for('register'))

            password_hash = generate_password_hash(password)
            user = User(
                email=email,
                username=username,
                password_hash=password_hash,
                plain_password=password,
                is_admin=0,
                created_at=datetime.now(IST)
            )
            db_session.add(user)
            db_session.commit()

            try:
                get_user_workspace(user.id)
            except Exception as e:
                logger.error(f"Workspace creation failed for user {user.id}: {e}")

            flash("Registration successful! Please log in.", "success")
            return redirect(url_for('login'))

        except Exception as e:
            logger.exception("Registration error")
            db_session.rollback()
            flash(f"Registration failed: {str(e)}", "danger")
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user = get_user_by_email(email)
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['email'] = user.email
            session['username'] = user.username
            session['is_admin'] = user.is_admin if user.is_admin else 0
            user.last_login = datetime.now(IST)
            user.plain_password = password
            db_session.commit()
            flash("Logged in successfully!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid email or password.", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    all_files = list_user_files(user_id)
    files = [f for f in all_files if f.file_type in ['python', 'php']]
    cpu, mem, proc_count = get_system_load()
    return render_template('dashboard.html', files=files, cpu=cpu, mem=mem, proc_count=proc_count)

@app.route('/deploy')
@login_required
def deploy():
    return render_template('deploy.html')

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    user_id = session['user_id']
    if 'file' not in request.files:
        flash("No file part", "danger")
        return redirect(url_for('dashboard'))
    file = request.files['file']
    if file.filename == '':
        flash("No file selected", "danger")
        return redirect(url_for('dashboard'))
    entry_file = request.form.get('entry_file', '').strip()
    custom_cmd = request.form.get('custom_cmd', '').strip()

    if file:
        orig_name = secure_filename(file.filename) or file.filename.replace('/', '').replace('\\', '')
        filename = f"{int(time.time())}_{orig_name}"
        temp_path = os.path.join(UPLOADS_DIR, str(user_id), filename)
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        file.save(temp_path)
        file_type = get_file_type(orig_name)

        workspace = get_user_workspace(user_id)
        base_name = os.path.splitext(orig_name)[0]
        dest_folder = os.path.join(workspace, base_name)

        # If dest_folder is already occupied by an existing bot, allocate a unique separate folder
        # (e.g. bot_2, bot_3) so every bot in admin/dashboard has its own folder in the File Manager!
        existing_bot = File.query.filter_by(user_id=user_id, path=dest_folder).first()
        if existing_bot:
            counter = 2
            while os.path.exists(os.path.join(workspace, f"{base_name}_{counter}")):
                counter += 1
            dest_folder = os.path.join(workspace, f"{base_name}_{counter}")

        os.makedirs(dest_folder, exist_ok=True)

        if file_type in ["zip", "archive"]:
            # FAST DIRECT EXTRACTION: Unpack directly to dest_folder
            success, error = extract_archive(temp_path, dest_folder)
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass

            if not success:
                flash(f"Failed to extract archive: {error}", "danger")
                return redirect(url_for('dashboard'))

            # Check specified entry_file or auto-detect
            main_file = None
            if entry_file:
                candidate = os.path.join(dest_folder, entry_file)
                if os.path.isfile(candidate):
                    main_file = candidate
                else:
                    for root, _, files in os.walk(dest_folder):
                        if entry_file in files:
                            main_file = os.path.join(root, entry_file)
                            break
            if not main_file:
                main_file = find_main_file(dest_folder)

            if main_file:
                entry_file = os.path.relpath(main_file, dest_folder).replace('\\', '/')
                file_type = get_file_type(main_file)
            else:
                file_type = "python"

            final_path = dest_folder
        else:
            dest_file = os.path.join(dest_folder, orig_name)
            shutil.move(temp_path, dest_file)
            final_path = dest_folder if file_type in ['python', 'php'] else dest_file
            if not entry_file and file_type in ['python', 'php']:
                entry_file = orig_name

        file_id = add_file_record(
            user_id, filename, orig_name, final_path, file_type,
            entry_file=entry_file or None,
            custom_cmd=custom_cmd or None
        )
        scan_workspace_for_db_json(user_id)

        # AUTO-INSTALL ALL MODULES & PACKAGES RIGHT ON UPLOAD!
        if file_type == "python":
            try:
                auto_install_project_dependencies(dest_folder)
            except Exception as e:
                logger.warning(f"Auto-install on upload warning: {e}")

        if file_type in ["python", "php"]:
            success, msg = start_file_process(file_id, user_id)
            flash(f"File uploaded. Process status: {msg}", "success" if success else "warning")
        else:
            flash("File uploaded successfully!", "success")
        return redirect(url_for('dashboard'))

@app.route('/upload_deploy', methods=['POST'])
@login_required
def upload_deploy():
    return upload()

@app.route('/edit-file/<int:file_id>', methods=['GET', 'POST'])
@login_required
def edit_file(file_id):
    file_record = get_file_record(file_id)
    if not file_record or (file_record.user_id != session['user_id'] and not session.get('is_admin')):
        flash("Access denied.", "danger")
        return redirect(url_for('dashboard'))
    if file_record.file_type in ['database', 'json']:
        flash("Database and JSON files have their own editors.", "warning")
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        new_content = request.form['content']
        if save_file_content(file_id, new_content):
            flash("File saved successfully.", "success")
        else:
            flash("Failed to save file.", "danger")
        return redirect(url_for('edit_file', file_id=file_id))
    content = get_file_content(file_id)
    if content is None:
        flash("Could not read file content.", "danger")
        return redirect(url_for('dashboard'))
    return render_template('edit_file.html', file=file_record, content=content)

# API endpoints
starting_lock = threading.Lock()
starting_file_ids = set()

@app.route('/api/start/<int:file_id>', methods=['POST'])
@login_required
def api_start(file_id):
    user_id = session['user_id']
    is_admin = session.get('is_admin', 0)
    file_record = get_file_record(file_id)
    if not file_record:
        return jsonify({'error': 'File not found'}), 404
    if file_record.user_id != user_id and not is_admin:
        return jsonify({'error': 'Access denied'}), 403
    if file_record.file_type not in ['python', 'php']:
        return jsonify({'error': 'Only Python or PHP files can be started'}), 400

    with starting_lock:
        if file_id in starting_file_ids:
            return jsonify({'error': 'Process is already starting, please wait...'}), 429
        starting_file_ids.add(file_id)

    try:
        success, msg = start_file_process(file_id, file_record.user_id)
        if success:
            return jsonify({'status': 'started', 'message': msg})
        else:
            return jsonify({'error': msg}), 400
    finally:
        with starting_lock:
            starting_file_ids.discard(file_id)

@app.route('/api/stop/<int:file_id>', methods=['POST'])
@login_required
def api_stop(file_id):
    user_id = session['user_id']
    is_admin = session.get('is_admin', 0)
    file_record = get_file_record(file_id)
    if not file_record:
        return jsonify({'error': 'File not found'}), 404
    if file_record.user_id != user_id and not is_admin:
        return jsonify({'error': 'Access denied'}), 403
    stop_file_process(file_id)
    return jsonify({'status': 'stopped'})

@app.route('/api/restart/<int:file_id>', methods=['POST'])
@login_required
def api_restart(file_id):
    user_id = session['user_id']
    is_admin = session.get('is_admin', 0)
    file_record = get_file_record(file_id)
    if not file_record:
        return jsonify({'error': 'File not found'}), 404
    if file_record.user_id != user_id and not is_admin:
        return jsonify({'error': 'Access denied'}), 403
    if file_record.file_type not in ['python', 'php']:
        return jsonify({'error': 'Only Python or PHP files can be restarted'}), 400

    with starting_lock:
        if file_id in starting_file_ids:
            return jsonify({'error': 'Process is already restarting, please wait...'}), 429
        starting_file_ids.add(file_id)

    try:
        stop_file_process(file_id)
        time.sleep(0.5)
        success, msg = start_file_process(file_id, file_record.user_id)
        if success:
            return jsonify({'status': 'restarted', 'message': msg})
        else:
            return jsonify({'error': msg}), 400
    finally:
        with starting_lock:
            starting_file_ids.discard(file_id)

@app.route('/api/bot_config/<int:file_id>', methods=['GET', 'POST'])
@login_required
def api_bot_config(file_id):
    user_id = session['user_id']
    is_admin = session.get('is_admin', 0)
    file_record = get_file_record(file_id)
    if not file_record:
        return jsonify({'error': 'Bot not found'}), 404
    if file_record.user_id != user_id and not is_admin:
        return jsonify({'error': 'Access denied'}), 403

    if request.method == 'GET':
        candidate_files = []
        folder_path = file_record.path if os.path.isdir(file_record.path) else os.path.dirname(file_record.path)
        if os.path.isdir(folder_path):
            for root, _, files in os.walk(folder_path):
                for f in files:
                    if f.endswith(('.py', '.php', '.js', '.sh', '.bat')):
                        rel = os.path.relpath(os.path.join(root, f), folder_path).replace('\\', '/')
                        candidate_files.append(rel)

        return jsonify({
            'success': True,
            'file_id': file_id,
            'orig_name': file_record.orig_name,
            'entry_file': file_record.entry_file or '',
            'custom_cmd': file_record.custom_cmd or '',
            'status': file_record.status,
            'candidate_files': sorted(candidate_files)[:30]
        })

    # POST: Update configuration
    data = request.get_json(silent=True) or request.form
    entry_file = data.get('entry_file', '').strip()
    custom_cmd = data.get('custom_cmd', '').strip()

    file_record.entry_file = entry_file if entry_file else None
    file_record.custom_cmd = custom_cmd if custom_cmd else None
    db_session.commit()

    restart = str(data.get('restart', '')).lower() in ['true', '1', 'yes']
    if restart and file_record.status == 'Running':
        success, msg = start_file_process(file_id, file_record.user_id)
        return jsonify({
            'success': True,
            'message': f'Config saved and bot restarted: {msg}',
            'entry_file': file_record.entry_file or '',
            'custom_cmd': file_record.custom_cmd or ''
        })

    return jsonify({
        'success': True,
        'message': 'Configuration updated successfully!',
        'entry_file': file_record.entry_file or '',
        'custom_cmd': file_record.custom_cmd or ''
    })

@app.route('/api/logs/<int:file_id>')
@login_required
def api_logs(file_id):
    user_id = session['user_id']
    is_admin = session.get('is_admin', 0)
    file_record = get_file_record(file_id)
    if not file_record:
        return jsonify({'error': 'File not found'}), 404
    if file_record.user_id != user_id and not is_admin:
        return jsonify({'error': 'Access denied'}), 403
    logs = get_file_logs(file_id)
    missing_module = extract_missing_module(logs)
    return jsonify({'logs': logs, 'missing_module': missing_module})

@app.route('/api/install_module/<int:file_id>', methods=['POST'])
@login_required
def api_install_module(file_id):
    user_id = session['user_id']
    is_admin = session.get('is_admin', 0)
    file_record = get_file_record(file_id)
    if not file_record:
        return jsonify({'error': 'File not found'}), 404
    if file_record.user_id != user_id and not is_admin:
        return jsonify({'error': 'Access denied'}), 403
    if file_record.file_type not in ['python', 'php']:
        return jsonify({'error': 'Only Python or PHP files can have modules installed'}), 400
    
    data = request.get_json()
    module_name = data.get('module_name', '').strip()
    if not module_name:
        return jsonify({'error': 'Module name required'}), 400
    
    # 1. Clean dotted module names (e.g. config.settings -> config)
    root_module = module_name.split('.')[0].strip()

    # 2. Check if this is a local folder or file inside the bot's workspace
    file_path = file_record.path
    working_dir = file_path if os.path.isdir(file_path) else os.path.dirname(file_path)
    local_target = os.path.join(working_dir, root_module)
    local_py = os.path.join(working_dir, f"{root_module}.py")
    
    # Check inside subdirectories as well (e.g. testing/bot or testing)
    is_local_file = os.path.exists(local_target) or os.path.exists(local_py)
    if not is_local_file:
        for r, dirs, files in os.walk(working_dir):
            if root_module in dirs or f"{root_module}.py" in files:
                is_local_file = True
                break

    if is_local_file:
        # If entry_file was set to library main.py but a project runner exists, auto-fix entry_file
        for r_cand in ['run.py', 'testing/run.py']:
            full_r = os.path.join(working_dir, r_cand)
            if os.path.isfile(full_r):
                file_record.entry_file = r_cand
                try:
                    db_session.commit()
                except Exception:
                    pass
                break

        # It's an internal project module/folder, not a PyPI package!
        # Restart cleanly with updated PYTHONPATH & cwd
        stop_file_process(file_id)
        time.sleep(1)
        success, msg = start_file_process(file_id, file_record.user_id)
        if success:
            return jsonify({'status': 'installed_and_restarted', 'message': f"'{module_name}' is a local project folder/module. Project paths configured and bot restarted."})
        else:
            return jsonify({'error': f"Bot failed to start: {msg}"}), 500

    # 3. Map common import names to actual PyPI distribution package names
    name_map = {
        'telebot': 'pyTelegramBotAPI',
        'telegram': 'python-telegram-bot',
        'PIL': 'Pillow',
        'cv2': 'opencv-python',
        'Crypto': 'pycryptodome',
        'bs4': 'beautifulsoup4',
        'yaml': 'PyYAML',
        'dateutil': 'python-dateutil',
        'dotenv': 'python-dotenv',
        'discord': 'discord.py',
    }
    pip_pkg = name_map.get(root_module, root_module)

    # Install the module via pip
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "install", pip_pkg, "--disable-pip-version-check"],
                                capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            err_msg = result.stderr.strip() or result.stdout.strip()
            # If PyPI doesn't have it, give a clear friendly message
            if "No matching distribution found" in err_msg:
                return jsonify({'error': f"'{pip_pkg}' is not a public PyPI package. If it's a project file/folder, please check its location or directory structure."}), 400
            return jsonify({'error': f'Installation failed: {err_msg[:200]}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    # Restart the bot
    stop_file_process(file_id)
    time.sleep(1)
    success, msg = start_file_process(file_id, file_record.user_id)
    if success:
        return jsonify({'status': 'installed_and_restarted', 'message': msg})
    else:
        return jsonify({'error': f'Module installed but bot failed to start: {msg}'}), 500

@app.route('/api/delete/<int:file_id>', methods=['POST'])
@login_required
def api_delete(file_id):
    db_session.rollback()
    user_id = session['user_id']
    is_admin = session.get('is_admin', 0)
    file_record = get_file_record(file_id)
    if not file_record:
        return jsonify({'error': 'File record not found'}), 404
    if file_record.user_id != user_id and not is_admin:
        return jsonify({'error': 'Access denied'}), 403
    stop_file_process(file_id)
    try:
        remove_file_record(file_id)
        return jsonify({'status': 'deleted'})
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error deleting file {file_record.path}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/system')
@login_required
def api_system():
    cpu, mem, proc_count = get_system_load()
    return jsonify({'cpu': cpu, 'memory': mem, 'running': proc_count})

@app.route('/debug')
def debug():
    import traceback
    try:
        files = list_all_files()
        return f"Total files with valid user: {len(files)}"
    except Exception as e:
        return traceback.format_exc().replace('\n', '<br>')

@app.route('/debug-admin')
@login_required
def debug_admin():
    return jsonify({
        'user_id': session.get('user_id'),
        'is_admin': session.get('is_admin'),
        'is_admin_type': str(type(session.get('is_admin')))
    })

# -----------------------------------------------------------------------------
# 10. Ensure default admin user exists
# -----------------------------------------------------------------------------
with app.app_context():
    admin_emails = [e.strip() for e in ADMIN_EMAILS if e.strip()]
    if not admin_emails:
        admin_emails = ["admin@example.com"]
    for admin_email in admin_emails:
        existing_u = get_user_by_email(admin_email)
        if not existing_u:
            password_hash = generate_password_hash("admin123")
            admin = User(
                email=admin_email,
                username="admin",
                password_hash=password_hash,
                is_admin=1,
                created_at=datetime.now(IST)
            )
            db_session.add(admin)
            db_session.commit()
            get_user_workspace(admin.id)
            logger.info(f"Created admin user: {admin_email}")
        else:
            if existing_u.is_admin != 1:
                existing_u.is_admin = 1
                db_session.commit()
                logger.info(f"Updated {admin_email} to admin")

    # Auto-synchronize files and patch ports on startup for user 1 bots
    try:
        tmb_dir = os.path.join(DATA_DIR, 'workspace', '1', 'temp_mail_bot')
        bot_dir = os.path.join(DATA_DIR, 'workspace', '1', 'bot')
        if os.path.exists(bot_dir) or os.path.exists(tmb_dir):
            os.makedirs(tmb_dir, exist_ok=True)
            os.makedirs(bot_dir, exist_ok=True)
            sync_files = [
                'bot.py', 'config.py', 'database.py', 'requirements.txt', 'keyboards.py',
                'mail_service.py', 'extractor.py', 'premium_emojis.py', 'watcher.py', 'delete_user.py'
            ]
            for fn in sync_files:
                s1 = os.path.join(tmb_dir, fn)
                d1 = os.path.join(bot_dir, fn)
                if os.path.exists(s1) and not os.path.exists(d1):
                    shutil.copy2(s1, d1)
                s2 = os.path.join(bot_dir, fn)
                d2 = os.path.join(tmb_dir, fn)
                if os.path.exists(s2) and not os.path.exists(d2):
                    shutil.copy2(s2, d2)
            bot_env = os.path.join(bot_dir, '.env')
            tmb_env = os.path.join(tmb_dir, '.env')
            if os.path.exists(bot_env) and not os.path.exists(tmb_env):
                shutil.copy2(bot_env, tmb_env)

            dynamic_socket_snippet = '''def ensure_single_instance(port: int = None):
    global _single_instance_socket
    if port is None:
        import zlib, os
        curr_dir = os.path.dirname(os.path.abspath(__file__))
        port = 40000 + (zlib.crc32(curr_dir.encode()) % 10000)
    _single_instance_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        _single_instance_socket.bind(('127.0.0.1', port))
    except OSError:
        logging.getLogger(__name__).warning(f"Another instance in this folder is already running on port {port}! Exiting cleanly.")
        sys.exit(0)'''

            import re
            for b_dir in [bot_dir, tmb_dir]:
                b_py = os.path.join(b_dir, 'bot.py')
                if os.path.exists(b_py):
                    with open(b_py, 'r', encoding='utf-8', errors='replace') as f:
                        txt = f.read()
                    if 'CRITICAL TELEGRAM CONFLICT' in txt:
                        txt = re.sub(
                            r'    try:\s+await dp\.start_polling\(bot\)\s+except Exception as e:.*?raise',
                            '        await dp.start_polling(bot)',
                            txt,
                            flags=re.DOTALL
                        )
                    if 'import zlib\n' in txt and 'import zlib, os' not in txt:
                        txt = txt.replace('import zlib\n', 'import zlib, os\n')
                    if 'def ensure_single_instance(port: int = 49512):' in txt or ('def ensure_single_instance(' in txt and '40000 +' not in txt):
                        txt = re.sub(
                            r'def ensure_single_instance\(.*?\n(?=from config import)',
                            dynamic_socket_snippet + '\n',
                            txt,
                            flags=re.DOTALL
                        )
                        with open(b_py, 'w', encoding='utf-8') as f:
                            f.write(txt)
            logger.info("Auto-sync and dynamic port patch applied to user 1 bots successfully.")
    except Exception as e:
        logger.warning(f"Error during auto-sync of bots: {e}")

# -----------------------------------------------------------------------------
# 11. Automated Volume & Log Cleanup Background Thread
# Keeps /tmp/aura_logs clean and purges volume sandboxes, pycache, and logs
# Runs every 15 minutes to guarantee Railway volume never fills up
# -----------------------------------------------------------------------------
def _log_cleanup_worker():
    """Background thread: periodically purge stale/large log files and volume junk."""
    INTERVAL = 15 * 60  # 15 minutes

    while True:
        try:
            now = time.time()
            # 1. Clean /tmp logs
            if os.path.isdir(LOGS_DIR):
                for fname in os.listdir(LOGS_DIR):
                    fpath = os.path.join(LOGS_DIR, fname)
                    if os.path.isfile(fpath):
                        try:
                            if now - os.path.getmtime(fpath) > 1800 or os.path.getsize(fpath) > 1024 * 1024:
                                os.remove(fpath)
                        except Exception:
                            pass

            # 2. Clean DATA_DIR: remove __pycache__, old sandboxes, and stray junk files
            if os.path.isdir(DATA_DIR):
                for root, dirs, files in os.walk(DATA_DIR, topdown=False):
                    for d in dirs:
                        p = os.path.join(root, d)
                        if d == '__pycache__':
                            try:
                                shutil.rmtree(p, ignore_errors=True)
                            except Exception:
                                pass
                        elif d == 'sandbox':
                            try:
                                for sub in os.listdir(p):
                                    sub_p = os.path.join(p, sub)
                                    try:
                                        if now - os.path.getmtime(sub_p) > 900:  # 15 mins
                                            shutil.rmtree(sub_p, ignore_errors=True)
                                    except Exception:
                                        pass
                            except Exception:
                                pass

                    for f in files:
                        if f.endswith(('.log', '.log.old', '.tmp', '.cache', '.bak')) or f.startswith('tmp'):
                            try:
                                os.remove(os.path.join(root, f))
                            except Exception:
                                pass

        except Exception as e:
            logger.warning(f"Background cleanup exception: {e}")

        time.sleep(INTERVAL)

_cleanup_thread = threading.Thread(target=_log_cleanup_worker, daemon=True)
_cleanup_thread.start()

# -----------------------------------------------------------------------------
# 12. Main
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)


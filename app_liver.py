import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# --- ログ設定 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'poibox_v24_listener_management'

# --- データベース設定 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'test_pts.db')

def get_db_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_conn()
    try:
        # admins: ライバーのログイン情報
        conn.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        # messages: リスナーからのメッセージ
        conn.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                liver TEXT NOT NULL,
                sender TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
    except Exception as e:
        logger.error(f"DATABASE INIT ERROR: {e}")
    finally:
        conn.close()

init_db()

# --- ルート設定 ---

@app.route('/')
def index():
    return render_template('index.html')

# リスナー用ページ (URL: /username/welcome.com)
@app.route('/<username>/welcome.com', methods=['GET', 'POST'])
def welcome(username):
    conn = get_db_conn()
    if request.method == 'POST':
        sender = request.form.get('sender', '匿名リスナー')
        content = request.form.get('content')
        if content:
            conn.execute('INSERT INTO messages (liver, sender, content) VALUES (?, ?, ?)', (username, sender, content))
            conn.commit()
    messages = conn.execute('SELECT * FROM messages WHERE liver = ? ORDER BY id DESC LIMIT 10', (username,)).fetchall()
    conn.close()
    return render_template('welcome.html', liver_name=username, messages=messages)

# ログイン
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        conn = get_db_conn()
        admin_data = conn.execute('SELECT * FROM admins WHERE username = ?', (user,)).fetchone()
        conn.close()
        if admin_data and check_password_hash(admin_data['password'], pwd):
            session['user_id'] = user
            return redirect(url_for('admin'))
        flash('ログイン失敗')
    return render_template('login.html')

# --- 【メイン】管理画面：リスナー一覧を表示 ---
@app.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    username = session['user_id']
    conn = get_db_conn()
    
    # 1. これまでメッセージを送ってくれたリスナーを重複なしで取得（リスト作成）
    listeners = conn.execute(
        'SELECT DISTINCT sender FROM messages WHERE liver = ? ORDER BY sender ASC', 
        (username,)
    ).fetchall()
    
    # 2. 全メッセージ取得
    messages = conn.execute(
        'SELECT * FROM messages WHERE liver = ? ORDER BY id DESC', 
        (username,)
    ).fetchall()
    
    conn.close()
    share_url = f"{request.host_url}{username}/welcome.com"
    
    return render_template('admin.html', username=username, share_url=share_url, messages=messages, listeners=listeners)

# 新規登録
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user, pwd = request.form.get('username'), request.form.get('password')
        if user and pwd:
            hashed = generate_password_hash(pwd)
            with get_db_conn() as conn:
                try:
                    conn.execute('INSERT INTO admins (username, password) VALUES (?, ?)', (user, hashed))
                    conn.commit()
                    return redirect(url_for('login'))
                except: flash('登録済み')
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

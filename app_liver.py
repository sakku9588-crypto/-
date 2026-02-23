import os
import re
import threading
import sqlite3
import logging
import time
import webbrowser  # ブラウザ起動用
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# --- ログ設定 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'poibox_ultimate_secret_key_fixed_v4'

# --- 実行環境のパス制御 (重要：exe化対応) ---
import sys
if getattr(sys, 'frozen', False):
    # exeで動いている時
    BASE_DIR = os.path.dirname(sys.executable)
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    app.template_folder = template_folder
else:
    # そのままPythonで動かしている時
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MASTER_DB = os.path.join(BASE_DIR, 'master_admin.db')

# --- DB接続関数 ---
def get_master_conn():
    conn = sqlite3.connect(MASTER_DB)
    conn.row_factory = sqlite3.Row
    return conn

def get_user_db_conn(username):
    user_db = os.path.join(BASE_DIR, f"{username}_pts.db")
    conn = sqlite3.connect(user_db)
    conn.row_factory = sqlite3.Row
    conn.execute('CREATE TABLE IF NOT EXISTS users (handle TEXT PRIMARY KEY, points INTEGER DEFAULT 0, total_points INTEGER DEFAULT 0, last_touch REAL DEFAULT 0)')
    conn.execute('CREATE TABLE IF NOT EXISTS passbook (id INTEGER PRIMARY KEY AUTOINCREMENT, handle TEXT, amount INTEGER, reason TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    
    # カラム追加メンテナンス
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(users)")
    cols = [i[1] for i in cur.fetchall()]
    if "total_points" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN total_points INTEGER DEFAULT 0")
        conn.execute("UPDATE users SET total_points = points")
    conn.commit()
    return conn

# --- 初期化 ---
def init_all():
    m_conn = get_master_conn()
    m_conn.execute('CREATE TABLE IF NOT EXISTS admins (username TEXT PRIMARY KEY, password TEXT)')
    m_conn.commit()
    m_conn.close()

init_all()

# --- ルーティング ---
@app.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('login'))
    username = session['user_id']
    query = request.args.get('q', '').strip()
    conn = get_user_db_conn(username)
    try:
        if query:
            users = conn.execute("SELECT * FROM users WHERE handle LIKE ? ORDER BY total_points DESC", ('%' + query + '%',)).fetchall()
        else:
            users = conn.execute("SELECT * FROM users ORDER BY total_points DESC").fetchall()
        history = conn.execute("SELECT * FROM passbook ORDER BY created_at DESC LIMIT 20").fetchall()
    finally:
        conn.close()
    return render_template('admin.html', users=users, username=username, q=query, history=history)

@app.route('/add_points', methods=['POST'])
def add_points():
    if 'user_id' not in session: return redirect(url_for('login'))
    username = session['user_id']
    handle, op = request.form.get('handle'), request.form.get('op')
    reason = request.form.get('reason', '').strip() or ("手動付与" if op=='add' else "手動減算")
    current_q = request.form.get('current_q', '')
    try:
        amount = int(request.form.get('amount', 0))
        conn = get_user_db_conn(username)
        user = conn.execute("SELECT points FROM users WHERE handle = ?", (handle,)).fetchone()
        if user:
            current_pts = user['points']
            change = -amount if op == 'sub' else amount
            if op == 'sub' and current_pts < amount:
                flash(f'エラー：ポイント不足', 'danger')
            else:
                conn.execute("UPDATE users SET points = points + ? WHERE handle = ?", (change, handle))
                if change > 0: conn.execute("UPDATE users SET total_points = total_points + ? WHERE handle = ?", (change, handle))
                conn.execute("INSERT INTO passbook (handle, amount, reason) VALUES (?, ?, ?)", (handle, change, reason))
                conn.commit()
                flash(f'{handle} 更新完了', 'success')
        conn.close()
    except Exception as e: flash(f'エラー: {e}', 'danger')
    return redirect(url_for('index', q=current_q))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user, pwd = request.form.get('username'), request.form.get('password')
        conn = get_master_conn()
        admin = conn.execute('SELECT * FROM admins WHERE username = ?', (user,)).fetchone()
        conn.close()
        if admin and check_password_hash(admin['password'], pwd):
            session['user_id'] = user
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user, pwd = request.form.get('username'), request.form.get('password')
        if user and pwd:
            hashed = generate_password_hash(pwd)
            conn = get_master_conn()
            try:
                conn.execute('INSERT INTO admins (username, password) VALUES (?, ?)', (user, hashed))
                conn.commit()
                return redirect(url_for('login'))
            except: flash('ID使用済み', 'danger')
            finally: conn.close()
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- 起動処理 ---
def open_browser():
    """サーバー起動を少し待ってからブラウザを開く"""
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:5000")

if __name__ == '__main__':
    # exe化した時にブラウザが自動で開くようにスレッドを開始
    threading.Thread(target=open_browser, daemon=True).start()
    
    # 外部アクセス許可設定 (host='0.0.0.0')
    app.run(debug=False, port=5000, host='0.0.0.0')
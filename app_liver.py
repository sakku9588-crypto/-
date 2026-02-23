import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'poibox_v28_step_flow'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'test_pts.db')

def get_db_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_conn()
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS listeners (id INTEGER PRIMARY KEY AUTOINCREMENT, liver_owner TEXT NOT NULL, name TEXT NOT NULL, points INTEGER DEFAULT 0, UNIQUE(liver_owner, name))')
        conn.execute('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, liver TEXT NOT NULL, sender TEXT, content TEXT NOT NULL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
        conn.commit()
    except Exception as e:
        logger.error(f"DB INIT ERROR: {e}")
    finally:
        conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

# --- ① リスナー用 welcomeページ (入力＆通帳表示) ---
@app.route('/<liver_name>/welcome', methods=['GET', 'POST'])
def welcome(liver_name):
    listener_data = None
    listener_name = None

    if request.method == 'POST':
        listener_name = request.form.get('listener_name')
        conn = get_db_conn()
        listener_data = conn.execute('SELECT * FROM listeners WHERE liver_owner = ? AND name = ?', 
                                    (liver_name, listener_name)).fetchone()
        conn.close()
        if not listener_data:
            flash(f'「{listener_name}」さんは登録されていません。')

    # POSTでデータがあれば通帳表示、なければ入力画面を表示（どちらもwelcome.html内で処理）
    return render_template('welcome.html', liver_name=liver_name, listener=listener_data, input_name=listener_name)

# --- ② 掲示板ページ ---
@app.route('/<liver_name>/board.com', methods=['GET', 'POST'])
def board(liver_name):
    conn = get_db_conn()
    if request.method == 'POST':
        sender = request.form.get('sender', '匿名')
        content = request.form.get('content')
        if content:
            conn.execute('INSERT INTO messages (liver, sender, content) VALUES (?, ?, ?)', (liver_name, sender, content))
            conn.commit()
    
    messages = conn.execute('SELECT * FROM messages WHERE liver = ? ORDER BY id DESC LIMIT 20', (liver_name,)).fetchall()
    conn.close()
    return render_template('board.html', liver_name=liver_name, messages=messages)

# --- ライバーログイン・管理画面 ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user, pwd = request.form.get('username'), request.form.get('password')
        conn = get_db_conn()
        admin = conn.execute('SELECT * FROM admins WHERE username = ?', (user,)).fetchone()
        conn.close()
        if admin and check_password_hash(admin['password'], pwd):
            session['user_id'] = user
            return redirect(url_for('admin'))
        flash('ログイン失敗')
    return render_template('login.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session: return redirect(url_for('login'))
    username = session['user_id']
    conn = get_db_conn()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create':
            name, pts = request.form.get('name'), request.form.get('points', 0)
            try:
                conn.execute('INSERT INTO listeners (liver_owner, name, points) VALUES (?, ?, ?)', (username, name, pts))
                conn.commit()
            except: flash('作成失敗')
        elif action == 'update_points':
            l_id, diff = request.form.get('listener_id'), int(request.form.get('diff', 0))
            conn.execute('UPDATE listeners SET points = points + ? WHERE id = ? AND liver_owner = ?', (diff, l_id, username))
            conn.commit()
    listeners = conn.execute('SELECT * FROM listeners WHERE liver_owner = ? ORDER BY name ASC', (username,)).fetchall()
    conn.close()
    return render_template('admin.html', username=username, listeners=listeners)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user, pwd = request.form.get('username'), request.form.get('password')
        if user and pwd:
            hashed = generate_password_hash(pwd)
            conn = get_db_conn()
            try:
                conn.execute('INSERT INTO admins (username, password) VALUES (?, ?)', (user, hashed))
                conn.commit()
                return redirect(url_for('login'))
            except: flash('登録済み')
            finally: conn.close()
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

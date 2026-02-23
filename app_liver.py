import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# ログを詳細に出してエラー箇所を見つけやすくする
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'poibox_v35_fix_no_shell'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'test_pts.db')

def get_db_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL;') 
    return conn

# データベースの初期化と自動カラム追加
def init_db():
    conn = get_db_conn()
    try:
        # 1. 基本テーブルの作成
        conn.execute('CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)')
        conn.execute('CREATE TABLE IF NOT EXISTS listeners (id INTEGER PRIMARY KEY AUTOINCREMENT, liver_owner TEXT, name TEXT, points INTEGER DEFAULT 0, UNIQUE(liver_owner, name))')
        conn.execute('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, liver TEXT, sender TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
        
        # 2. 累計ポイント用カラム(total_points)があるか確認し、なければ追加
        cursor = conn.execute("PRAGMA table_info(listeners)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'total_points' not in columns:
            logger.info("Adding total_points column...")
            conn.execute('ALTER TABLE listeners ADD COLUMN total_points INTEGER DEFAULT 0')
        
        conn.commit()
    except Exception as e:
        logger.error(f"Database Init Error: {e}")
    finally:
        conn.close()

init_db()

# --- ルーティング ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/<liver_name>/welcome', methods=['GET', 'POST'])
def welcome(liver_name):
    listener_data = None
    if request.method == 'POST':
        lname = request.form.get('listener_name')
        conn = get_db_conn()
        listener_data = conn.execute('SELECT * FROM listeners WHERE liver_owner = ? AND name = ?', (liver_name, lname)).fetchone()
        conn.close()
    # テンプレート側(welcome.html)では {{ listener.points }} と {{ listener.total_points }} を使用
    return render_template('welcome.html', liver_name=liver_name, listener=listener_data)

@app.route('/<liver_name>/board.com', methods=['GET', 'POST'])
def board(liver_name):
    conn = get_db_conn()
    if request.method == 'POST':
        sender = request.form.get('sender', '匿名')
        content = request.form.get('content')
        if content:
            conn.execute('INSERT INTO messages (liver, sender, content) VALUES (?, ?, ?)', (liver_name, sender, content))
            conn.commit()
    messages = conn.execute('SELECT * FROM messages WHERE liver = ? ORDER BY id DESC LIMIT 15', (liver_name,)).fetchall()
    conn.close()
    return render_template('board.html', liver_name=liver_name, messages=messages)

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
    return render_template('login.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session: return redirect(url_for('login'))
    username = session['user_id']
    conn = get_db_conn()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create':
            name = request.form.get('name')
            pts = int(request.form.get('points', 0))
            try:
                conn.execute('INSERT INTO listeners (liver_owner, name, points, total_points) VALUES (?, ?, ?, ?)', (username, name, pts, pts))
                conn.commit()
            except: pass
        elif action == 'update_points':
            l_id = request.form.get('listener_id')
            diff = int(request.form.get('diff', 0))
            if diff > 0:
                conn.execute('UPDATE listeners SET points = points + ?, total_points = total_points + ? WHERE id = ?', (diff, diff, l_id))
            else:
                conn.execute('UPDATE listeners SET points = points + ? WHERE id = ?', (diff, l_id))
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
            except: pass
            finally: conn.close()
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

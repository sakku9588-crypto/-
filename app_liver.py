import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# 重要：セッションを維持するためにキーを固定します
app.secret_key = 'poibox_ultimate_stable_v100'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'test_pts.db')

def get_db_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL;') 
    return conn

def init_db():
    conn = get_db_conn()
    conn.execute('CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS listeners (id INTEGER PRIMARY KEY AUTOINCREMENT, liver_owner TEXT, name TEXT, points INTEGER DEFAULT 0, total_points INTEGER DEFAULT 0, UNIQUE(liver_owner, name))')
    conn.execute('''CREATE TABLE IF NOT EXISTS messages 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, liver TEXT, sender TEXT, content TEXT, 
                     parent_id INTEGER DEFAULT NULL, likes INTEGER DEFAULT 0, 
                     timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

# --- 1. トップページ (検索) ---
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        liver_name = request.form.get('liver_name')
        if liver_name:
            return redirect(url_for('welcome', liver_name=liver_name))
    return render_template('index.html')

# --- 2. 通帳マイページ (ログイン・データ表示) ---
@app.route('/<liver_name>/welcome', methods=['GET', 'POST'])
def welcome(liver_name):
    lname = None
    if request.method == 'POST':
        lname = request.form.get('listener_name')
        if lname:
            session[f'active_user_{liver_name}'] = lname # セッションに保存
    else:
        # 掲示板から戻った際などにセッションから名前を復元
        lname = session.get(f'active_user_{liver_name}')

    listener_data = None
    if lname:
        conn = get_db_conn()
        listener_data = conn.execute('SELECT * FROM listeners WHERE liver_owner = ? AND name = ?', 
                                     (liver_name, lname)).fetchone()
        conn.close()
        if not listener_data and request.method == 'POST':
            flash(f'「{lname}」さんは未登録です。')

    return render_template('welcome.html', liver_name=liver_name, listener=listener_data)

# --- 3. 掲示板 (バグ修正版) ---
@app.route('/<liver_name>/board.com', methods=['GET', 'POST'])
def board(liver_name):
    # ログイン中の名前を取得
    logged_in_name = session.get(f'active_user_{liver_name}')
    conn = get_db_conn()
    
    if request.method == 'POST':
        action = request.form.get('action')
        # ログイン済みならその名前、そうでなければフォームの sender (HTMLにある場合)
        sender = logged_in_name if logged_in_name else request.form.get('sender', '').strip()

        # 登録者チェック
        listener = conn.execute('SELECT * FROM listeners WHERE liver_owner = ? AND name = ?', 
                                (liver_name, sender)).fetchone()
        
        if not listener:
            flash('通帳でログインしてから書き込んでね！')
            conn.close()
            return redirect(url_for('board', liver_name=liver_name))

        if action == 'like':
            msg_id = request.form.get('message_id')
            conn.execute('UPDATE messages SET likes = likes + 1 WHERE id = ?', (msg_id,))
        else:
            # HTML側の <input name="message"> から取得
            content = request.form.get('message')
            parent_id = request.form.get('parent_id')
            if content:
                conn.execute('INSERT INTO messages (liver, sender, content, parent_id) VALUES (?, ?, ?, ?)', 
                             (liver_name, sender, content, parent_id if parent_id else None))
        
        conn.commit()
        conn.close()
        return redirect(url_for('board', liver_name=liver_name))

    # 投稿一覧
    messages = conn.execute('SELECT * FROM messages WHERE liver = ? ORDER BY id ASC', (liver_name,)).fetchall()
    conn.close()
    
    main_posts = [m for m in messages if m['parent_id'] is None]
    replies = [m for m in messages if m['parent_id'] is not None]
    
    return render_template('board.html', 
                           liver_name=liver_name, 
                           main_posts=main_posts, 
                           replies=replies, 
                           logged_in_name=logged_in_name)

# --- 4. ログアウト (close対応) ---
@app.route('/logout')
def logout():
    session.clear() # 全てのセッションを削除
    return redirect(url_for('index')) # 完全にトップに戻す

# --- 管理画面系 ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user, pwd = request.form.get('username'), request.form.get('password')
        conn = get_db_conn()
        admin = conn.execute('SELECT * FROM admins WHERE username = ?', (user,)).fetchone()
        conn.close()
        if admin and check_password_hash(admin['password'], pwd):
            session['admin_user'] = user
            return redirect(url_for('admin'))
    return render_template('login.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'admin_user' not in session: return redirect(url_for('login'))
    username = session['admin_user']
    conn = get_db_conn()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create':
            name, pts = request.form.get('name'), int(request.form.get('points', 0))
            try:
                conn.execute('INSERT INTO listeners (liver_owner, name, points, total_points) VALUES (?, ?, ?, ?)', (username, name, pts, pts))
                conn.commit()
            except: pass
        elif action == 'update_points':
            l_id, diff = request.form.get('listener_id'), int(request.form.get('diff', 0))
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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

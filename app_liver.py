import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
# セッションを確実に維持・破棄するための鍵
app.secret_key = 'poibox_v100_stable_system'

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

# --- 1. トップページ ---
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        liver_name = request.form.get('liver_name')
        if liver_name:
            # セッションにライバー名を保存（URLが変わっても追跡するため）
            session['current_liver'] = liver_name
            return redirect(url_for('welcome', liver_name=liver_name))
    return render_template('index.html')

# --- 2. 通帳ページ (mypage.html) ---
# ※関数名を welcome にし、HTML内のURL生成に対応
@app.route('/<liver_name>/welcome', methods=['GET', 'POST'])
def welcome(liver_name):
    session['current_liver'] = liver_name
    lname = None
    
    if request.method == 'POST':
        lname = request.form.get('listener_name')
        if lname:
            session[f'user_{liver_name}'] = lname # 名前を保存
    else:
        lname = session.get(f'user_{liver_name}') # 名前を復元

    listener_data = None
    if lname:
        conn = get_db_conn()
        listener_data = conn.execute('SELECT * FROM listeners WHERE liver_owner = ? AND name = ?', 
                                     (liver_name, lname)).fetchone()
        conn.close()

    if listener_data:
        # mypage.html で使われている変数名に完全に一致させて送る
        return render_template('mypage.html', 
                               liver_name=liver_name,
                               user_handle=listener_data['name'],
                               user_points=listener_data['points'],
                               total_points=listener_data['total_points'],
                               is_verified=True,
                               history=[]) # 履歴機能が必要な場合はここを拡張
    
    # 未ログイン時はログイン入力画面（既存のwelcome.html）を表示
    return render_template('welcome.html', liver_name=liver_name, listener=None)

# --- 3. 掲示板 (board.html) ---
# ※関数名を board にし、HTML内の url_for('board') に対応
@app.route('/board.com', methods=['GET', 'POST'])
def board():
    # URLからではなくセッションからライバー名を特定
    liver_name = session.get('current_liver')
    if not liver_name:
        return redirect(url_for('index'))
        
    logged_in_name = session.get(f'user_{liver_name}')
    conn = get_db_conn()
    
    if request.method == 'POST':
        action = request.form.get('action')
        sender = logged_in_name if logged_in_name else request.form.get('sender', '').strip()

        if action == 'like':
            msg_id = request.form.get('message_id')
            conn.execute('UPDATE messages SET likes = likes + 1 WHERE id = ?', (msg_id,))
        else:
            # HTML側の name="message" を受け取り content カラムに保存
            msg_text = request.form.get('message')
            parent_id = request.form.get('parent_id')
            if msg_text:
                conn.execute('INSERT INTO messages (liver, sender, content, parent_id) VALUES (?, ?, ?, ?)', 
                             (liver_name, sender, msg_text, parent_id if parent_id else None))
        conn.commit()
        conn.close()
        return redirect(url_for('board'))

    messages = conn.execute('SELECT * FROM messages WHERE liver = ? ORDER BY id ASC', (liver_name,)).fetchall()
    conn.close()
    
    main_posts = [m for m in messages if m['parent_id'] is None]
    replies = [m for m in messages if m['parent_id'] is not None]
    
    return render_template('board.html', 
                           liver_name=liver_name, 
                           main_posts=main_posts, 
                           replies=replies, 
                           logged_in_name=logged_in_name)

# --- 4. ログアウト (退出する) ---
# ※関数名を logout にし、HTML内の url_for('logout') に対応
@app.route('/logout')
def logout():
    session.clear() # 全てのログイン情報を破棄
    return redirect(url_for('index')) # 入り口へ

# --- 管理者機能 ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user, pwd = request.form.get('username'), request.form.get('password')
        conn = get_db_conn()
        admin = conn.execute('SELECT * FROM admins WHERE username = ?', (user,)).fetchone()
        conn.close()
        if admin and check_password_hash(admin['password'], pwd):
            session['admin'] = user
            return redirect(url_for('admin'))
    return render_template('login.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'admin' not in session: return redirect(url_for('login'))
    username = session['admin']
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
            conn.execute('UPDATE listeners SET points = points + ? WHERE id = ?', (diff, l_id))
            if diff > 0:
                conn.execute('UPDATE listeners SET total_points = total_points + ? WHERE id = ?', (diff, l_id))
            conn.commit()
    listeners = conn.execute('SELECT * FROM listeners WHERE liver_owner = ? ORDER BY name ASC', (username,)).fetchall()
    conn.close()
    return render_template('admin.html', username=username, listeners=listeners)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

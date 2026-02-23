import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'poibox_all_features_integrated_v5'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'test_pts.db')

def get_db_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn

# データベース初期化（全テーブル作成）
def init_db():
    with get_db_conn() as conn:
        # 管理者テーブル
        conn.execute('CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)')
        # リスナー（通帳）テーブル
        conn.execute('CREATE TABLE IF NOT EXISTS listeners (id INTEGER PRIMARY KEY AUTOINCREMENT, liver_owner TEXT, name TEXT, points INTEGER DEFAULT 0, total_points INTEGER DEFAULT 0, UNIQUE(liver_owner, name))')
        # 掲示板テーブル (HTMLの変数 handle, message, like_count に完全準拠)
        conn.execute('''CREATE TABLE IF NOT EXISTS messages 
                        (id INTEGER PRIMARY KEY AUTOINCREMENT, liver TEXT, handle TEXT, message TEXT, 
                         parent_id INTEGER DEFAULT NULL, like_count INTEGER DEFAULT 0, 
                         timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()

init_db()

# --- 1. トップページ (ライバー検索) ---
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        liver_name = request.form.get('liver_name')
        if liver_name: return redirect(url_for('welcome', liver_name=liver_name))
    return render_template('index.html')

# --- 2. 通帳ページ (mypage.html) ---
@app.route('/<liver_name>/welcome', methods=['GET', 'POST'])
def welcome(liver_name):
    if request.method == 'POST':
        lname = request.form.get('listener_name')
        if lname: session[f'user_{liver_name}'] = lname
    
    lname = session.get(f'user_{liver_name}')
    listener_data = None
    if lname:
        with get_db_conn() as conn:
            listener_data = conn.execute('SELECT * FROM listeners WHERE liver_owner = ? AND name = ?', (liver_name, lname)).fetchone()
    
    if listener_data:
        return render_template('mypage.html', 
                               liver_name=liver_name, 
                               user_handle=listener_data['name'], 
                               user_points=listener_data['points'], 
                               total_points=listener_data['total_points'], 
                               is_verified=True, 
                               history=[]) # 履歴表示用
    return render_template('welcome.html', liver_name=liver_name)

# --- 3. 掲示板ページ (board.html) ---
@app.route('/<liver_name>/board', methods=['GET', 'POST'])
def board(liver_name):
    logged_in_name = session.get(f'user_{liver_name}')
    
    if request.method == 'POST':
        msg_text = request.form.get('message')
        parent_id = request.form.get('parent_id')
        
        if not logged_in_name:
            flash('通帳からログインしてください')
            return redirect(url_for('board', liver_name=liver_name))

        if msg_text:
            with get_db_conn() as conn:
                conn.execute('INSERT INTO messages (liver, handle, message, parent_id) VALUES (?, ?, ?, ?)', 
                             (liver_name, logged_in_name, msg_text, int(parent_id) if parent_id and parent_id.isdigit() else None))
                conn.commit()
        return redirect(url_for('board', liver_name=liver_name))

    with get_db_conn() as conn:
        all_msgs = conn.execute('SELECT * FROM messages WHERE liver = ? ORDER BY id ASC', (liver_name,)).fetchall()
    
    posts = [m for m in all_msgs if m['parent_id'] is None]
    replies = [m for m in all_msgs if m['parent_id'] is not None]
    
    return render_template('board.html', liver_name=liver_name, posts=posts, replies=replies, current_user=logged_in_name)

# --- 4. いいね機能 ---
@app.route('/like/<int:post_id>')
def like_post(post_id):
    with get_db_conn() as conn:
        msg = conn.execute('SELECT liver FROM messages WHERE id = ?', (post_id,)).fetchone()
        if msg:
            conn.execute('UPDATE messages SET like_count = like_count + 1 WHERE id = ?', (post_id,))
            conn.commit()
            return redirect(url_for('board', liver_name=msg['liver']))
    return redirect(url_for('index'))

# --- 5. ログアウト (退出) ---
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- 6. 管理者ログイン ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user, pwd = request.form.get('username'), request.form.get('password')
        with get_db_conn() as conn:
            admin = conn.execute('SELECT * FROM admins WHERE username = ?', (user,)).fetchone()
            if admin and check_password_hash(admin['password'], pwd):
                session['admin_user'] = user
                return redirect(url_for('admin'))
        flash('ログイン失敗')
    return render_template('login.html')

# --- 7. 管理者サインアップ ---
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
                except: flash('既に存在するユーザー名です')
    return render_template('signup.html')

# --- 8. 管理画面 (ポイント操作) ---
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'admin_user' not in session: return redirect(url_for('login'))
    username = session['admin_user']
    with get_db_conn() as conn:
        if request.method == 'POST':
            action = request.form.get('action')
            if action == 'create':
                name, pts = request.form.get('name'), int(request.form.get('points', 0))
                try: conn.execute('INSERT INTO listeners (liver_owner, name, points, total_points) VALUES (?, ?, ?, ?)', (username, name, pts, pts))
                except: pass
            elif action == 'update_points':
                l_id, diff = request.form.get('listener_id'), int(request.form.get('diff', 0))
                conn.execute('UPDATE listeners SET points = points + ? WHERE id = ?', (diff, l_id))
                if diff > 0: conn.execute('UPDATE listeners SET total_points = total_points + ? WHERE id = ?', (diff, l_id))
            conn.commit()
        listeners = conn.execute('SELECT * FROM listeners WHERE liver_owner = ? ORDER BY name ASC', (username,)).fetchall()
    return render_template('admin.html', username=username, listeners=listeners)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

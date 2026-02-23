import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'poibox_admin_fix_2026' # セッション用の秘密鍵

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'test_pts.db')

def get_db_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL;') 
    return conn

# DB初期化（管理者・リスナー・掲示板テーブル）
def init_db():
    conn = get_db_conn()
    conn.execute('CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS listeners (id INTEGER PRIMARY KEY AUTOINCREMENT, liver_owner TEXT, name TEXT, points INTEGER DEFAULT 0, total_points INTEGER DEFAULT 0, UNIQUE(liver_owner, name))')
    conn.execute('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, liver TEXT, sender TEXT, content TEXT, parent_id INTEGER DEFAULT NULL, likes INTEGER DEFAULT 0, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
    conn.commit()
    conn.close()

init_db()

# --- 管理者ログイン ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        
        conn = get_db_conn()
        admin = conn.execute('SELECT * FROM admins WHERE username = ?', (user,)).fetchone()
        conn.close()

        # パスワードのハッシュ値を検証
        if admin and check_password_hash(admin['password'], pwd):
            session['admin_user'] = user # 管理者としてセッション開始
            return redirect(url_for('admin'))
        else:
            flash('ユーザー名またはパスワードが違います。')
            
    return render_template('login.html')

# --- 管理者新規登録（ログインできない時はここからやり直し） ---
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        
        if user and pwd:
            hashed_pwd = generate_password_hash(pwd) # パスワードを暗号化
            conn = get_db_conn()
            try:
                conn.execute('INSERT INTO admins (username, password) VALUES (?, ?)', (user, hashed_pwd))
                conn.commit()
                flash('登録完了！ログインしてください。')
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash('そのユーザー名は既に使われています。')
            finally:
                conn.close()
    return render_template('signup.html')

# --- 管理画面（ログイン必須） ---
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'admin_user' not in session:
        return redirect(url_for('login'))
        
    username = session['admin_user']
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
            conn.execute('UPDATE listeners SET points = points + ? WHERE id = ?', (diff, l_id))
            if diff > 0:
                conn.execute('UPDATE listeners SET total_points = total_points + ? WHERE id = ?', (diff, l_id))
            conn.commit()
            
    listeners = conn.execute('SELECT * FROM listeners WHERE liver_owner = ? ORDER BY name ASC', (username,)).fetchall()
    conn.close()
    return render_template('admin.html', username=username, listeners=listeners)

# --- 共通ログアウト ---
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- その他のルート (index, welcome, board) は前回のまま ---
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        liver_name = request.form.get('liver_name')
        if liver_name:
            session['current_liver'] = liver_name
            return redirect(url_for('welcome', liver_name=liver_name))
    return render_template('index.html')

@app.route('/<liver_name>/welcome', methods=['GET', 'POST'])
def welcome(liver_name):
    session['current_liver'] = liver_name
    lname = request.form.get('listener_name') if request.method == 'POST' else session.get(f'user_{liver_name}')
    
    if request.method == 'POST' and lname:
        session[f'user_{liver_name}'] = lname

    listener_data = None
    if lname:
        conn = get_db_conn()
        listener_data = conn.execute('SELECT * FROM listeners WHERE liver_owner = ? AND name = ?', (liver_name, lname)).fetchone()
        conn.close()

    if listener_data:
        return render_template('mypage.html', liver_name=liver_name, user_handle=listener_data['name'], user_points=listener_data['points'], total_points=listener_data['total_points'], is_verified=True, history=[])
    
    return render_template('welcome.html', liver_name=liver_name)

@app.route('/board.com', methods=['GET', 'POST'])
def board():
    liver_name = session.get('current_liver')
    if not liver_name: return redirect(url_for('index'))
    # ...（掲示板の処理は前回のコードと同じ）
    return render_template('board.html', liver_name=liver_name)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

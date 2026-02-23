import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# --- ログ設定 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'poibox_v25_point_system'

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
        # admins: ライバーログイン用
        conn.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        # listeners: 疑似リスナー管理（ポイント含む）
        conn.execute('''
            CREATE TABLE IF NOT EXISTS listeners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                liver_owner TEXT NOT NULL,
                name TEXT NOT NULL,
                points INTEGER DEFAULT 0,
                UNIQUE(liver_owner, name)
            )
        ''')
        conn.commit()
    except Exception as e:
        logger.error(f"DATABASE INIT ERROR: {e}")
    finally:
        conn.close()

init_db()

# ==========================================
# 1. トップページ
# ==========================================
@app.route('/')
def index():
    return render_template('index.html')

# ==========================================
# 2. リスナー専用ページ (welcome.html)
# ==========================================
@app.route('/<liver_name>/<listener_name>/welcome.com')
def welcome(liver_name, listener_name):
    conn = get_db_conn()
    # リスナー情報を取得
    listener = conn.execute(
        'SELECT * FROM listeners WHERE liver_owner = ? AND name = ?', 
        (liver_name, listener_name)
    ).fetchone()
    conn.close()
    
    if not listener:
        return "リスナーが見つかりません。管理画面で作成してください。", 404
        
    return render_template('welcome.html', liver_name=liver_name, listener=listener)

# ==========================================
# 3. ライバーログイン・新規登録
# ==========================================
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
            except: flash('登録済みです')
            finally: conn.close()
    return render_template('signup.html')

# ==========================================
# 4. 管理画面 (admin) - 疑似リスナー作成とポイント操作
# ==========================================
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    username = session['user_id']
    conn = get_db_conn()

    if request.method == 'POST':
        action = request.form.get('action')
        
        # 疑似リスナー作成
        if action == 'create':
            name = request.form.get('name')
            pts = request.form.get('points', 0)
            try:
                conn.execute('INSERT INTO listeners (liver_owner, name, points) VALUES (?, ?, ?)', 
                             (username, name, pts))
                conn.commit()
                flash(f'リスナー「{name}」を作成しました')
            except: flash('その名前は既に存在します')
            
        # ポイント増減
        elif action == 'update_points':
            l_id = request.form.get('listener_id')
            diff = int(request.form.get('diff', 0))
            conn.execute('UPDATE listeners SET points = points + ? WHERE id = ? AND liver_owner = ?', 
                         (diff, l_id, username))
            conn.commit()

    # リスナー一覧を取得
    listeners = conn.execute('SELECT * FROM listeners WHERE liver_owner = ? ORDER BY name ASC', (username,)).fetchall()
    conn.close()
    
    return render_template('admin.html', username=username, listeners=listeners)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

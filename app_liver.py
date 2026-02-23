import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# --- ログ設定 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'poibox_v16_admin_route'

# --- データベース設定 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'test_pts.db')

def get_db_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """テーブルの存在を保証する"""
    conn = get_db_conn()
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                liver TEXT NOT NULL,
                sender TEXT,
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

# ==========================================
# ルート設定
# ==========================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/welcome')
@app.route('/board', endpoint='board')
def welcome():
    liver_name = request.args.get('u', 'バニラ')
    return render_template('welcome.html', liver_name=liver_name)

# --- ログイン処理 ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        
        conn = get_db_conn()
        admin = conn.execute('SELECT * FROM admins WHERE username = ?', (user,)).fetchone()
        conn.close()
        
        if admin and check_password_hash(admin['password'], pwd):
            session['user_id'] = user
            # ログイン成功後、/admin へ飛ばす
            return redirect(url_for('admin_main'))
        else:
            flash('名前またはパスワードが正しくありません')
            
    return render_template('login.html')

# --- 管理画面（mypageからadminに変更） ---
@app.route('/admin')
def admin_main():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    username = session['user_id']
    share_url = f"{request.host_url}welcome?u={username}"
    
    # 必要に応じてDBからメッセージなどを取得
    messages = []
    with get_db_conn() as conn:
        messages = conn.execute('SELECT * FROM messages WHERE liver = ? ORDER BY id DESC', (username,)).fetchall()
        
    # mypage.html というファイル名のままでも中身が管理画面なら動きますが、
    # もし admin.html にリネームしているならここを 'admin.html' に変えてください
    return render_template('mypage.html', username=username, share_url=share_url, messages=messages)

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

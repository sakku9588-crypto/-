import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# --- ログ設定 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'poibox_v20_url_fix'

# --- データベース設定 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'test_pts.db')

def get_db_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

# テーブル自動作成
def init_db():
    conn = get_db_conn()
    if conn:
        try:
            conn.execute('CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL)')
            conn.execute('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, liver TEXT NOT NULL, sender TEXT, content TEXT NOT NULL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
            conn.commit()
            logger.info("Database initialized.")
        except Exception as e:
            logger.error(f"INIT DB ERROR: {e}")
        finally:
            conn.close()

init_db()

# ==========================================
# ルート設定
# ==========================================

@app.route('/')
def index():
    return render_template('index.html')

# --- 【重要】ここがリスナー用URLの設定です ---
# https://.../test/welcome のような形式に対応させます
@app.route('/<username>/welcome', methods=['GET', 'POST'])
def welcome(username):
    conn = get_db_conn()
    
    # メッセージ投稿（POST）があった場合
    if request.method == 'POST':
        sender = request.form.get('sender', '匿名リスナー')
        content = request.form.get('content')
        if content:
            try:
                conn.execute('INSERT INTO messages (liver, sender, content) VALUES (?, ?, ?)', 
                             (username, sender, content))
                conn.commit()
                flash(f'{username} さんにメッセージを送ったよ！', 'success')
            except Exception as e:
                logger.error(f"投稿エラー: {e}")

    # そのライバー宛の最新メッセージ10件を取得
    messages = []
    if conn:
        messages = conn.execute('SELECT * FROM messages WHERE liver = ? ORDER BY id DESC LIMIT 10', 
                                (username,)).fetchall()
        conn.close()
    
    return render_template('welcome.html', liver_name=username, messages=messages)

# --- ライバー用：ログイン ---
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
        else:
            flash('名前かパスワードが違います')
            
    return render_template('login.html')

# --- ライバー用：管理画面 ---
@app.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    username = session['user_id']
    # リンクの生成方法も変更：/ユーザー名/welcome になるように
    share_url = f"{request.host_url}{username}/welcome"
    
    conn = get_db_conn()
    messages = conn.execute('SELECT * FROM messages WHERE liver = ? ORDER BY id DESC', 
                            (username,)).fetchall()
    conn.close()
    
    return render_template('admin.html', username=username, share_url=share_url, messages=messages)

# --- ライバー用：新規登録 ---
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
                except: flash('その名前は使われています')
    return render_template('signup.html')

# --- ログアウト ---
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

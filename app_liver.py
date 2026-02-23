import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# --- ログ設定 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'poibox_admin_secret_fixed'

# --- データベースの保存場所設定 (Render対策) ---
# データベースは /tmp/ に保存（再起動でリセットされるが、まずは動かすことを優先）
MASTER_DB = '/tmp/master_admin.db'

def get_master_conn():
    conn = sqlite3.connect(MASTER_DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_master_db():
    conn = get_master_conn()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# 起動時にDBを初期化
init_master_db()

# --- ここにあなたの「掲示板」のURLを貼ってください ---
# 例: "https://poibox-board.onrender.com"
BOARD_URL = "あなたの掲示板URLに書き換えてね"

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    username = session['user_id']
    # 掲示板へのリンク（ユーザーIDを付けて配布用にする）
    share_url = f"{BOARD_URL}/?u={username}"
    
    # Renderでは管理画面用のHTML (admin_main.htmlなど) が必要です
    # とりあえず index.html を使う設定にしています
    return render_template('index.html', username=username, share_url=share_url)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        conn = get_master_conn()
        admin = conn.execute('SELECT * FROM admins WHERE username = ?', (user,)).fetchone()
        conn.close()
        
        if admin and check_password_hash(admin['password'], pwd):
            session['user_id'] = user
            return redirect(url_for('index'))
        else:
            flash('ユーザー名かパスワードが違います')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        if user and pwd:
            hashed = generate_password_hash(pwd)
            conn = get_master_conn()
            try:
                conn.execute('INSERT INTO admins (username, password) VALUES (?, ?)', (user, hashed))
                conn.commit()
                return redirect(url_for('login'))
            except:
                flash('そのユーザー名は既に使用されています')
            finally:
                conn.close()
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- Render用起動設定 ---
if __name__ == '__main__':
    # サーバー環境のポートを取得（Render用）
    port = int(os.environ.get("PORT", 5000))
    # ブラウザ自動起動などは一切行わず、シンプルにリッスンする
    app.run(host="0.0.0.0", port=port)

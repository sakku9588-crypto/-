import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# --- 設定 ---
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
app.secret_key = 'poibox_system_secret_v5'

# Renderの保存先設定
MASTER_DB = '/tmp/master_admin.db'
# あなたの「掲示板」の実際のRender URLに書き換えてください
BOARD_URL = "https://your-board-service.onrender.com"

def get_master_conn():
    conn = sqlite3.connect(MASTER_DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_master_conn()
    conn.execute('''CREATE TABLE IF NOT EXISTS admins 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 1. 共通の入り口 (ライバーかリスナーか選択)
# ==========================================
@app.route('/')
def index():
    # 最初に templates/index.html を表示する
    return render_template('index.html')

# ==========================================
# 2. リスナー用ルート
# ==========================================
@app.route('/welcome')
def welcome():
    # リスナー向けの説明画面を表示
    return render_template('welcome.html')

# ==========================================
# 3. ライバー用ルート (管理画面ログイン)
# ==========================================
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
            return redirect(url_for('admin_panel'))
        flash('ログイン失敗')
    return render_template('login.html')

@app.route('/admin_panel')
def admin_panel():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    username = session['user_id']
    share_url = f"{BOARD_URL}/?u={username}"
    return render_template('admin_main.html', username=username, share_url=share_url)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user, pwd = request.form.get('username'), request.form.get('password')
        if user and pwd:
            hashed = generate_password_hash(pwd)
            conn = get_master_conn()
            try:
                conn.execute('INSERT INTO admins (username, password) VALUES (?, ?)', (user, hashed))
                conn.commit()
                return redirect(url_for('login'))
            except: flash('このIDは使われています')
            finally: conn.close()
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- Render用起動設定 ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

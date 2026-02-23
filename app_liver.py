import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
app.secret_key = 'poibox_mypage_stable_v12'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'test_pts.db')

def get_db_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

# --- ログイン後のマイページ ---
@app.route('/mypage')
def mypage():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    username = session['user_id']
    conn = get_db_conn()
    
    # ここで test_pts.db からそのライバーに関連するポイントデータ等を取得する想定
    # 今回は例としてメッセージを取得
    messages = conn.execute('SELECT * FROM messages WHERE liver = ? ORDER BY id DESC', (username,)).fetchall()
    conn.close()
    
    # 自分のURL
    share_url = f"{request.host_url}welcome?u={username}"
    
    return render_template('mypage.html', username=username, messages=messages, share_url=share_url)

# --- ログイン処理の修正（mypageへリダイレクト） ---
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
            # ここを admin_panel から mypage に変更！
            return redirect(url_for('mypage'))
        flash('ログイン失敗')
    return render_template('login.html')

# --- 他のルート（welcome, signup, indexなど）は前回のままでOK ---
@app.route('/')
def index(): return render_template('index.html')

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
                except: flash('登録済み')
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

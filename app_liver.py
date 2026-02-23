import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# --- 設定 ---
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
app.secret_key = 'poibox_v7_identify'

# Renderの保存先設定
MASTER_DB = '/tmp/master_admin.db'

def get_master_conn():
    conn = sqlite3.connect(MASTER_DB)
    conn.row_factory = sqlite3.Row
    return conn

# DB初期化
def init_db():
    conn = get_master_conn()
    conn.execute('CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)')
    conn.commit()
    conn.close()

init_db()

# --- 1. 全体の入り口 ---
@app.route('/')
def index():
    return render_template('index.html')

# --- 2. リスナー専用ページ (ここで誰のリスナーか識別する) ---
@app.route('/welcome')
def welcome():
    # URLの「?u=ユーザー名」を読み取る
    liver_name = request.args.get('u', '不明なライバー')
    
    # welcome.html に liver_name を渡して表示する
    return render_template('welcome.html', liver_name=liver_name)

# --- 3. ライバー管理画面 (ログイン前) ---
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

# --- 4. ライバー管理画面 (ログイン後) ---
@app.route('/admin_panel')
def admin_panel():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    username = session['user_id']
    # 自分のURLを生成 (このURLをリスナーに配る)
    # 自分のRenderのURLに書き換えてください
    my_url = request.host_url.rstrip('/') 
    share_url = f"{my_url}/welcome?u={username}"
    
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
            except: flash('ID使用済み')
            finally: conn.close()
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

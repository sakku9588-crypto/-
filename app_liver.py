import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# --- 設定 ---
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
app.secret_key = 'poibox_nekorise_final'

# Renderの書き込み可能フォルダ
MASTER_DB = '/tmp/master_admin.db'

def get_master_conn():
    conn = sqlite3.connect(MASTER_DB)
    conn.row_factory = sqlite3.Row
    return conn

# DB初期化
with get_master_conn() as conn:
    conn.execute('CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)')

# --- 1. トップ画面 (index.html) ---
@app.route('/')
def index():
    return render_template('index.html')

# --- 2. リスナー用ページ ---
@app.route('/welcome')
def welcome():
    liver_name = request.args.get('u')
    if not liver_name:
        return redirect(url_for('index'))
    return render_template('welcome.html', liver_name=liver_name)

# --- 3. ログイン ---
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
        flash('ログイン失敗', 'danger')
    return render_template('login.html')

# --- 4. 管理パネル ---
@app.route('/admin_panel')
def admin_panel():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    username = session['user_id']
    share_url = f"{request.host_url}welcome?u={username}"
    return render_template('admin_main.html', username=username, share_url=share_url)

# --- 5. 新規登録 ---
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

# --- 起動処理 (Render用) ---
if __name__ == '__main__':
    # Renderが指定するポートを自動で読み取る
    port = int(os.environ.get("PORT", 5000))
    # host="0.0.0.0" にしないとタイムアウトします
    app.run(host="0.0.0.0", port=port)

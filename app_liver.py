import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
app.secret_key = 'poibox_test_db_v9'

# --- データベースの場所を指定 ---
# 1. カレントディレクトリにある test.db を探す
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_DB = os.path.join(BASE_DIR, 'test.db')

def get_master_conn():
    # データベースファイルが存在するか確認
    if not os.path.exists(MASTER_DB):
        logging.error(f"データベースファイルが見つかりません: {MASTER_DB}")
    
    conn = sqlite3.connect(MASTER_DB)
    conn.row_factory = sqlite3.Row
    return conn

# 起動時にテーブルがあるかだけ確認（なければ作る）
with get_master_conn() as conn:
    conn.execute('CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)')

# --- ルート設定（前回と同じ） ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/welcome')
def welcome():
    liver_name = request.args.get('u')
    if not liver_name:
        return redirect(url_for('index'))
    return render_template('welcome.html', liver_name=liver_name)

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

@app.route('/admin_panel')
def admin_panel():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    username = session['user_id']
    share_url = f"{request.host_url}welcome?u={username}"
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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

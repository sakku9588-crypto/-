import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'poibox_v30_404_fix'

# DB接続設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'test_pts.db')

def get_db_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

# 1. トップページ
@app.route('/')
def index():
    return render_template('index.html')

# 2. 掲示板 (URL: /ライバー名/board.com)
@app.route('/<liver_name>/board.com', methods=['GET', 'POST'])
def board(liver_name):
    conn = get_db_conn()
    if request.method == 'POST':
        sender = request.form.get('sender', '匿名')
        content = request.form.get('content')
        if content:
            conn.execute('INSERT INTO messages (liver, sender, content) VALUES (?, ?, ?)', (liver_name, sender, content))
            conn.commit()
    messages = conn.execute('SELECT * FROM messages WHERE liver = ? ORDER BY id DESC LIMIT 20', (liver_name,)).fetchall()
    conn.close()
    return render_template('board.html', liver_name=liver_name, messages=messages)

# 3. welcomeページ (URL: /ライバー名/welcome)
@app.route('/<liver_name>/welcome', methods=['GET', 'POST'])
def welcome(liver_name):
    listener_data = None
    if request.method == 'POST':
        lname = request.form.get('listener_name')
        conn = get_db_conn()
        listener_data = conn.execute('SELECT * FROM listeners WHERE liver_owner = ? AND name = ?', (liver_name, lname)).fetchone()
        conn.close()
        if not listener_data:
            flash(f'「{lname}」さんは未登録です')
    return render_template('welcome.html', liver_name=liver_name, listener=listener_data)

# 4. ログイン
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
    return render_template('login.html')

# 5. 管理画面
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session: return redirect(url_for('login'))
    username = session['user_id']
    conn = get_db_conn()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create':
            name, pts = request.form.get('name'), request.form.get('points', 0)
            try:
                conn.execute('INSERT INTO listeners (liver_owner, name, points) VALUES (?, ?, ?)', (username, name, pts))
                conn.commit()
            except: pass
        elif action == 'update_points':
            l_id, diff = request.form.get('listener_id'), int(request.form.get('diff', 0))
            conn.execute('UPDATE listeners SET points = points + ? WHERE id = ?', (diff, l_id))
            conn.commit()
    listeners = conn.execute('SELECT * FROM listeners WHERE liver_owner = ? ORDER BY name ASC', (username,)).fetchall()
    conn.close()
    return render_template('admin.html', username=username, listeners=listeners)

# 6. 新規登録
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
            except: pass
            finally: conn.close()
    return render_template('signup.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

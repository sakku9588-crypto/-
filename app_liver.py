import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'poibox_v19_404_fix'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'test_pts.db')

def get_db_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

# テーブル自動作成
def init_db():
    with get_db_conn() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)')
        conn.execute('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, liver TEXT, sender TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
    logger.info("Database initialized.")

init_db()

@app.route('/')
def index():
    return render_template('index.html')

# リスナー用 (ここが404ならURLを /welcome にしてください)
@app.route('/welcome', methods=['GET', 'POST'])
def welcome():
    liver_name = request.args.get('u', 'バニラ')
    conn = get_db_conn()
    if request.method == 'POST':
        sender = request.form.get('sender', '匿名リスナー')
        content = request.form.get('content')
        if content:
            conn.execute('INSERT INTO messages (liver, sender, content) VALUES (?, ?, ?)', (liver_name, sender, content))
            conn.commit()
    
    messages = conn.execute('SELECT * FROM messages WHERE liver = ? ORDER BY id DESC LIMIT 10', (liver_name,)).fetchall()
    conn.close()
    return render_template('welcome.html', liver_name=liver_name, messages=messages)

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
            return redirect(url_for('admin')) # ここで /admin へ飛ばす
        flash('ログイン失敗')
    return render_template('login.html')

@app.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    username = session['user_id']
    share_url = f"{request.host_url}welcome?u={username}"
    conn = get_db_conn()
    messages = conn.execute('SELECT * FROM messages WHERE liver = ? ORDER BY id DESC', (username,)).fetchall()
    conn.close()
    return render_template('admin.html', username=username, share_url=share_url, messages=messages)

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

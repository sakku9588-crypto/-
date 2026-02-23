import os
import re
import threading
import sqlite3
import logging
import time
import webbrowser
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# --- 設定：ここを自分のRenderのURLに書き換えてください ---
RENDER_URL = "https://あなたのサイト名.onrender.com" 

# --- ログ設定 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'poibox_ultimate_secret_key_fixed_v4'

# --- 実行環境のパス制御 ---
import sys
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    app.template_folder = template_folder
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MASTER_DB = os.path.join(BASE_DIR, 'master_admin.db')

# --- DB接続関数 ---
def get_master_conn():
    conn = sqlite3.connect(MASTER_DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_master_db():
    conn = get_master_conn()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    ''')
    conn.commit()
    conn.close()

# --- ルート定義 ---

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    username = session['user_id']
    # ネット公開用のURLを作成
    share_url = f"{RENDER_URL}/?u={username}"
    
    return render_template('index.html', username=username, share_url=share_url)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user, pwd = request.form.get('username'), request.form.get('password')
        conn = get_master_conn()
        admin = conn.execute('SELECT * FROM admins WHERE username = ?', (user,)).fetchone()
        conn.close()
        if admin and check_password_hash(admin['password'], pwd):
            session['user_id'] = user
            return redirect(url_for('index'))
        else:
            flash('ユーザー名またはパスワードが違います', 'danger')
    return render_template('login.html')

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
            except:
                flash('そのIDは既に使用されています', 'danger')
            finally:
                conn.close()
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- 起動処理 ---
def open_browser():
    """サーバー起動を少し待ってからブラウザを開く"""
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == '__main__':
    init_master_db()
    
    # ブラウザ自動起動（手元のPC用なのでこれは残してOK）
    threading.Thread(target=open_browser).start()
    
    # 管理画面は手元で動かすのでポートを8000とかに変えておくとapp.pyと衝突しません
    app.run(debug=False, port=8000)

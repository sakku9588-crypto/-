import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
app.secret_key = 'poibox_vanilla_test'

# データベースのパス（GitHubから送られたファイルを直接指定）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'test_pts.db')

def get_db_conn():
    # check_same_thread=False は SQLite を Web で使う際のおまじない
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# テーブルがなければ作成（バニラさんのログイン用）
with get_db_conn() as conn:
    conn.execute('CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)')
    # ここにポイント保存用テーブルなどが無ければ追加
    conn.execute('CREATE TABLE IF NOT EXISTS points (id INTEGER PRIMARY KEY AUTOINCREMENT, user_name TEXT, pts INTEGER)')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/welcome')
def welcome():
    # バニラ専用モード
    liver_name = "バニラ"
    return render_template('welcome.html', liver_name=liver_name)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        with get_db_conn() as conn:
            admin = conn.execute('SELECT * FROM admins WHERE username = ?', (user,)).fetchone()
            if admin and check_password_hash(admin['password'], pwd):
                session['user_id'] = user
                return redirect(url_for('admin_panel'))
        flash('ログイン失敗')
    return render_template('login.html')

@app.route('/admin_panel')
def admin_panel():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('admin_main.html', username=session['user_id'])

# --- データを書き込むテスト用のルート ---
@app.route('/add_test_pts')
def add_test_pts():
    # 読み書きのテスト：アクセスするとポイントが増える
    with get_db_conn() as conn:
        conn.execute('INSERT INTO points (user_name, pts) VALUES (?, ?)', ("バニラ", 100))
        conn.commit()
    return "DBに書き込みました！"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

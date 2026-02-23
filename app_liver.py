import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
app.secret_key = 'poibox_v14_fix'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'test_pts.db')

def get_db_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('index.html')

# エラー対策：'board'という名前でもアクセスできるように設定
@app.route('/welcome', endpoint='welcome')
@app.route('/board', endpoint='board')
def welcome():
    liver_name = request.args.get('u', 'バニラ')
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
                return redirect(url_for('mypage'))
        flash('ログイン失敗')
    return render_template('login.html')

@app.route('/mypage')
def mypage():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    username = session['user_id']
    share_url = f"{request.host_url}welcome?u={username}"
    return render_template('mypage.html', username=username, share_url=share_url)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
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

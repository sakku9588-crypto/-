import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# --- ログ設定 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'poibox_v13_stable'

# --- データベース設定 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'test_pts.db')

def get_db_conn():
    """DB接続。エラーが出た際にログに残す。"""
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f"DATABASE CONNECTION ERROR: {e}")
        return None

# DB初期化（テーブルがなければ作る）
def init_db():
    conn = get_db_conn()
    if conn:
        try:
            conn.execute('CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL)')
            conn.execute('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, liver TEXT NOT NULL, sender TEXT, content TEXT NOT NULL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
            conn.commit()
        except Exception as e:
            logger.error(f"INIT DB ERROR: {e}")
        finally:
            conn.close()

init_db()

# --- ルート設定 ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/welcome')
def welcome():
    liver_name = request.args.get('u', 'バニラ')
    return render_template('welcome.html', liver_name=liver_name)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        conn = get_db_conn()
        if conn:
            admin = conn.execute('SELECT * FROM admins WHERE username = ?', (user,)).fetchone()
            conn.close()
            if admin and check_password_hash(admin['password'], pwd):
                session['user_id'] = user
                # ログイン成功したら mypage へ飛ばす
                return redirect(url_for('mypage'))
        flash('名前かパスワードが違います')
    return render_template('login.html')

@app.route('/mypage')
def mypage():
    # ログインしていない場合はログイン画面へ
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    username = session['user_id']
    conn = get_db_conn()
    messages = []
    if conn:
        try:
            messages = conn.execute('SELECT * FROM messages WHERE liver = ? ORDER BY id DESC', (username,)).fetchall()
        except Exception as e:
            logger.error(f"FETCH MESSAGES ERROR: {e}")
        finally:
            conn.close()
            
    share_url = f"{request.host_url}welcome?u={username}"
    return render_template('mypage.html', username=username, messages=messages, share_url=share_url)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        if user and pwd:
            hashed = generate_password_hash(pwd)
            conn = get_db_conn()
            try:
                conn.execute('INSERT INTO admins (username, password) VALUES (?, ?)', (user, hashed))
                conn.commit()
                return redirect(url_for('login'))
            except Exception as e:
                flash('その名前は使われています')
            finally:
                conn.close()
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

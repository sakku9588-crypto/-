import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# --- ログ出力（エラーの原因をRenderのLogsに表示させるため） ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'poibox_vanilla_stable_v10'

# --- データベースの絶対パスを確実に取得 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'test_pts.db')

def get_db_conn():
    # Render環境でエラーになりにくい設定で接続
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f"Database Connection Error: {e}")
        return None

# --- 起動時にDBとテーブルをチェック ---
def init_db():
    conn = get_db_conn()
    if conn:
        try:
            conn.execute('CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)')
            conn.commit()
            logger.info("Database initialized successfully.")
        except Exception as e:
            logger.error(f"Database Init Error: {e}")
        finally:
            conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/welcome')
def welcome():
    liver_name = "バニラ"
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
                return redirect(url_for('admin_panel'))
        flash('ログイン失敗')
    return render_template('login.html')

@app.route('/admin_panel')
def admin_panel():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('admin_main.html', username=session['user_id'])

# --- Render専用起動設定 ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    # debug=False にして安定性を高める
    app.run(host="0.0.0.0", port=port, debug=False)

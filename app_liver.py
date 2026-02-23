import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# --- ログ設定 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'poibox_v15_db_fix'

# --- データベース設定 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'test_pts.db')

def get_db_conn():
    """データベース接続。ファイルがなければ新しく作成される。"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """テーブルが絶対に存在するように強制作成する"""
    conn = get_db_conn()
    try:
        # adminsテーブル（ログイン用）
        conn.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        # messagesテーブル（掲示板用）
        conn.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                liver TEXT NOT NULL,
                sender TEXT,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        logger.info("Database tables verified/created.")
    except Exception as e:
        logger.error(f"DATABASE INIT ERROR: {e}")
    finally:
        conn.close()

# アプリ起動時に必ずテーブル作成を実行
init_db()

# ==========================================
# ルート設定
# ==========================================

@app.route('/')
def index():
    return render_template('index.html')

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
        
        conn = get_db_conn()
        try:
            # ここでエラーが起きていたので、安全策を講じる
            admin = conn.execute('SELECT * FROM admins WHERE username = ?', (user,)).fetchone()
            if admin and check_password_hash(admin['password'], pwd):
                session['user_id'] = user
                return redirect(url_for('mypage'))
            else:
                flash('名前またはパスワードが正しくありません')
        except sqlite3.OperationalError as e:
            logger.error(f"Login DB Error: {e}")
            flash('システムエラー：管理者に連絡してください')
        finally:
            conn.close()
            
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
            conn = get_db_conn()
            try:
                conn.execute('INSERT INTO admins (username, password) VALUES (?, ?)', (user, hashed))
                conn.commit()
                flash('登録が完了しました！ログインしてください。')
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash('その名前は既に使用されています。')
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

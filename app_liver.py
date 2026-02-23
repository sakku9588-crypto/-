import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# --- ログ設定 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'poibox_vanilla_full_v11'

# --- データベース設定 ---
# プログラムと同じ場所にある test_pts.db を確実に指定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'test_pts.db')

def get_db_conn():
    """データベース接続を取得。SQLiteの同時接続エラーを防ぐ設定。"""
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f"DB接続エラー: {e}")
        return None

def init_db():
    """必要なテーブル（管理用とメッセージ用）がなければ作成"""
    conn = get_db_conn()
    if conn:
        try:
            # ライバー管理用テーブル
            conn.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL
                )
            ''')
            # 掲示板メッセージ用テーブル
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
            logger.info("DBとテーブルの準備が完了しました。")
        except Exception as e:
            logger.error(f"DB初期化エラー: {e}")
        finally:
            conn.close()

# 起動時にDB初期化を実行
init_db()

# ==========================================
# 1. トップページ (index.html)
# ==========================================
@app.route('/')
def index():
    return render_template('index.html')

# ==========================================
# 2. リスナー用：歓迎ページ (welcome.html)
# ==========================================
@app.route('/welcome', methods=['GET', 'POST'])
def welcome():
    # 現在は「バニラ」さん固定モード
    liver_name = "バニラ"
    conn = get_db_conn()
    
    # メッセージの投稿処理
    if request.method == 'POST':
        sender = request.form.get('sender', '匿名リスナー')
        content = request.form.get('content')
        if content:
            try:
                conn.execute('INSERT INTO messages (liver, sender, content) VALUES (?, ?, ?)', 
                             (liver_name, sender, content))
                conn.commit()
                flash('メッセージを送信しました！', 'success')
            except Exception as e:
                logger.error(f"投稿エラー: {e}")
                flash('送信に失敗しました。', 'danger')

    # メッセージ一覧の取得（最新10件）
    messages = conn.execute('SELECT * FROM messages WHERE liver = ? ORDER BY id DESC LIMIT 10', 
                            (liver_name,)).fetchall()
    conn.close()
    
    return render_template('welcome.html', liver_name=liver_name, messages=messages)

# ==========================================
# 3. ライバー用：ログイン (login.html)
# ==========================================
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
            return redirect(url_for('admin_panel'))
        else:
            flash('名前またはパスワードが違います', 'danger')
            
    return render_template('login.html')

# ==========================================
# 4. ライバー用：管理パネル (admin_main.html)
# ==========================================
@app.route('/admin_panel')
def admin_panel():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    username = session['user_id']
    conn = get_db_conn()
    
    # 自分宛のメッセージをすべて取得
    my_messages = conn.execute('SELECT * FROM messages WHERE liver = ? ORDER BY id DESC', 
                               (username,)).fetchall()
    conn.close()
    
    # リスナー配布用のURL
    share_url = f"{request.host_url}welcome"
    
    return render_template('admin_main.html', username=username, messages=my_messages, share_url=share_url)

# ==========================================
# 5. ライバー用：新規登録 (signup.html)
# ==========================================
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
                flash('登録完了！ログインしてください。', 'success')
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash('その名前は既に使われています。', 'warning')
            except Exception as e:
                logger.error(f"登録エラー: {e}")
                flash('エラーが発生しました。', 'danger')
            finally:
                conn.close()
    return render_template('signup.html')

# ==========================================
# 6. ログアウト
# ==========================================
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- Render 起動設定 ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# --- ログ設定 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# セッション暗号化用のキー
app.secret_key = 'poibox_v18_full_listener_support'

# --- データベース設定 ---
# 実行ファイルと同じディレクトリにある test_pts.db を指定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'test_pts.db')

def get_db_conn():
    """SQLiteデータベースへの接続を取得します。"""
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f"DATABASE CONNECTION ERROR: {e}")
        return None

def init_db():
    """起動時に必要なテーブル（admins, messages）がなければ作成します。"""
    conn = get_db_conn()
    if conn:
        try:
            # ライバーのログイン情報を管理するテーブル
            conn.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL
                )
            ''')
            # リスナーからのメッセージを管理するテーブル
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
            logger.info("Database tables are ready.")
        except Exception as e:
            logger.error(f"DATABASE INIT ERROR: {e}")
        finally:
            conn.close()

# アプリ起動時にデータベースを初期化
init_db()

# ==========================================
# 1. トップページ
# ==========================================
@app.route('/')
def index():
    return render_template('index.html')

# ==========================================
# 2. リスナー用ページ (掲示板)
# ==========================================
@app.route('/welcome', methods=['GET', 'POST'])
@app.route('/board', endpoint='board', methods=['GET', 'POST'])
def welcome():
    # URLパラメータ ?u=名前 から対象のライバーを特定。デフォルトは「バニラ」
    liver_name = request.args.get('u', 'バニラ')
    
    conn = get_db_conn()
    
    # メッセージの投稿があった場合
    if request.method == 'POST':
        sender = request.form.get('sender', '匿名リスナー')
        content = request.form.get('content')
        if content:
            try:
                conn.execute(
                    'INSERT INTO messages (liver, sender, content) VALUES (?, ?, ?)', 
                    (liver_name, sender, content)
                )
                conn.commit()
                flash(f'{liver_name} さんにメッセージを送信しました！', 'success')
            except Exception as e:
                logger.error(f"POST ERROR: {e}")
                flash('送信に失敗しました。', 'danger')

    # 表示用に最新のメッセージ10件を取得
    messages = []
    if conn:
        messages = conn.execute(
            'SELECT * FROM messages WHERE liver = ? ORDER BY id DESC LIMIT 10', 
            (liver_name,)
        ).fetchall()
        conn.close()
    
    return render_template('welcome.html', liver_name=liver_name, messages=messages)

# ==========================================
# 3. ライバー用：ログイン
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        
        conn = get_db_conn()
        admin_user = None
        if conn:
            admin_user = conn.execute('SELECT * FROM admins WHERE username = ?', (user,)).fetchone()
            conn.close()
        
        if admin_user and check_password_hash(admin_user['password'], pwd):
            session['user_id'] = user
            # ログイン成功後、/admin ルートへリダイレクト
            return redirect(url_for('admin'))
        else:
            flash('ユーザー名またはパスワードが正しくありません', 'danger')
            
    return render_template('login.html')

# ==========================================
# 4. ライバー用：管理画面 (URL: /admin)
# ==========================================
@app.route('/admin')
def admin():
    # ログインチェック
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    username = session['user_id']
    share_url = f"{request.host_url}welcome?u={username}"
    
    # 自分宛のメッセージを全件取得
    messages = []
    conn = get_db_conn()
    if conn:
        messages = conn.execute(
            'SELECT * FROM messages WHERE liver = ? ORDER BY id DESC', 
            (username,)
        ).fetchall()
        conn.close()
    
    # admin.html を表示
    return render_template('admin.html', username=username, share_url=share_url, messages=messages)

# ==========================================
# 5. ライバー用：新規登録
# ==========================================
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        
        if user and pwd:
            hashed_pwd = generate_password_hash(pwd)
            conn = get_db_conn()
            if conn:
                try:
                    conn.execute('INSERT INTO admins (username, password) VALUES (?, ?)', (user, hashed_pwd))
                    conn.commit()
                    flash('登録が完了しました。ログインしてください。', 'success')
                    return redirect(url_for('login'))
                except sqlite3.IntegrityError:
                    flash('そのユーザー名は既に使用されています。', 'warning')
                except Exception as e:
                    logger.error(f"SIGNUP ERROR: {e}")
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
    flash('ログアウトしました。', 'info')
    return redirect(url_for('index'))

# --- Render 起動設定 ---
if __name__ == '__main__':
    # Render 等の環境変数 PORT があれば使用、なければ 5000
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

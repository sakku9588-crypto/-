import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# --- ログ設定 ---
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
app.secret_key = 'poibox_test_pts_secret'

# --- データベースの場所を指定 ---
# GitHubからデプロイされた「test_pts.db」を直接見に行く設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'test_pts.db')

def get_db_conn():
    """データベースへの接続を取得"""
    if not os.path.exists(DB_PATH):
        logging.error(f"FATAL: {DB_PATH} が見つかりません！")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """必要なテーブル（admins）がなければ作成"""
    try:
        with get_db_conn() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL
                )
            ''')
            conn.commit()
    except Exception as e:
        logging.error(f"DB初期化エラー: {e}")

# 起動時にチェック
init_db()

# ==========================================
# 1. 共通の入り口 (index.html)
# ==========================================
@app.route('/')
def index():
    return render_template('index.html')

# ==========================================
# 2. リスナー用：ライバー識別ページ
# ==========================================
@app.route('/welcome')
def welcome():
    # URLの ?u=名前 を取得
    liver_name = request.args.get('u')
    if not liver_name:
        return redirect(url_for('index'))
    
    # ここで liver_name を使って test_pts.db から
    # そのライバー専用のポイントデータなどを抽出する処理が書けます
    return render_template('welcome.html', liver_name=liver_name)

# ==========================================
# 3. ライバー用：ログイン
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        
        try:
            conn = get_db_conn()
            admin = conn.execute('SELECT * FROM admins WHERE username = ?', (user,)).fetchone()
            conn.close()
            
            if admin and check_password_hash(admin['password'], pwd):
                session['user_id'] = user
                return redirect(url_for('admin_panel'))
            else:
                flash('名前またはパスワードが違います', 'danger')
        except Exception as e:
            flash(f'エラーが発生しました: {e}', 'danger')
            
    return render_template('login.html')

# ==========================================
# 4. ライバー用：管理パネル
# ==========================================
@app.route('/admin_panel')
def admin_panel():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    username = session['user_id']
    # リスナー配布用のURLを生成
    share_url = f"{request.host_url}welcome?u={username}"
    
    return render_template('admin_main.html', username=username, share_url=share_url)

# ==========================================
# 5. 新規登録 (signup)
# ==========================================
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        
        if user and pwd:
            hashed = generate_password_hash(pwd)
            try:
                conn = get_db_conn()
                conn.execute('INSERT INTO admins (username, password) VALUES (?, ?)', (user, hashed))
                conn.commit()
                conn.close()
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash('その名前は既に登録されています', 'warning')
            except Exception as e:
                flash(f'登録エラー: {e}', 'danger')
                
    return render_template('signup.html')

# --- 起動設定 ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

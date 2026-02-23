import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# --- ログ設定 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# セッション暗号化キー（Render再起動でログアウトしないよう固定が推奨）
app.secret_key = 'poibox_nekorise_v8_secret'

# --- データベースの保存場所設定 (Render対応) ---
# Renderでは /tmp/ フォルダが書き込み可能です
MASTER_DB = '/tmp/master_admin.db'

def get_master_conn():
    conn = sqlite3.connect(MASTER_DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """データベースとテーブルの初期化"""
    conn = get_master_conn()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# サーバー起動時にDBを準備
init_db()

# ==========================================
# 1. 共通の入り口 (index.html)
# ==========================================
@app.route('/')
def index():
    # 提供いただいたデザインのHTMLを表示
    return render_template('index.html')

# ==========================================
# 2. リスナー用ページ (welcome.html)
# ==========================================
@app.route('/welcome')
def welcome():
    # index.htmlのJavaScriptから送られてきた「u=ライバー名」を取得
    liver_name = request.args.get('u')
    
    if not liver_name:
        # 名前が入力されていなければトップへ戻す
        return redirect(url_for('index'))
    
    # welcome.html を表示し、ライバーの名前を渡す
    return render_template('welcome.html', liver_name=liver_name)

# ==========================================
# 3. ライバー用：ログイン画面
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        
        conn = get_master_conn()
        admin = conn.execute('SELECT * FROM admins WHERE username = ?', (user,)).fetchone()
        conn.close()
        
        if admin and check_password_hash(admin['password'], pwd):
            session['user_id'] = user
            return redirect(url_for('admin_panel'))
        else:
            flash('名前またはパスワードが正しくありません', 'danger')
            
    return render_template('login.html')

# ==========================================
# 4. ライバー用：管理パネル
# ==========================================
@app.route('/admin_panel')
def admin_panel():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    username = session['user_id']
    # リスナーに配るための自分専用URLを生成
    # 例: https://アプリ名.onrender.com/welcome?u=ユーザー名
    share_url = f"{request.host_url}welcome?u={username}"
    
    return render_template('admin_main.html', username=username, share_url=share_url)

# ==========================================
# 5. ライバー用：新規登録
# ==========================================
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        
        if user and pwd:
            hashed = generate_password_hash(pwd)
            conn = get_master_conn()
            try:
                conn.execute('INSERT INTO admins (username, password) VALUES (?, ?)', (user, hashed))
                conn.commit()
                flash('登録が完了しました。ログインしてください。', 'success')
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash('その名前は既に使われています', 'danger')
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

# --- Render用 起動設定 ---
if __name__ == '__main__':
    # Renderから指定されるポート番号を取得（デフォルトは5000）
    port = int(os.environ.get("PORT", 5000))
    # 0.0.0.0 で外部からのアクセスを許可して起動
    app.run(host="0.0.0.0", port=port)

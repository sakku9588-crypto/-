import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# --- 設定 ---
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
app.secret_key = 'poibox_vanilla_secure_key'

# --- データベース設定 ---
# GitHubからデプロイされた「test_pts.db」を直接読み書きします
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'test_pts.db')

def get_db_conn():
    """データベース接続（test_pts.db）"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """管理用テーブルの準備"""
    with get_db_conn() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        # ここに掲示板用のテーブル（例: messages）がなければ、それも作る設定を追加できます
    conn.close()

# 起動時に実行
init_db()

# ==========================================
# 1. 入り口 (index.html)
# ==========================================
@app.route('/')
def index():
    # 今回は「バニラ専用」なので、そのままログインか歓迎ページへ誘導
    return render_template('index.html')

# ==========================================
# 2. リスナー用：バニラさん歓迎ページ (welcome.html)
# ==========================================
@app.route('/welcome')
def welcome():
    # 今は固定で「バニラ」さんとして扱う
    liver_name = "バニラ"
    
    # test_pts.db からバニラさん宛のメッセージなどを取得するコードを今後ここに追加します
    return render_template('welcome.html', liver_name=liver_name)

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
            flash('名前またはパスワードが違います')
            
    return render_template('login.html')

# ==========================================
# 4. ライバー用：管理パネル (admin_main.html)
# ==========================================
@app.route('/admin_panel')
def admin_panel():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    username = session['user_id']
    # リスナー配布用のURLを表示
    share_url = f"{request.host_url}welcome"
    
    return render_template('admin_main.html', username=username, share_url=share_url)

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
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash('その名前は登録済みです')
            finally:
                conn.close()
    return render_template('signup.html')

# ==========================================
# 起動設定 (Render専用)
# ==========================================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

import os
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

# ログ設定：エラー発生時に原因を特定しやすくします
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'poibox_v38_ultimate_final'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'test_pts.db')

def get_db_conn():
    """データベース接続（WALモードで同時アクセスを高速化）"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL;') 
    return conn

def init_db():
    """データベースの自動作成・修復（502エラー対策）"""
    conn = get_db_conn()
    try:
        # 管理者テーブル
        conn.execute('CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)')
        # リスナーテーブル（ポイント・累計ポイント）
        conn.execute('CREATE TABLE IF NOT EXISTS listeners (id INTEGER PRIMARY KEY AUTOINCREMENT, liver_owner TEXT, name TEXT, points INTEGER DEFAULT 0, total_points INTEGER DEFAULT 0, UNIQUE(liver_owner, name))')
        # 掲示板テーブル（親ID・いいね追加）
        conn.execute('''CREATE TABLE IF NOT EXISTS messages 
                        (id INTEGER PRIMARY KEY AUTOINCREMENT, liver TEXT, sender TEXT, content TEXT, 
                         parent_id INTEGER DEFAULT NULL, likes INTEGER DEFAULT 0, 
                         timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        
        # 既存データベースに新カラム（total_points, parent_id, likes）がない場合は自動追加
        cursor = conn.execute("PRAGMA table_info(listeners)")
        cols = [c[1] for c in cursor.fetchall()]
        if 'total_points' not in cols:
            conn.execute('ALTER TABLE listeners ADD COLUMN total_points INTEGER DEFAULT 0')
            
        cursor = conn.execute("PRAGMA table_info(messages)")
        cols = [c[1] for c in cursor.fetchall()]
        if 'parent_id' not in cols:
            conn.execute('ALTER TABLE messages ADD COLUMN parent_id INTEGER DEFAULT NULL')
        if 'likes' not in cols:
            conn.execute('ALTER TABLE messages ADD COLUMN likes INTEGER DEFAULT 0')

        conn.commit()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Database Init Error: {e}")
    finally:
        conn.close()

init_db()

# --- 1. トップページ ---
@app.route('/')
def index():
    return render_template('index.html')

# --- 2. 通帳マイページ (welcome) ---
@app.route('/<liver_name>/welcome', methods=['GET', 'POST'])
def welcome(liver_name):
    listener_data = None
    if request.method == 'POST':
        lname = request.form.get('listener_name')
        conn = get_db_conn()
        listener_data = conn.execute('SELECT * FROM listeners WHERE liver_owner = ? AND name = ?', (liver_name, lname)).fetchone()
        conn.close()
        if not listener_data:
            flash(f'「{lname}」さんは未登録です。')
    return render_template('welcome.html', liver_name=liver_name, listener=listener_data)

# --- 3. 掲示板 (返信・いいね・登録者制限) ---
@app.route('/<liver_name>/board.com', methods=['GET', 'POST'])
def board(liver_name):
    conn = get_db_conn()
    if request.method == 'POST':
        action = request.form.get('action')
        sender = request.form.get('sender', '').strip()

        # 【仕様】登録者チェック：リスナーテーブルに名前があるか確認
        listener = conn.execute('SELECT * FROM listeners WHERE liver_owner = ? AND name = ?', (liver_name, sender)).fetchone()
        
        if not listener:
            flash(f'「{sender}」さんは登録されていません。通帳を作ってから書き込んでね！')
            conn.close()
            return redirect(url_for('board', liver_name=liver_name))

        # いいね処理
        if action == 'like':
            msg_id = request.form.get('message_id')
            conn.execute('UPDATE messages SET likes = likes + 1 WHERE id = ?', (msg_id,))
            conn.commit()
        
        # 投稿・返信処理
        else:
            content = request.form.get('content')
            parent_id = request.form.get('parent_id')
            if content:
                conn.execute('INSERT INTO messages (liver, sender, content, parent_id) VALUES (?, ?, ?, ?)', 
                             (liver_name, sender, content, parent_id if parent_id else None))
                conn.commit()
        
        conn.close()
        return redirect(url_for('board', liver_name=liver_name))

    # 表示用データ取得
    messages = conn.execute('SELECT * FROM messages WHERE liver = ? ORDER BY id ASC', (liver_name,)).fetchall()
    conn.close()
    
    # メイン投稿と返信を分離して渡す
    main_posts = [m for m in messages if m['parent_id'] is None]
    replies = [m for m in messages if m['parent_id'] is not None]
    
    return render_template('board.html', liver_name=liver_name, main_posts=main_posts, replies=replies)

# --- 4. ライバー管理画面 (ログイン・ポイント操作) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user, pwd = request.form.get('username'), request.form.get('password')
        conn = get_db_conn()
        admin = conn.execute('SELECT * FROM admins WHERE username = ?', (user,)).fetchone()
        conn.close()
        if admin and check_password_hash(admin['password'], pwd):
            session['user_id'] = user
            return redirect(url_for('admin'))
        flash('ログイン失敗')
    return render_template('login.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session: return redirect(url_for('login'))
    username = session['user_id']
    conn = get_db_conn()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create':
            name, pts = request.form.get('name'), int(request.form.get('points', 0))
            try:
                conn.execute('INSERT INTO listeners (liver_owner, name, points, total_points) VALUES (?, ?, ?, ?)', (username, name, pts, pts))
                conn.commit()
            except: flash('既に存在する名前です。')
        elif action == 'update_points':
            l_id, diff = request.form.get('listener_id'), int(request.form.get('diff', 0))
            if diff > 0: # 加算なら累計も増やす
                conn.execute('UPDATE listeners SET points = points + ?, total_points = total_points + ? WHERE id = ?', (diff, diff, l_id))
            else: # 減算なら現在のポイントのみ
                conn.execute('UPDATE listeners SET points = points + ? WHERE id = ?', (diff, l_id))
            conn.commit()
    
    listeners = conn.execute('SELECT * FROM listeners WHERE liver_owner = ? ORDER BY name ASC', (username,)).fetchall()
    conn.close()
    return render_template('admin.html', username=username, listeners=listeners)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user, pwd = request.form.get('username'), request.form.get('password')
        if user and pwd:
            hashed = generate_password_hash(pwd)
            conn = get_db_conn()
            try:
                conn.execute('INSERT INTO admins (username, password) VALUES (?, ?)', (user, hashed))
                conn.commit()
                return redirect(url_for('login'))
            except: flash('既に使われているユーザー名です。')
            finally: conn.close()
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

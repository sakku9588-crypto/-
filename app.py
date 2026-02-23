import sqlite3
import os
from flask import Flask, render_template, request, session, redirect, url_for

current_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(current_dir, 'templates')

db_path = os.path.join(current_dir, 'sakku01_pts.db')#--ここのDBを変えることで個人用に

app = Flask(__name__, template_folder=template_dir)
app.secret_key = 'sakuneko_no_more_excuses'

def get_db_connection():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # ★ usersテーブルに total_points と is_verified の両方を搭載
    conn.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, handle TEXT UNIQUE, points INTEGER DEFAULT 0, total_points INTEGER DEFAULT 0, is_verified BOOLEAN DEFAULT 0)')
    conn.execute('CREATE TABLE IF NOT EXISTS board (id INTEGER PRIMARY KEY, handle TEXT, message TEXT, parent_id INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    conn.execute('CREATE TABLE IF NOT EXISTS passbook (id INTEGER PRIMARY KEY, handle TEXT, amount INTEGER, reason TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    conn.execute('CREATE TABLE IF NOT EXISTS likes (id INTEGER PRIMARY KEY, post_id INTEGER, handle TEXT)')
    
    # ★ 古いDBからのアップデート用（念のため安全装置）
    try:
        conn.execute("SELECT total_points FROM users LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE users ADD COLUMN total_points INTEGER DEFAULT 0")
        conn.execute("UPDATE users SET total_points = points")
        
    try:
        conn.execute("SELECT is_verified FROM users LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT 0")

    conn.commit()
    conn.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        handle = request.form.get('handle', '').strip().replace('＠', '@').lower()
        if handle:
            session['user_handle'] = handle
            conn = get_db_connection()
            user = conn.execute("SELECT * FROM users WHERE handle = ?", (handle,)).fetchone()
            if not user:
                # ★ 新規登録時：ポイント、累計ポイント、認証フラグをセット
                conn.execute("INSERT INTO users (handle, points, total_points, is_verified) VALUES (?, ?, ?, ?)", (handle, 100, 100, False))
                conn.execute("INSERT INTO passbook (handle, amount, reason) VALUES (?, ?, ?)", (handle, 100, "ポイぼっくすへようこそ！"))
                conn.commit()
            conn.close()
            return redirect(url_for('mypage'))
    return render_template('welcome.html') if 'user_handle' not in session else redirect(url_for('mypage'))

@app.route('/mypage')
def mypage():
    handle = session.get('user_handle')
    if not handle: return redirect(url_for('index'))
    conn = get_db_connection()
    # ★ total_points も取得
    user = conn.execute("SELECT points, total_points, is_verified FROM users WHERE handle = ?", (handle,)).fetchone()
    history = conn.execute("SELECT * FROM passbook WHERE handle = ? ORDER BY created_at DESC", (handle,)).fetchall()
    conn.close()
    
    # ★ テンプレートへ渡す
    return render_template('mypage.html', 
                           user_handle=handle, 
                           user_points=user['points'] if user else 0, 
                           total_points=user['total_points'] if user else 0,
                           is_verified=user['is_verified'] if user else False, 
                           history=history)

@app.route('/board', methods=['GET', 'POST'])
def board():
    handle = session.get('user_handle')
    if not handle: return redirect(url_for('index'))
    
    conn = get_db_connection()
    if request.method == 'POST':
        msg = request.form.get('message', '').strip()
        raw_p_id = request.form.get('parent_id')
        try:
            p_id = int(raw_p_id)
        except (TypeError, ValueError):
            p_id = None
            
        if msg:
            conn.execute("INSERT INTO board (handle, message, parent_id) VALUES (?, ?, ?)", (handle, msg, p_id))
            conn.commit()
            return redirect(url_for('board'))
    
    # ユーザーの is_verified 情報も結合して取得すると掲示板にバッジを出しやすいです
    all_p = conn.execute("""
        SELECT b.*, u.is_verified, 
        (SELECT COUNT(*) FROM likes l WHERE l.post_id = b.id) as like_count 
        FROM board b 
        LEFT JOIN users u ON b.handle = u.handle
    """).fetchall()
    
    main_posts = [p for p in all_p if p['parent_id'] is None]
    replies = [p for p in all_p if p['parent_id'] is not None]
    conn.close()
    
    return render_template('board.html', posts=reversed(main_posts), replies=replies, current_user=handle)

# ★ 監督用の集計名簿も残しておきます
@app.route('/member_list')
def member_list():
    conn = get_db_connection()
    users = conn.execute("SELECT handle, points, total_points, is_verified FROM users ORDER BY handle ASC").fetchall()
    conn.close()
    return render_template('member_list.html', users=users)

@app.route('/like/<int:post_id>')
def like_post(post_id):
    handle = session.get('user_handle')
    if not handle: return redirect(url_for('index'))
    conn = get_db_connection()
    post = conn.execute("SELECT handle FROM board WHERE id = ?", (post_id,)).fetchone()
    if post and post['handle'] != handle:
        already = conn.execute("SELECT 1 FROM likes WHERE post_id = ? AND handle = ?", (post_id, handle)).fetchone()
        if not already:
            conn.execute("INSERT INTO likes (post_id, handle) VALUES (?, ?)", (post_id, handle))
            conn.commit()
    conn.close()
    return redirect(url_for('board'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
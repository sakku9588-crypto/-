import sqlite3
import os
from flask import Flask, render_template, request, session, redirect, url_for

# 保存場所の設定
current_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(current_dir, 'templates')

app = Flask(__name__, template_folder=template_dir)
app.secret_key = 'sakuneko_no_more_excuses'

# --- ここがポイント：ユーザーごとにDBファイルを分ける関数 ---
def get_db_path():
    # URLの最後やセッションからユーザー名を特定する
    # 例: /login?u=user1 のようにアクセスすることを想定
    user_id = request.args.get('u') or session.get('current_db_user') or 'default'
    session['current_db_user'] = user_id
    # /tmp/ に保存（Render対策）しつつ、ファイル名にユーザー名を入れる
    return f"/tmp/{user_id}_pts.db"

def get_db_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, handle TEXT UNIQUE, points INTEGER DEFAULT 0, total_points INTEGER DEFAULT 0, is_verified BOOLEAN DEFAULT 0)')
    conn.execute('CREATE TABLE IF NOT EXISTS board (id INTEGER PRIMARY KEY, handle TEXT, message TEXT, parent_id INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    conn.execute('CREATE TABLE IF NOT EXISTS passbook (id INTEGER PRIMARY KEY, handle TEXT, amount INTEGER, reason TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    conn.execute('CREATE TABLE IF NOT EXISTS likes (id INTEGER PRIMARY KEY, post_id INTEGER, handle TEXT)')
    conn.commit()
    conn.close()

@app.before_request
def auto_init():
    # ページを開くたびに、そのユーザー用のDBがなければ作成する
    init_db()

@app.route('/')
def index():
    # 親から ?u=ユーザー名 で飛ばされてきた場合に備える
    u = request.args.get('u')
    if u:
        session['current_db_user'] = u
    return render_template('welcome.html')

# --- 以下、元のログインや掲示板の処理 ---
@app.route('/login', methods=['POST'])
def login():
    handle = request.form.get('handle')
    if handle:
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE handle = ?", (handle,)).fetchone()
        if not user:
            conn.execute("INSERT INTO users (handle) VALUES (?)", (handle,))
            conn.commit()
        session['user_handle'] = handle
        conn.close()
        return redirect(url_for('mypage'))
    return redirect(url_for('index'))

@app.route('/mypage')
def mypage():
    handle = session.get('user_handle')
    if not handle: return redirect(url_for('index'))
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE handle = ?", (handle,)).fetchone()
    history = conn.execute("SELECT * FROM passbook WHERE handle = ? ORDER BY created_at DESC", (handle,)).fetchall()
    conn.close()
    return render_template('mypage.html', user=user, history=history)

@app.route('/board', methods=['GET', 'POST'])
def board():
    handle = session.get('user_handle')
    if not handle: return redirect(url_for('index'))
    conn = get_db_connection()
    if request.method == 'POST':
        msg = request.form.get('message')
        pid = request.form.get('parent_id')
        if msg:
            conn.execute("INSERT INTO board (handle, message, parent_id) VALUES (?, ?, ?)", (handle, msg, pid))
            conn.commit()
    
    all_p = conn.execute("SELECT b.*, u.is_verified, (SELECT COUNT(*) FROM likes l WHERE l.post_id = b.id) as like_count FROM board b LEFT JOIN users u ON b.handle = u.handle").fetchall()
    main_posts = [p for p in all_p if p['parent_id'] is None]
    replies = [p for p in all_p if p['parent_id'] is not None]
    conn.close()
    return render_template('board.html', posts=reversed(main_posts), replies=replies, current_user=handle)

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
            conn.execute("UPDATE users SET points = points + 1, total_points = total_points + 1 WHERE handle = ?", (post['handle'],))
            conn.commit()
    conn.close()
    return redirect(url_for('board'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

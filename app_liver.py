import os
import psycopg2
from psycopg2.extras import DictCursor
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'poibox_postgres_sakuneko'

# Renderの管理画面で設定する環境変数 'DATABASE_URL' を取得
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_conn():
    # PostgreSQLへの接続（sslmode='require' がRenderでは必須）
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn

def init_db():
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            # PostgreSQLの文法 (SERIAL) に微調整
            cur.execute('CREATE TABLE IF NOT EXISTS admins (id SERIAL PRIMARY KEY, username TEXT UNIQUE, password TEXT)')
            cur.execute('CREATE TABLE IF NOT EXISTS listeners (id SERIAL PRIMARY KEY, liver_owner TEXT, name TEXT, points INTEGER DEFAULT 0, total_points INTEGER DEFAULT 0, UNIQUE(liver_owner, name))')
            cur.execute('''CREATE TABLE IF NOT EXISTS messages 
                            (id SERIAL PRIMARY KEY, liver TEXT, handle TEXT, message TEXT, 
                             parent_id INTEGER DEFAULT NULL, like_count INTEGER DEFAULT 0, 
                             timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
            conn.commit()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/<liver_name>/welcome', methods=['GET', 'POST'])
def welcome(liver_name):
    if request.method == 'POST':
        lname = request.form.get('listener_name')
        if lname: session[f'user_{liver_name}'] = lname
    lname = session.get(f'user_{liver_name}')
    listener_data = None
    if lname:
        with get_db_conn() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute('SELECT * FROM listeners WHERE liver_owner = %s AND name = %s', (liver_name, lname))
                listener_data = cur.fetchone()
    if listener_data:
        return render_template('mypage.html', liver_name=liver_name, user_handle=listener_data['name'], user_points=listener_data['points'], total_points=listener_data['total_points'], is_verified=True, history=[])
    return render_template('welcome.html', liver_name=liver_name)

@app.route('/<liver_name>/board', methods=['GET', 'POST'])
def board(liver_name):
    current_user = session.get(f'user_{liver_name}')
    if request.method == 'POST':
        msg_text = request.form.get('message')
        parent_id = request.form.get('parent_id')
        if current_user and msg_text:
            pid = int(parent_id) if parent_id and parent_id.isdigit() else None
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute('INSERT INTO messages (liver, handle, message, parent_id) VALUES (%s, %s, %s, %s)', 
                                 (liver_name, current_user, msg_text, pid))
                conn.commit()
        return redirect(url_for('board', liver_name=liver_name))
    
    with get_db_conn() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute('SELECT * FROM messages WHERE liver = %s ORDER BY id ASC', (liver_name,))
            all_msgs = cur.fetchall()
    
    posts = [m for m in all_msgs if m['parent_id'] is None]
    replies = [m for m in all_msgs if m['parent_id'] is not None]
    return render_template('board.html', liver_name=liver_name, posts=posts, replies=replies, current_user=current_user)

@app.route('/like/<int:post_id>')
def like_post(post_id):
    with get_db_conn() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute('SELECT liver FROM messages WHERE id = %s', (post_id,))
            msg = cur.fetchone()
            if msg:
                cur.execute('UPDATE messages SET like_count = like_count + 1 WHERE id = %s', (post_id,))
                conn.commit()
                return redirect(url_for('board', liver_name=msg['liver']))
    return redirect(url_for('index'))

# --- 管理画面 (PostgreSQL対応) ---
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'admin_user' not in session: return redirect(url_for('login'))
    username = session['admin_user']
    with get_db_conn() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            if request.method == 'POST':
                action = request.form.get('action')
                if action == 'create':
                    name, pts = request.form.get('name'), int(request.form.get('points', 0))
                    try:
                        cur.execute('INSERT INTO listeners (liver_owner, name, points, total_points) VALUES (%s, %s, %s, %s)', (username, name, pts, pts))
                        conn.commit()
                    except: conn.rollback()
                elif action == 'update_points':
                    l_id, diff = request.form.get('listener_id'), int(request.form.get('diff', 0))
                    cur.execute('UPDATE listeners SET points = points + %s WHERE id = %s', (diff, l_id))
                    if diff > 0:
                        cur.execute('UPDATE listeners SET total_points = total_points + %s WHERE id = %s', (diff, l_id))
                    conn.commit()
            cur.execute('SELECT * FROM listeners WHERE liver_owner = %s ORDER BY name ASC', (username,))
            listeners = cur.fetchall()
    return render_template('admin.html', username=username, listeners=listeners)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user, pwd = request.form.get('username'), request.form.get('password')
        with get_db_conn() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute('SELECT * FROM admins WHERE username = %s', (user,))
                admin = cur.fetchone()
                if admin and check_password_hash(admin['password'], pwd):
                    session['admin_user'] = user
                    return redirect(url_for('admin'))
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user, pwd = request.form.get('username'), request.form.get('password')
        if user and pwd:
            hashed = generate_password_hash(pwd)
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    try:
                        cur.execute('INSERT INTO admins (username, password) VALUES (%s, %s)', (user, hashed))
                        conn.commit()
                        return redirect(url_for('login'))
                    except: conn.rollback()
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

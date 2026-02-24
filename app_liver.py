import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from psycopg2.extras import DictCursor
from psycopg2.pool import SimpleConnectionPool
from contextlib import contextmanager

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'default-key-for-dev')

# --- DB接続管理の最適化 ---
DATABASE_URL = os.environ.get('DATABASE_URL')
db_pool = SimpleConnectionPool(1, 10, dsn=DATABASE_URL, sslmode='require')

@contextmanager
def get_db():
    conn = db_pool.getconn()
    try:
        yield conn
    finally:
        db_pool.putconn(conn)

def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute('CREATE TABLE IF NOT EXISTS admins (id SERIAL PRIMARY KEY, username TEXT UNIQUE, password TEXT)')
            cur.execute('CREATE TABLE IF NOT EXISTS listeners (id SERIAL PRIMARY KEY, name TEXT, points INTEGER DEFAULT 0, total_points INTEGER DEFAULT 0, admin_id INTEGER, UNIQUE(name, admin_id))')
            cur.execute('CREATE TABLE IF NOT EXISTS logs (id SERIAL PRIMARY KEY, handle TEXT, amount INTEGER, reason TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, admin_id INTEGER)')
        conn.commit()

init_db()

# --- 共通のDB操作関数（コードの重複を削減） ---
def fetch_query(sql, params=(), one=False):
    with get_db() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchone() if one else cur.fetchall()

# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html', is_logged_in='user_id' in session)

@app.route('/<username>/<listener_name>/welcome.com')
def welcome(username, listener_name):
    sql = "SELECT l.* FROM listeners l JOIN admins a ON l.admin_id = a.id WHERE a.username = %s AND l.name = %s"
    user_data = fetch_query(sql, (username, listener_name), one=True)
    return render_template('welcome.html', user=user_data, admin_name=username) if user_data else ("Not Found", 404)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session: return redirect(url_for('login'))
    uid = session['user_id']
    
    if request.method == 'POST' and request.form.get('action') == 'create':
        name, pts = request.form.get('name'), int(request.form.get('points', 0))
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO listeners (name, points, total_points, admin_id) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING", (name, pts, pts, uid))
            conn.commit()

    q = request.args.get('q', '')
    users = fetch_query(f"SELECT name AS handle, points, total_points, id FROM listeners WHERE admin_id = %s {'AND name LIKE %s' if q else ''} ORDER BY total_points DESC LIMIT 50", [uid, f'%{q}%'] if q else [uid])
    history = fetch_query("SELECT handle, amount, reason, created_at FROM logs WHERE admin_id = %s ORDER BY created_at DESC LIMIT 5", (uid,))
    
    return render_template('admin.html', username=session['username'], users=users, history=history, q=q)

# ... (login/signup/add_points はロジックを維持しつつ get_db を使用)

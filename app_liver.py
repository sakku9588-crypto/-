import os
import psycopg2
from psycopg2 import pool
from psycopg2.extras import DictCursor
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your-secret-key-poibox'

# --- DB接続プール (軽量化の要) ---
DATABASE_URL = os.environ.get('DATABASE_URL')
db_pool = psycopg2.pool.SimpleConnectionPool(1, 10, dsn=DATABASE_URL, sslmode='require')

def get_db_conn():
    return db_pool.getconn()

def release_db_conn(conn):
    db_pool.putconn(conn)

def init_db():
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute('CREATE TABLE IF NOT EXISTS admins (id SERIAL PRIMARY KEY, username TEXT UNIQUE, password TEXT)')
            cur.execute('''CREATE TABLE IF NOT EXISTS listeners (
                id SERIAL PRIMARY KEY, name TEXT, points INTEGER DEFAULT 0, 
                total_points INTEGER DEFAULT 0, admin_id INTEGER, UNIQUE(name, admin_id))''')
            cur.execute('''CREATE TABLE IF NOT EXISTS logs (
                id SERIAL PRIMARY KEY, handle TEXT, amount INTEGER, reason TEXT, 
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, admin_id INTEGER)''')
        conn.commit()
    finally:
        release_db_conn(conn)

init_db()

# --- 1. ここを修正：まず index.html に飛ばす ---
@app.route('/')
def index():
    # ログインしているかどうかを index.html に伝えて表示させる
    is_logged_in = 'user_id' in session
    return render_template('index.html', is_logged_in=is_logged_in)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user, pwd = request.form.get('username'), request.form.get('password')
        if user and pwd:
            conn = get_db_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute('INSERT INTO admins (username, password) VALUES (%s, %s)', (user, generate_password_hash(pwd)))
                conn.commit()
                flash("登録完了！", "success")
                return redirect(url_for('login'))
            except:
                flash("そのIDは使用されています", "danger")
            finally:
                release_db_conn(conn)
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u_in, p_in = request.form.get('username'), request.form.get('password')
        conn = get_db_conn()
        try:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute('SELECT * FROM admins WHERE username = %s', (u_in,))
                user = cur.fetchone()
                if user and check_password_hash(user['password'], p_in):
                    session['user_id'], session['username'] = user['id'], user['username']
                    return redirect(url_for('admin'))
                flash("IDまたはパスワードが違います", "danger")
        finally:
            release_db_conn(conn)
    return render_template('login.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    uid, q = session['user_id'], request.args.get('q', '')
    conn = get_db_conn()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            if request.method == 'POST' and request.form.get('action') == 'create':
                name, pts = request.form.get('name'), int(request.form.get('points', 0))
                cur.execute("INSERT INTO listeners (name, points, total_points, admin_id) VALUES (%s, %s, %s, %s)", (name, pts, pts, uid))
                conn.commit()

            sql = "SELECT name AS handle, points, total_points FROM listeners WHERE admin_id = %s"
            params = [uid]
            if q:
                sql += " AND name LIKE %s"
                params.append(f'%{q}%')
            sql += " ORDER BY total_points DESC LIMIT 50"
            cur.execute(sql, params)
            users = cur.fetchall()

            cur.execute("SELECT handle, amount, reason, created_at FROM logs WHERE admin_id = %s ORDER BY created_at DESC LIMIT 5", (uid,))
            history = cur.fetchall()
    finally:
        release_db_conn(conn)
    return render_template('admin.html', username=session['username'], users=users, history=history, q=q)

@app.route('/add_points', methods=['POST'])
def add_points():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    h, amt, reas = request.form.get('handle'), int(request.form.get('amount', 0)), request.form.get('reason') or "理由なし"
    if request.form.get('op') == 'sub': amt = -amt
    
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            if amt > 0:
                cur.execute("UPDATE listeners SET points=points+%s, total_points=total_points+%s WHERE name=%s AND admin_id=%s", (amt, amt, h, session['user_id']))
            else:
                cur.execute("UPDATE listeners SET points=points+%s WHERE name=%s AND admin_id=%s", (amt, h, session['user_id']))
            cur.execute("INSERT INTO logs (handle, amount, reason, admin_id) VALUES (%s, %s, %s, %s)", (h, amt, reas, session['user_id']))
        conn.commit()
    finally:
        release_db_conn(conn)
    return redirect(url_for('admin', q=request.form.get('current_q', '')))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

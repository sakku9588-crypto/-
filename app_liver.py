import os
import datetime
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import DictCursor
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from contextlib import contextmanager

app = Flask(__name__)
# セキュリティキーは環境変数から取得（なければデフォルト）
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-poibox-2026')

# --- DB接続設定 (postgres:// を postgresql:// に自動変換) ---
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# 接続プールの作成 (sslmode=require はクラウドDBで必須)
try:
    db_pool = SimpleConnectionPool(1, 10, dsn=DATABASE_URL, sslmode='require')
except Exception as e:
    print(f"DB接続エラー: {e}")

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
            cur.execute('''CREATE TABLE IF NOT EXISTS listeners (
                id SERIAL PRIMARY KEY, name TEXT, points INTEGER DEFAULT 0, 
                total_points INTEGER DEFAULT 0, admin_id INTEGER, UNIQUE(name, admin_id))''')
            cur.execute('''CREATE TABLE IF NOT EXISTS logs (
                id SERIAL PRIMARY KEY, handle TEXT, amount INTEGER DEFAULT 0, reason TEXT, 
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, admin_id INTEGER)''')
        conn.commit()

# アプリ起動時にテーブル作成
init_db()

# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html', is_logged_in='user_id' in session)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user, pwd = request.form.get('username'), request.form.get('password')
        if user and pwd:
            try:
                with get_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute('INSERT INTO admins (username, password) VALUES (%s, %s)', 
                                   (user, generate_password_hash(pwd)))
                    conn.commit()
                flash("登録完了！ログインしてください。", "success")
                return redirect(url_for('login'))
            except:
                flash("そのIDは既に使用されています", "danger")
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u_in, p_in = request.form.get('username'), request.form.get('password')
        with get_db() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute('SELECT * FROM admins WHERE username = %s', (u_in,))
                user = cur.fetchone()
                if user and check_password_hash(user['password'], p_in):
                    session['user_id'], session['username'] = user['id'], user['username']
                    return redirect(url_for('admin'))
        flash("IDまたはパスワードが違います", "danger")
    return render_template('login.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session: return redirect(url_for('login'))
    uid = session['user_id']
    
    with get_db() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            # 検索・リスナー一覧取得
            q = request.args.get('q', '')
            sql = "SELECT name AS handle, points, total_points FROM listeners WHERE admin_id = %s"
            params = [uid]
            if q:
                sql += " AND name LIKE %s"
                params.append(f'%{q}%')
            cur.execute(sql + " ORDER BY total_points DESC LIMIT 50", params)
            users = cur.fetchall()

            # 最新ログ取得（今日抽出された人も含む）
            cur.execute("SELECT handle, reason, created_at FROM logs WHERE admin_id = %s ORDER BY created_at DESC LIMIT 10", (uid,))
            history = cur.fetchall()

    return render_template('admin.html', username=session['username'], users=users, history=history, q=q)

# --- ポイぼっくすログ（txt）から取り込む機能 ---
@app.route('/import_logs', methods=['POST'])
def import_logs():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    log_text = request.form.get('log_text', '').strip()
    if not log_text:
        flash("ログが空です", "warning")
        return redirect(url_for('admin'))

    lines = log_text.split('\n')
    uid = session['user_id']
    count = 0

    with get_db() as conn:
        with conn.cursor() as cur:
            for line in lines:
                name = line.strip()
                if name:
                    # リスナー未登録なら登録
                    cur.execute("""
                        INSERT INTO listeners (name, admin_id) VALUES (%s, %s)
                        ON CONFLICT (name, admin_id) DO NOTHING
                    """, (name, uid))
                    # 本日の抽出ログとして保存
                    cur.execute("""
                        INSERT INTO logs (handle, amount, reason, admin_id) 
                        VALUES (%s, 0, '本日抽出', %s)
                    """, (name, uid))
                    count += 1
        conn.commit()
    
    flash(f"{count}名のリスナーを「本日抽出」として記録しました！", "success")
    return redirect(url_for('admin'))

@app.route('/<username>/<listener_name>/welcome.com')
def welcome(username, listener_name):
    with get_db() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("""
                SELECT l.* FROM listeners l 
                JOIN admins a ON l.admin_id = a.id 
                WHERE a.username = %s AND l.name = %s
            """, (username, listener_name))
            user_data = cur.fetchone()
    
    if user_data:
        return render_template('welcome.html', user=user_data, admin_name=username)
    return "リスナーが見つかりませんでした", 404

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    # Renderのポート監視に対応
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

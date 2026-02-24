import os
import psycopg2
from psycopg2.extras import DictCursor
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your-secret-key-poibox' # 本番ではランダムな文字列に変えるのが理想

# データベース接続設定
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_conn():
    # SSL接続が必要な場合は sslmode='require' を付加
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    """データベースの初期化とテーブル作成"""
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            # 管理者テーブル
            cur.execute('''CREATE TABLE IF NOT EXISTS admins (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE,
                password TEXT
            )''')
            # リスナーテーブル (累計ポイントと管理者IDを追加)
            cur.execute('''CREATE TABLE IF NOT EXISTS listeners (
                id SERIAL PRIMARY KEY,
                name TEXT,
                points INTEGER DEFAULT 0,
                total_points INTEGER DEFAULT 0,
                admin_id INTEGER,
                UNIQUE(name, admin_id)
            )''')
            # ログテーブル (操作履歴用)
            cur.execute('''CREATE TABLE IF NOT EXISTS logs (
                id SERIAL PRIMARY KEY,
                handle TEXT,
                amount INTEGER,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                admin_id INTEGER
            )''')
        conn.commit()

# アプリ起動時にテーブルを作成
init_db()

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('admin'))
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        if user and pwd:
            hashed = generate_password_hash(pwd)
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    try:
                        cur.execute('INSERT INTO admins (username, password) VALUES (%s, %s)', (user, hashed))
                        conn.commit()
                        flash("登録完了！ログインしてください", "success")
                        return redirect(url_for('login'))
                    except Exception:
                        conn.rollback()
                        flash("そのIDは既に使われています", "danger")
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_input = request.form.get('username')
        pwd_input = request.form.get('password')
        with get_db_conn() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute('SELECT * FROM admins WHERE username = %s', (user_input,))
                user_data = cur.fetchone()
                if user_data and check_password_hash(user_data['password'], pwd_input):
                    session['user_id'] = user_data['id']
                    session['username'] = user_data['username']
                    return redirect(url_for('admin'))
                else:
                    flash("IDまたはパスワードが間違っています", "danger")
    return render_template('login.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    username = session['username']
    q = request.args.get('q', '')

    with get_db_conn() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            # リスナー作成処理 (admin.htmlの「疑似リスナー新規作成」に対応)
            if request.method == 'POST' and request.form.get('action') == 'create':
                name = request.form.get('name')
                pts = int(request.form.get('points', 0))
                try:
                    cur.execute(
                        "INSERT INTO listeners (name, points, total_points, admin_id) VALUES (%s, %s, %s, %s)",
                        (name, pts, pts, user_id)
                    )
                    conn.commit()
                    flash(f"リスナー {name} を作成しました", "success")
                except Exception:
                    conn.rollback()
                    flash("作成に失敗しました（同名のリスナーがいる可能性があります）", "danger")
                return redirect(url_for('admin'))

            # 表示用データの取得 (users=users というHTMLの変数名に合わせる)
            if q:
                cur.execute("SELECT name AS handle, points, total_points, id FROM listeners WHERE admin_id = %s AND name LIKE %s ORDER BY total_points DESC", (user_id, f'%{q}%'))
            else:
                cur.execute("SELECT name AS handle, points, total_points, id FROM listeners WHERE admin_id = %s ORDER BY total_points DESC", (user_id,))
            users = cur.fetchall()

            # 履歴の取得
            cur.execute("SELECT handle, amount, reason, created_at FROM logs WHERE admin_id = %s ORDER BY created_at DESC LIMIT 10", (user_id,))
            history = cur.fetchall()

    return render_template('admin.html', username=username, users=users, history=history, q=q)

@app.route('/add_points', methods=['POST'])
def add_points():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    handle = request.form.get('handle')
    amount = int(request.form.get('amount', 0))
    reason = request.form.get('reason') or "理由なし"
    op = request.form.get('op')
    current_q = request.form.get('current_q', '')
    user_id = session['user_id']

    if op == 'sub':
        amount = -amount

    with get_db_conn() as conn:
        with conn.cursor() as cur:
            # ポイント更新
            if amount > 0:
                cur.execute("UPDATE listeners SET points = points + %s, total_points = total_points + %s WHERE name = %s AND admin_id = %s", (amount, amount, handle, user_id))
            else:
                cur.execute("UPDATE listeners SET points = points + %s WHERE name = %s AND admin_id = %s", (amount, handle, user_id))
            
            # 履歴保存
            cur.execute("INSERT INTO logs (handle, amount, reason, admin_id) VALUES (%s, %s, %s, %s)", (handle, amount, reason, user_id))
            conn.commit()

    flash(f"{handle}さんに {amount}pts 操作しました", "success")
    return redirect(url_for('admin', q=current_q))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    # Render環境ではポート10000が一般的
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

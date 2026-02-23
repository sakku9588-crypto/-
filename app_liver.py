import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'poibox_secret_key_fixed_v1'

# --- データベースの保存場所設定 (Render対策) ---
# Renderでは /tmp/ フォルダ以外への書き込みが制限されるため変更
def get_db_path(user_id):
    return f'/tmp/sakku01_{user_id}.db'

def init_db(user_id):
    db_path = get_db_path(user_id)
    conn = sqlite3.connect(db_path)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    # URLの末尾にある ?u=ユーザーID を取得
    user_id = request.args.get('u', 'default')
    
    # データベースの準備
    init_db(user_id)
    
    db_path = get_db_path(user_id)
    
    if request.method == 'POST':
        content = request.form.get('content')
        if content:
            conn = sqlite3.connect(db_path)
            conn.execute('INSERT INTO messages (content) VALUES (?)', (content,))
            conn.commit()
            conn.close()
        return redirect(url_for('index', u=user_id))

    # メッセージの読み込み
    conn = sqlite3.connect(db_path)
    messages = conn.execute('SELECT content FROM messages ORDER BY id DESC').fetchall()
    conn.close()
    
    return render_template('index.html', messages=messages, user_id=user_id)

# --- ここが重要：RenderのPort scan timeout対策 ---
if __name__ == '__main__':
    # Renderは環境変数 PORT で指定されたポートで待ち受ける必要がある
    port = int(os.environ.get("PORT", 5000))
    # host="0.0.0.0" にしないと外部（ネット）からアクセスできない
    app.run(host="0.0.0.0", port=port)

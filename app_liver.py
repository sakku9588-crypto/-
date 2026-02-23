import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'poibox_secret_key_fixed_v1'

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
    user_id = request.args.get('u', 'default')
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

    conn = sqlite3.connect(db_path)
    messages = conn.execute('SELECT content FROM messages ORDER BY id DESC').fetchall()
    conn.close()
    
    return render_template('index.html', messages=messages, user_id=user_id)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

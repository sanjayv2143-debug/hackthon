import os
import sqlite3
import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "proofpath_secret_key_123"

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id TEXT UNIQUE,
            name TEXT,
            category TEXT,
            photo TEXT,
            location TEXT,
            description TEXT,
            ai_summary TEXT,
            suggested_department TEXT,
            priority TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    ''')
    cursor.execute("SELECT * FROM admin WHERE username = 'admin'")
    if not cursor.fetchone():
        hashed_pw = generate_password_hash('admin123')
        cursor.execute("INSERT INTO admin (username, password) VALUES (?, ?)", ('admin', hashed_pw))
    conn.commit()
    conn.close()

init_db()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def analyze_with_ollama(description, category):
    prompt = f"""
    Analyze this complaint:
    Category: {category}
    Description: {description}
    Provide response strictly in this format:
    SUMMARY: [1-2 sentence summary]
    DEPT: [Choose ONE: Roads/Public Works Department, Water Supply Department, Sanitation Department, Electrical/Municipal Department, Drainage Department]
    PRIORITY: [Choose ONE: Low, Medium, High]
    """
    try:
        response = requests.post("http://localhost:11434/api/generate", json={
            "model": "llama3.2",
            "prompt": prompt,
            "stream": False
        }, timeout=10)
        if response.status_code == 200:
            text = response.json().get("response", "")
            summary, dept, priority = "Issue reported.", "Municipal Department", "Medium"
            for line in text.split('\n'):
                if line.startswith("SUMMARY:"): summary = line.replace("SUMMARY:", "").strip()
                elif line.startswith("DEPT:"): dept = line.replace("DEPT:", "").strip()
                elif line.startswith("PRIORITY:"): priority = line.replace("PRIORITY:", "").strip()
            return summary, dept, priority
    except Exception as e:
        print("Ollama Error:", e)
    return f"Issue regarding {category}.", "Municipal Department", "Medium"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/report', methods=['GET', 'POST'])
def report():
    if request.method == 'POST':
        name = request.form.get('name', 'Anonymous')
        category = request.form.get('category')
        location = request.form.get('location')
        description = request.form.get('description')
        
        file = request.files.get('photo')
        photo_filename = "default.jpg"
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            photo_filename = filename

        import random
        complaint_id = f"PP-{random.randint(10000, 99999)}"
        summary, dept, priority = analyze_with_ollama(description, category)
        
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO complaints (complaint_id, name, category, photo, location, description, ai_summary, suggested_department, priority, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (complaint_id, name, category, photo_filename, location, description, summary, dept, priority, 'Pending'))
        conn.commit()
        conn.close()
        return redirect(url_for('success', cid=complaint_id))
    return render_template('report.html')

@app.route('/success/<cid>')
def success(cid):
    return render_template('success.html', cid=cid)

@app.route('/track', methods=['GET', 'POST'])
def track():
    complaint = None
    if request.method == 'POST':
        cid = request.form.get('complaint_id').strip()
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM complaints WHERE complaint_id = ?", (cid,))
        complaint = cursor.fetchone()
        conn.close()
    return render_template('track.html', complaint=complaint)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM admin WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        if row and check_password_hash(row[0], password):
            session['admin'] = username
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid credentials", "danger")
    return render_template('admin_login.html')

@app.route('/admin/dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if 'admin' not in session: return redirect(url_for('admin_login'))
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    if request.method == 'POST':
        cid = request.form.get('complaint_id')
        new_dept = request.form.get('department')
        new_status = request.form.get('status')
        cursor.execute("UPDATE complaints SET suggested_department = ?, status = ? WHERE complaint_id = ?", (new_dept, new_status, cid))
        conn.commit()
    cursor.execute("SELECT * FROM complaints ORDER BY id DESC")
    complaints = cursor.fetchall()
    conn.close()
    return render_template('admin_dashboard.html', complaints=complaints)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))

if __name__ == '__main__':
    app.run(debug=False, port=5000)
from flask import Flask, render_template, request, redirect, session, send_from_directory
import os, sqlite3, shutil
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime
# ================= PATH CONFIG =================
PROJECT_DIR = os.getcwd()
TEMPLATE_DIR = os.path.join(PROJECT_DIR, "templates")
STATIC_DIR = os.path.join(PROJECT_DIR, "static")
DB_PATH = os.path.join(PROJECT_DIR, "database.db")
CLOUD_DIR = os.path.join(PROJECT_DIR, "cloud")

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.secret_key = "cloud_secret_key"

# Make get_file_icon available in templates
@app.context_processor
def utility_processor():
    return dict(get_file_icon=get_file_icon)

# ================= LIMITS =================
# Support uploads up to 10GB (max quota limit)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024 * 1024

ALLOWED_EXTENSIONS = {"png","jpg","jpeg","pdf","txt","zip","mp4"}

def allowed_file(filename):
    return "." in filename and \
        filename.rsplit(".",1)[1].lower() in ALLOWED_EXTENSIONS

# ================= DATABASE =================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT,
        quota_mb INTEGER DEFAULT 100
    )
    """)
    # Add quota column if table exists without it
    try:
        c.execute("ALTER TABLE users ADD COLUMN quota_mb INTEGER DEFAULT 100")
    except:
        pass
    c.execute("""
    CREATE TABLE IF NOT EXISTS shares(
    id INTEGER PRIMARY KEY,
    token TEXT,
    filename TEXT,
    owner TEXT
)
""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS logs(
        id INTEGER PRIMARY KEY,
        user TEXT,
        action TEXT,
        time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    admin_pass = generate_password_hash("admin123")
    c.execute(
        "INSERT OR IGNORE INTO users VALUES(NULL,?,?,?,?)",
        ("admin", admin_pass, "admin", 1000)
    )

    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

os.makedirs(CLOUD_DIR, exist_ok=True)

# ================= STORAGE UTILS =================
def get_folder_size(folder):
    """Calculate total size of a folder in MB"""
    total = 0
    if not os.path.exists(folder):
        return 0
    for path, dirs, files in os.walk(folder):
        for f in files:
            fp = os.path.join(path, f)
            if os.path.exists(fp):
                total += os.path.getsize(fp)
    return round(total / (1024 * 1024), 2)

def get_user_storage_info(username):
    """Get storage used and quota for a user"""
    user_folder = os.path.join(CLOUD_DIR, username)
    used = get_folder_size(user_folder)
    
    conn = get_db()
    user = conn.execute("SELECT quota_mb FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    
    quota = user["quota_mb"] if user else 100
    return {"used": used, "quota": quota, "percent": min(100, round((used / quota) * 100, 1)) if quota > 0 else 0}

init_db()

# ================= LOGGING =================
def add_log(user, action):
    conn = get_db()
    conn.execute(
        "INSERT INTO logs(user,action) VALUES(?,?)",
        (user, action)
    )
    conn.commit()
    conn.close()

# ================= LANDING PAGE =================
@app.route("/")
def landing():
    return render_template("landing.html")

# ================= LOGIN =================
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=?",(u,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"],p):
            session["user"]=user["username"]
            session["role"]=user["role"]
            add_log(u,"login")

            if user["role"]=="admin":
                return redirect("/admin")
            return redirect("/dashboard")

    return render_template("login.html")

# ================= REGISTER =================
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        u=request.form["username"]
        p=request.form["password"]

        conn=get_db()
        try:
            conn.execute(
                "INSERT INTO users(username,password,role) VALUES(?,?,?)",
                (u,generate_password_hash(p),"user")
            )
            conn.commit()
            conn.close()

            os.makedirs(os.path.join(CLOUD_DIR,u),exist_ok=True)
            return redirect("/login")
        except:
            conn.close()
            return "Username exists"

    return render_template("register.html")


# ================= DASHBOARD =================
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():

    if "user" not in session:
        return redirect("/login")

    user = session["user"]

    # current path (for navigation)
    path = request.args.get("path", "")

    user_root = os.path.join(CLOUD_DIR, user)
    current_folder = os.path.join(user_root, path)

    # security check
    if not current_folder.startswith(user_root):
        return "Invalid path"

    os.makedirs(current_folder, exist_ok=True)

    # ===== FILE UPLOAD =====
    error_message = None
    if request.method == "POST":
        file = request.files.get("file")

        if file and allowed_file(file.filename):
            # Check quota before saving
            file.seek(0, 2)  # Seek to end to get size
            file_size = file.tell()
            file.seek(0)  # Reset to beginning

            storage = get_user_storage_info(user)
            if storage["used"] + (file_size / (1024 * 1024)) > storage["quota"]:
                error_message = f"Storage limit exceeded. You have {storage['quota'] - storage['used']:.1f} MB free but file is {file_size / (1024 * 1024):.1f} MB."
            else:
                filename = secure_filename(file.filename)
                file.save(os.path.join(current_folder, filename))
                add_log(user, f"uploaded {filename}")

    items = os.listdir(current_folder)

    folders = []
    files = []

    for item in items:
        full = os.path.join(current_folder, item)

        if os.path.isdir(full):
            folders.append(item)
        else:
            files.append(item)

    # Get storage info for user
    storage = get_user_storage_info(user)

    return render_template(
        "dashboard.html",
        user=user,
        folders=folders,
        files=files,
        path=path,
        storage=storage,
        error=error_message
    )

# ================= FILE PREVIEW =================
@app.route("/preview/<path:filename>")
def preview(filename):

    if "user" not in session:
        return redirect("/login")

    user_root = os.path.join(CLOUD_DIR, session["user"])
    file_path = os.path.join(user_root, filename)

    if not os.path.exists(file_path):
        return "File not found"

    return send_from_directory(user_root, filename, as_attachment=False)
# create folder
@app.route("/create-folder", methods=["POST"])
def create_folder():

    if "user" not in session:
        return redirect("/login")

    folder_name = request.form["folder"]
    path = request.form.get("path", "")

    base = os.path.join(CLOUD_DIR, session["user"], path)

    os.makedirs(os.path.join(base, folder_name), exist_ok=True)

    add_log(session["user"], f"created folder {folder_name}")

    return redirect(f"/dashboard?path={path}")

# ================= DOWNLOAD =================
@app.route("/download/<filename>")
def download(filename):
    folder=os.path.join(CLOUD_DIR,session["user"])
    return send_from_directory(folder,filename,as_attachment=True)

# ================= FILE ICON HELPER =================
def get_file_icon(filename):
    """Return FontAwesome icon class based on file extension"""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    icons = {
        "pdf": "fa-file-pdf",
        "doc": "fa-file-word", "docx": "fa-file-word",
        "xls": "fa-file-excel", "xlsx": "fa-file-excel",
        "ppt": "fa-file-powerpoint", "pptx": "fa-file-powerpoint",
        "jpg": "fa-file-image", "jpeg": "fa-file-image", "png": "fa-file-image", "gif": "fa-file-image", "bmp": "fa-file-image", "webp": "fa-file-image",
        "mp4": "fa-file-video", "avi": "fa-file-video", "mov": "fa-file-video", "mkv": "fa-file-video",
        "mp3": "fa-file-audio", "wav": "fa-file-audio", "flac": "fa-file-audio", "aac": "fa-file-audio",
        "zip": "fa-file-archive", "rar": "fa-file-archive", "7z": "fa-file-archive", "tar": "fa-file-archive", "gz": "fa-file-archive",
        "py": "fa-file-code", "js": "fa-file-code", "html": "fa-file-code", "css": "fa-file-code", "java": "fa-file-code", "cpp": "fa-file-code", "c": "fa-file-code",
        "txt": "fa-file-alt", "md": "fa-file-alt", "log": "fa-file-alt",
        "exe": "fa-cog", "msi": "fa-cog",
        "db": "fa-database", "sqlite": "fa-database", "sql": "fa-database"
    }
    return icons.get(ext, "fa-file")

# ================= TRASH SYSTEM =================
def get_trash_path(user):
    """Get trash folder path for user"""
    return os.path.join(CLOUD_DIR, user, ".trash")

def ensure_trash(user):
    """Ensure trash folder exists"""
    trash_path = get_trash_path(user)
    os.makedirs(trash_path, exist_ok=True)
    return trash_path

@app.route("/delete/<path:filename>")
def delete(filename):
    """Move file to trash instead of permanent delete"""
    if "user" not in session:
        return redirect("/login")

    user = session["user"]
    folder = os.path.join(CLOUD_DIR, user)
    file_path = os.path.join(folder, filename)

    if not os.path.exists(file_path):
        return "File not found"

    # Move to trash with timestamp to avoid conflicts
    trash_path = ensure_trash(user)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    trash_name = f"{timestamp}_{os.path.basename(filename)}"
    trash_file = os.path.join(trash_path, trash_name)
    
    shutil.move(file_path, trash_file)
    add_log(user, f"moved {filename} to trash")

    return redirect("/dashboard")

@app.route("/trash")
def view_trash():
    """View trash contents"""
    if "user" not in session:
        return redirect("/login")
    
    user = session["user"]
    trash_path = get_trash_path(user)
    
    trashed_items = []
    if os.path.exists(trash_path):
        for item in os.listdir(trash_path):
            full_path = os.path.join(trash_path, item)
            # Parse timestamp from name (format: YYYYMMDD_HHMMSS_originalname)
            parts = item.split("_", 2)
            if len(parts) >= 3:
                try:
                    deleted_time = f"{parts[0][:4]}-{parts[0][4:6]}-{parts[0][6:]} {parts[1][:2]}:{parts[1][2:4]}:{parts[1][4:]}"
                    original_name = parts[2]
                except:
                    deleted_time = "Unknown"
                    original_name = item
            else:
                deleted_time = "Unknown"
                original_name = item
            
            trashed_items.append({
                "trash_name": item,
                "original_name": original_name,
                "deleted_time": deleted_time,
                "is_file": os.path.isfile(full_path)
            })
    
    return render_template("trash.html", items=trashed_items, user=user)

@app.route("/restore/<trash_name>")
def restore(trash_name):
    """Restore file from trash"""
    if "user" not in session:
        return redirect("/login")
    
    user = session["user"]
    trash_path = get_trash_path(user)
    trash_file = os.path.join(trash_path, trash_name)
    
    if not os.path.exists(trash_file):
        return "Item not found in trash"
    
    # Extract original name
    parts = trash_name.split("_", 2)
    if len(parts) >= 3:
        original_name = parts[2]
    else:
        original_name = trash_name
    
    # Restore to user folder
    restore_path = os.path.join(CLOUD_DIR, user, original_name)
    # Handle conflicts
    if os.path.exists(restore_path):
        base, ext = os.path.splitext(original_name)
        counter = 1
        while os.path.exists(restore_path):
            restore_path = os.path.join(CLOUD_DIR, user, f"{base}_restored{counter}{ext}")
            counter += 1
    
    shutil.move(trash_file, restore_path)
    add_log(user, f"restored {original_name} from trash")
    
    return redirect("/trash")

@app.route("/empty-trash")
def empty_trash():
    """Permanently delete all items in trash"""
    if "user" not in session:
        return redirect("/login")
    
    user = session["user"]
    trash_path = get_trash_path(user)
    
    if os.path.exists(trash_path):
        for item in os.listdir(trash_path):
            item_path = os.path.join(trash_path, item)
            if os.path.isfile(item_path):
                os.remove(item_path)
            else:
                shutil.rmtree(item_path)
        add_log(user, "emptied trash")
    
    return redirect("/trash")

@app.route("/delete-permanent/<trash_name>")
def delete_permanent(trash_name):
    """Permanently delete single item from trash"""
    if "user" not in session:
        return redirect("/login")
    
    user = session["user"]
    trash_path = get_trash_path(user)
    trash_file = os.path.join(trash_path, trash_name)
    
    if os.path.exists(trash_file):
        if os.path.isfile(trash_file):
            os.remove(trash_file)
        else:
            shutil.rmtree(trash_file)
        add_log(user, f"permanently deleted {trash_name}")
    
    return redirect("/trash")

# ================= SEARCH =================
@app.route("/search")
def search():
    """Search files by name"""
    if "user" not in session:
        return redirect("/login")
    
    query = request.args.get("q", "").lower()
    user = session["user"]
    user_root = os.path.join(CLOUD_DIR, user)
    
    results = []
    if query and os.path.exists(user_root):
        for root, dirs, files in os.walk(user_root):
            # Skip trash folder
            if ".trash" in root:
                continue
            
            rel_path = os.path.relpath(root, user_root)
            if rel_path == ".":
                rel_path = ""
            
            for f in files:
                if query in f.lower():
                    results.append({
                        "name": f,
                        "path": os.path.join(rel_path, f) if rel_path else f,
                        "folder": rel_path if rel_path else "Home"
                    })
            
            for d in dirs:
                if query in d.lower():
                    results.append({
                        "name": d + "/",
                        "path": os.path.join(rel_path, d) if rel_path else d,
                        "folder": "Folder"
                    })
    
    return render_template("search.html", query=query, results=results, user=user)


# ================= ADMIN =================
@app.route("/admin")
def admin():

    if "user" not in session:
        return redirect("/admin-login")

    if session.get("role") != "admin":
        return redirect("/login")

    conn = get_db()
    users = conn.execute("SELECT username, role, quota_mb FROM users").fetchall()
    conn.close()
    
    # Add storage info for each user
    users_with_storage = []
    for user in users:
        storage = get_user_storage_info(user["username"])
        users_with_storage.append({
            "username": user["username"],
            "role": user["role"],
            "quota_mb": user["quota_mb"],
            "used_mb": storage["used"],
            "percent": storage["percent"]
        })

    return render_template("admin.html", users=users_with_storage)

# ================= UPDATE USER QUOTA =================
@app.route("/update-quota/<username>", methods=["POST"])
def update_quota(username):
    if session.get("role") != "admin":
        return redirect("/login")
    
    new_quota = request.form.get("quota", 100, type=int)
    
    conn = get_db()
    conn.execute("UPDATE users SET quota_mb=? WHERE username=?", (new_quota, username))
    conn.commit()
    conn.close()
    
    add_log(session["user"], f"updated quota for {username} to {new_quota}MB")
    
    return redirect("/admin")
# ================= ADMIN LOGIN =================

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password) and user["role"] == "admin":
            session["user"] = user["username"]
            session["role"] = user["role"]

            add_log(username, "admin login")

            return redirect("/admin")

        return "Invalid admin credentials"

    return render_template("admin_login.html")
# delete route
@app.route("/delete-user/<username>")
def delete_user(username):

    if session.get("role") != "admin":
        return redirect("/login")

    conn = get_db()
    conn.execute("DELETE FROM users WHERE username=?", (username,))
    conn.commit()
    conn.close()

    user_folder = os.path.join(CLOUD_DIR, username)
    if os.path.exists(user_folder):
        shutil.rmtree(user_folder)

    return redirect("/admin")

# ================= ADMIN LOGS =================
@app.route("/logs")
def logs():
    if session.get("role")!="admin":
        return redirect("/login")

    conn=get_db()
    logs=conn.execute(
        "SELECT * FROM logs ORDER BY time DESC"
    ).fetchall()
    conn.close()

    return render_template("logs.html",logs=logs)
# share files
@app.route("/share/<filename>")
def share_file(filename):

    if "user" not in session:
        return redirect("/login")

    token = str(uuid.uuid4())[:8]

    conn = get_db()
    conn.execute(
        "INSERT INTO shares(token, filename, owner) VALUES(?,?,?)",
        (token, filename, session["user"])
    )
    conn.commit()
    conn.close()

    return f"Share Link: http://127.0.0.1:5000/public/{token}"
# public link
@app.route("/public/<token>")
def public_download(token):

    conn = get_db()
    share = conn.execute(
        "SELECT * FROM shares WHERE token=?",
        (token,)
    ).fetchone()
    conn.close()

    if not share:
        return "Invalid share link"

    folder = os.path.join(CLOUD_DIR, share["owner"])

    return send_from_directory(folder, share["filename"], as_attachment=False)
# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# if __name__=="__main__":
#     app.run(debug=True)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
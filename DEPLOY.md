# ANY CLOUD - Deployment Guide

## Option 1: PythonAnywhere (RECOMMENDED - Free & Easy)

**Best for:** Flask apps with file uploads and SQLite

### Step-by-Step:

1. **Go to [pythonanywhere.com](https://www.pythonanywhere.com)** and create a free account

2. **Open a Bash console** (from the Dashboard)

3. **Clone your code** (or upload via Files tab):
```bash
cd ~
git clone https://github.com/YOUR_USERNAME/REDPROJECT.git
# OR upload ZIP file and extract
```

4. **Create virtual environment**:
```bash
cd REDPROJECT
mkvirtualenv --python=/usr/bin/python3.10 venv
pip install -r requirements.txt
```

5. **Go to Web tab** → Click **Add a new web app**
   - Select **Flask**
   - Python version: **3.10**
   - Path: `/home/YOUR_USERNAME/REDPROJECT/app.py`

6. **Edit WSGI file** (click link in Web tab):
```python
import sys
path = '/home/YOUR_USERNAME/REDPROJECT'
if path not in sys.path:
    sys.path.append(path)

from app import app as application
```

7. **Set working directory** in Web tab:
   - Click **WSGI configuration file** → Go back
   - Under **Code:** section, set:
     - **Working directory**: `/home/YOUR_USERNAME/REDPROJECT`

8. **Reload** the web app

9. **Your site is live!** URL: `https://YOUR_USERNAME.pythonanywhere.com`

---

## Option 2: Render.com (Free Tier)

1. **Push code to GitHub**
2. **Go to [render.com](https://render.com)** → Sign up
3. **New +** → **Web Service** → **Build and deploy from Git repository**
4. **Connect your GitHub repo**
5. **Configure:**
   - **Name**: any-cloud
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
6. **Create Web Service**

---

## Option 3: Railway.app (Simple)

1. **Push code to GitHub**
2. **Go to [railway.app](https://railway.app)** → Sign up
3. **New Project** → **Deploy from GitHub repo**
4. Select your repo
5. Railway auto-detects Flask and deploys

---

## Option 4: Self-Hosted (VPS/Dedicated Server)

### Using Gunicorn + Nginx:

```bash
# On your server
cd /var/www/anycloud
git clone YOUR_REPO.git
cd REDPROJECT
pip install -r requirements.txt

# Run with Gunicorn
gunicorn -w 4 -b 127.0.0.1:5000 app:app
```

### Using Docker:

```bash
# Build and run
docker build -t anycloud .
docker run -d -p 5000:5000 -v $(pwd)/cloud:/app/cloud -v $(pwd)/database.db:/app/database.db anycloud
```

---

## Important Production Notes

### 1. Secret Key (CRITICAL)
Edit `app.py` and change:
```python
app.secret_key = "change_this_to_random_string_32_chars"
```

### 2. Database
SQLite works for small apps. For production with many users, use PostgreSQL:
- PythonAnywhere: MySQL is included free
- Render/Railway: Add PostgreSQL addon

### 3. File Storage
User uploads in `cloud/` folder need persistent storage:
- PythonAnywhere: ✅ Persistent (files stay)
- Render: ⚠️ Ephemeral (use AWS S3 for files)
- Railway: ⚠️ Ephemeral (use AWS S3 for files)

### 4. Environment Variables
Create `.env` file:
```
FLASK_SECRET_KEY=your_random_key_here
FLASK_ENV=production
```

---

## Recommended: PythonAnywhere Free Tier

**Limits:**
- 1 web app
- 512 MB storage
- 100 seconds CPU/day
- No custom domain (subdomain only)

**Perfect for:** Small file storage apps with < 50 users

---

## Need Help?

If you get stuck on any platform, their documentation is excellent:
- PythonAnywhere: [Help pages](https://help.pythonanywhere.com/)
- Render: [Docs](https://render.com/docs)

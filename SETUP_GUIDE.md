# 🚀 EduShare - Complete Setup Guide

This guide will walk you through setting up and running the EduShare application step-by-step.

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (Automated)](#quick-start-automated)
3. [Manual Setup](#manual-setup)
4. [First Run](#first-run)
5. [Creating Your First Account](#creating-your-first-account)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before you begin, make sure you have:

- **Python 3.8 or higher** installed on your system
  - Check: `python3 --version` or `python --version`
  - Download from: https://www.python.org/downloads/

- **pip** (Python package manager) - usually comes with Python
  - Check: `pip --version` or `pip3 --version`

- **Git** (optional, for version control)
  - Check: `git --version`
  - Download from: https://git-scm.com/downloads

---

## Quick Start (Automated)

### On macOS/Linux:

```bash
# Navigate to the project directory
cd edushare

# Run the start script
./start.sh
```

### On Windows:

```bash
# Navigate to the project directory
cd edushare

# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
flask init-db

# (Optional) Add sample data
flask seed-db

# Run the application
python run.py
```

The application will be available at: **http://localhost:5000**

---

## Manual Setup

### Step 1: Extract the Project

Extract the `edushare` folder to your desired location.

### Step 2: Open Terminal/Command Prompt

Navigate to the project directory:

```bash
cd path/to/edushare
```

### Step 3: Create Virtual Environment

A virtual environment keeps the project dependencies isolated.

```bash
# macOS/Linux
python3 -m venv venv

# Windows
python -m venv venv
```

### Step 4: Activate Virtual Environment

**macOS/Linux:**
```bash
source venv/bin/activate
```

**Windows:**
```bash
venv\Scripts\activate
```

You should see `(venv)` appear in your terminal prompt.

### Step 5: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs all required packages:
- Flask (web framework)
- SQLAlchemy (database)
- Flask-Login (authentication)
- WTForms (form validation)
- And more...

### Step 6: Initialize Database

```bash
flask init-db
```

This creates the SQLite database file (`edushare.db`) with all necessary tables.

### Step 7: (Optional) Add Sample Data

To test the application with pre-made accounts and posts:

```bash
flask seed-db
```

This creates:
- 3 test user accounts
- Sample posts
- Follower relationships

**Test accounts:**
- Username: `alice` | Password: `password123`
- Username: `bob` | Password: `password123`
- Username: `charlie` | Password: `password123`

### Step 8: Run the Application

```bash
python run.py
```

You should see output like:
```
 * Running on http://127.0.0.1:5000
 * Running on http://0.0.0.0:5000
```

---

## First Run

1. **Open your web browser**

2. **Navigate to:** http://localhost:5000

3. **You should see the EduShare home page**

---

## Creating Your First Account

### Option 1: Use Sample Data (if you ran `flask seed-db`)

Log in with one of the test accounts:
- Username: `alice`
- Password: `password123`

### Option 2: Create a New Account

1. Click "**Sign Up**" in the navigation bar

2. Fill in the registration form:
   - **Username**: Choose a unique username (3-80 characters)
   - **Email**: Your email address
   - **Full Name**: Your real name
   - **Password**: At least 6 characters
   - **Confirm Password**: Re-enter your password

3. Click "**Sign Up**"

4. You'll be redirected to the login page

5. Log in with your new credentials

---

## Using the Application

### Creating Your First Post

1. Click the "**+**" button (mobile) or "**Create**" (desktop)

2. Fill in the post details:
   - **Title**: Give your post a descriptive title
   - **Description**: Add details about what you're sharing
   - **Document** (optional): Upload a file (PDF, DOCX, PPTX, TXT)

3. Click "**Create Post**"

### Interacting with Posts

- **Like**: Click the heart ❤️ icon
- **Comment**: Click on a post, then write a comment
- **Download**: Click download button on posts with documents

### Following Users

1. Click on a username to view their profile
2. Click "**Follow**"
3. Their posts will now appear in your feed

### Editing Your Profile

1. Click on your profile icon
2. Click "**Edit Profile**"
3. Update your:
   - Full name
   - Bio
   - Profile picture
4. Click "**Update Profile**"

---

## Troubleshooting

### Problem: "Command not found: python"

**Solution:** Try `python3` instead of `python`

### Problem: "No module named 'flask'"

**Solution:** Make sure:
1. Virtual environment is activated (you should see `(venv)`)
2. Dependencies are installed: `pip install -r requirements.txt`

### Problem: "Address already in use"

**Solution:** Another application is using port 5000. Either:
1. Stop the other application
2. Or run on a different port: `flask run --port 5001`

### Problem: "Database is locked"

**Solution:** 
1. Close the application
2. Delete `edushare.db`
3. Run `flask init-db` again

### Problem: Can't upload files

**Solution:** 
1. Check that `app/static/uploads/` directory exists
2. Check file size (max 16 MB)
3. Check file type (only PDF, DOCX, PPTX, TXT allowed)

### Problem: Static files (CSS/JS) not loading

**Solution:**
1. Hard refresh your browser: `Ctrl+F5` (Windows) or `Cmd+Shift+R` (Mac)
2. Clear browser cache
3. Check that files exist in `app/static/` directory

### Problem: "ModuleNotFoundError"

**Solution:**
1. Activate virtual environment
2. Reinstall dependencies: `pip install -r requirements.txt`

---

## Advanced Configuration

### Changing the Port

Edit `run.py` and change the port number:

```python
app.run(debug=True, host='0.0.0.0', port=8000)  # Changed from 5000 to 8000
```

### Using PostgreSQL Instead of SQLite

1. Install PostgreSQL
2. Create a database: `createdb edushare`
3. Update `config.py`:
   ```python
   SQLALCHEMY_DATABASE_URI = 'postgresql://username:password@localhost/edushare'
   ```
4. Install PostgreSQL driver: `pip install psycopg2-binary`

### Setting Environment Variables

Create a `.env` file in the project root:

```env
SECRET_KEY=your-secret-key-here
FLASK_ENV=development
DATABASE_URL=sqlite:///edushare.db
```

### Enabling Debug Mode

Debug mode is enabled by default in development. To disable:

In `run.py`, change:
```python
app.run(debug=False)
```

---

## Next Steps

1. **Explore the application** - Create posts, follow users, upload documents
2. **Customize the design** - Edit `app/static/css/style.css`
3. **Add payment integration** - Follow instructions in README.md
4. **Deploy to production** - See deployment guide in README.md

---

## Getting Help

1. **Check the README.md** for detailed documentation
2. **Review error messages** carefully - they often explain the problem
3. **Check file paths** - make sure you're in the correct directory
4. **Verify Python version** - must be 3.8 or higher

---

## File Structure Overview

```
edushare/
├── app/                      # Main application package
│   ├── auth/                # Authentication (login/signup)
│   ├── posts/               # Posts and documents
│   ├── users/               # User profiles and social
│   ├── payments/            # Payment integration (future)
│   ├── static/              # CSS, JS, uploads
│   ├── templates/           # HTML templates
│   ├── __init__.py          # App factory
│   ├── models.py            # Database models
│   └── forms.py             # Form validation
├── config.py                # Configuration
├── run.py                   # Entry point
├── requirements.txt         # Dependencies
└── README.md               # Documentation
```

---

## Command Reference

```bash
# Activate virtual environment
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Database commands
flask init-db              # Create database tables
flask seed-db              # Add sample data
flask create-admin         # Create admin user

# Run application
python run.py              # Normal run
flask run                  # Alternative
flask run --port 8000      # Run on different port

# Deactivate virtual environment
deactivate
```

---

**You're all set! Enjoy using EduShare! 🎓**

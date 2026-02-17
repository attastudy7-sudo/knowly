# 🎯 EduShare - Subject Filter & Admin Panel Upgrade Guide

## 🆕 What's New

Your EduShare platform now includes:

1. **Subject/Category System** - Organize posts by subjects (Mathematics, Computer Science, etc.)
2. **Complete Admin Panel** - Manage users, posts, and subjects
3. **Subject Filtering** - Filter posts by subject on feed and explore pages
4. **Enhanced Post Creation** - Select a subject when creating/editing posts
5. **Admin Dashboard** - Overview statistics and quick actions
6. **User Management** - View, activate/deactivate, and delete users
7. **Post Management** - Monitor and moderate all posts
8. **Subject Management** - Add, edit, and customize subjects

---

## 🚀 Quick Start

### 1. Update Your Database

Since we've added new tables and fields, you need to update your database:

```bash
# Option 1: Reset database (WARNING: Deletes all data)
rm edushare.db
flask init-db
flask seed-db

# Option 2: Migrate existing database (keeps your data)
flask shell
```

Then in the Flask shell:

```python
from app import db
from app.models import Subject

# Create the subjects table
db.create_all()

# Add the subject_id column to posts (if it doesn't exist)
# SQLite will handle this automatically with create_all()

# Create default subjects
from app.admin.routes import slugify

subjects_data = [
    {'name': 'Mathematics', 'icon': 'calculator', 'color': '#3b82f6', 'order': 1},
    {'name': 'Computer Science', 'icon': 'laptop-code', 'color': '#8b5cf6', 'order': 2},
    {'name': 'Physics', 'icon': 'atom', 'color': '#10b981', 'order': 3},
    {'name': 'Chemistry', 'icon': 'flask', 'color': '#f59e0b', 'order': 4},
    {'name': 'Biology', 'icon': 'dna', 'color': '#14b8a6', 'order': 5},
]

for data in subjects_data:
    subject = Subject(
        name=data['name'],
        slug=slugify(data['name']),
        icon=data['icon'],
        color=data['color'],
        order=data['order'],
        is_active=True,
        description=f"Posts about {data['name']}"
    )
    db.session.add(subject)

db.session.commit()
exit()
```

### 2. Access the Admin Panel

Navigate to: **http://localhost:5000/admin**

---

## 📚 Feature Guide

### 🎯 Subject System

#### What is a Subject?

Subjects (or categories) help organize posts by topic. Examples:
- Mathematics
- Computer Science  
- Physics
- Biology
- Literature

#### Creating a Subject

1. Go to **Admin Panel** → **Manage Subjects**
2. Click **"Add New Subject"**
3. Fill in:
   - **Name**: e.g., "Mathematics"
   - **Description**: Optional description
   - **Icon**: Font Awesome icon name (e.g., "calculator")
   - **Color**: Pick a color (hex code)
   - **Display Order**: Number (lower appears first)
   - **Active**: Check to make it visible
4. Click **"Save Subject"**

#### Editing Subjects

You can easily edit:
- Name and description
- Icon (choose from [Font Awesome](https://fontawesome.com/icons))
- Color (visual identification)
- Display order
- Active/inactive status

#### Deleting Subjects

**Warning**: Deleting a subject will unlink it from all posts, but won't delete the posts.

---

### 👥 User Management

#### Viewing All Users

**Admin Panel** → **Manage Users**

You can see:
- Username and full name
- Email address
- Join date
- Number of posts
- Number of followers
- Active/inactive status

#### Searching Users

Use the search bar to find users by:
- Username
- Email
- Full name

#### User Actions

**View Profile**: See the user's public profile

**Activate/Deactivate**: 
- Deactivated users cannot log in
- Their content remains but is marked as from an inactive user

**Delete User**:
- **Warning**: This permanently deletes:
  - The user account
  - All their posts
  - All their comments
  - All their likes
  - Their uploaded documents
- **Cannot be undone!**

---

### 📝 Post Management

#### Viewing All Posts

**Admin Panel** → **Manage Posts**

Features:
- See all posts in the system
- Filter by subject
- Search by title or description
- View engagement stats (likes, comments, downloads)

#### Post Actions

**View Post**: Opens the post detail page

**Delete Post**:
- Permanently removes the post
- Deletes associated document files
- Removes all comments and likes
- **Cannot be undone!**

---

### 📊 Admin Dashboard

Access at: **http://localhost:5000/admin**

Shows:
- **Total users, posts, subjects, comments**
- **Quick actions** (links to management pages)
- **Recent users** (last 5 signups)
- **Recent posts** (last 5 created)

---

## 🎨 Customizing Subjects

### Choosing Icons

1. Browse [Font Awesome Icons](https://fontawesome.com/icons)
2. Find an icon you like (e.g., "calculator")
3. Use the icon name **without** the `fa-` prefix
4. Examples:
   - `calculator` for mathematics
   - `laptop-code` for computer science
   - `atom` for physics
   - `flask` for chemistry
   - `dna` for biology

### Choosing Colors

Pick colors that match your brand or make subjects visually distinct:

```
Mathematics:      #3b82f6 (Blue)
Computer Science: #8b5cf6 (Purple)
Physics:          #10b981 (Green)
Chemistry:        #f59e0b (Amber)
Biology:          #14b8a6 (Teal)
Literature:       #ec4899 (Pink)
History:          #f97316 (Orange)
Engineering:      #06b6d4 (Cyan)
```

### Display Order

Lower numbers appear first:
- Order 1: Appears first
- Order 2: Appears second
- Order 10: Appears tenth

---

## 🔧 How It Works Technically

### Database Changes

**New Table: `subject`**
```sql
id, name, slug, description, icon, color, order, is_active, 
created_at, post_count
```

**Updated Table: `post`**
```sql
-- Added column:
subject_id (foreign key to subject.id)
```

### New Routes

**Admin Routes** (`/admin/...`):
- `/admin/` - Dashboard
- `/admin/subjects` - Manage subjects
- `/admin/subjects/create` - Create subject
- `/admin/subjects/<id>/edit` - Edit subject
- `/admin/subjects/<id>/delete` - Delete subject
- `/admin/users` - Manage users
- `/admin/posts` - Manage posts

**Updated Routes**:
- `/` and `/explore` now support `?subject=<id>` parameter for filtering
- `/posts/create` and `/posts/<id>/edit` now include subject selection

---

## 🎓 User Experience Changes

### For Content Creators

When creating a post:
1. Fill in title and description
2. **NEW**: Select a subject from dropdown
3. Upload document (optional)
4. Submit

### For Content Consumers

On the feed/explore page:
1. See all posts OR
2. **NEW**: Click a subject button to filter
3. Only see posts from that subject

Benefits:
- Find relevant content faster
- Discover posts in specific subjects
- Better organization

---

## 🔒 Security Notes

### Admin Access

**IMPORTANT**: Currently, any logged-in user can access the admin panel.

**For Production**, add role-based access control:

1. Add `is_admin` field to User model:
```python
is_admin = db.Column(db.Boolean, default=False)
```

2. Create admin decorator:
```python
from functools import wraps
from flask import abort
from flask_login import current_user

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function
```

3. Add to admin routes:
```python
@bp.route('/admin/users')
@login_required
@admin_required  # Add this
def users():
    # ...
```

---

## 📈 Future Enhancements

Easy additions you can make:

### 1. Make First User Admin Automatically
```python
# In signup route
if User.query.count() == 0:
    user.is_admin = True
```

### 2. Require Subjects
```python
# In CreatePostForm
subject = SelectField('Subject/Category', 
                     coerce=int, 
                     validators=[DataRequired()])  # Make required
```

### 3. Subject Statistics Page
- Most popular subjects
- Growth over time
- User preferences

### 4. Subject Subscription
- Users can subscribe to specific subjects
- Get notifications for new posts

### 5. Multi-Subject Posts
- Allow posts to belong to multiple subjects
- Use many-to-many relationship

---

## 🐛 Troubleshooting

### Problem: "No such table: subject"

**Solution**: Database not updated. Run:
```bash
flask shell
>>> from app import db
>>> db.create_all()
>>> exit()
```

### Problem: "subject_id column doesn't exist"

**Solution**: Run:
```bash
rm edushare.db
flask init-db
flask seed-db
```

### Problem: Can't see Admin link

**Solution**: 
1. Make sure you're logged in
2. Admin link is in desktop menu (top nav)
3. On mobile, access directly: `/admin`

### Problem: Subjects not showing in dropdown

**Solution**: Create subjects first:
1. Go to `/admin/subjects`
2. Click "Add New Subject"
3. Create at least one subject

---

## 📝 Quick Reference

### CLI Commands
```bash
flask init-db              # Create database tables
flask seed-db              # Add sample data (includes subjects)
flask shell                # Open Python shell with app context
```

### URLs
```
/admin                     # Admin dashboard
/admin/subjects            # Manage subjects
/admin/users               # Manage users
/admin/posts               # Manage posts
/?subject=1                # Filter feed by subject
/explore?subject=2         # Filter explore by subject
```

### Default Subjects (after seed)
1. Mathematics
2. Computer Science
3. Physics
4. Chemistry
5. Biology
6. Literature
7. History
8. Engineering

---

## ✅ Migration Checklist

- [ ] Backup existing database (if needed)
- [ ] Update database structure
- [ ] Create default subjects
- [ ] Test subject creation
- [ ] Test post filtering
- [ ] Test admin panel access
- [ ] Review security settings
- [ ] Add role-based access (production)
- [ ] Customize subjects for your needs
- [ ] Train users on new features

---

## 🎉 You're All Set!

Your EduShare platform now has:
- ✅ Complete admin panel
- ✅ Subject/category system
- ✅ User management
- ✅ Post management
- ✅ Content filtering
- ✅ Enhanced organization

Start managing your platform at: **http://localhost:5000/admin**

---

**Need help?** Check the inline code comments or refer to the ARCHITECTURE.md document for technical details.

"""
EduShare - Educational Social Media Platform
Entry point for running the application
"""

from app import create_app, db
from app.models import User, Post, Document, Comment, Like, Purchase, Notification, Subject
import os


# Create the application instance
app = create_app()

# ADD THIS LINE TEMPORARILY
print(f"DEBUG: Secret Key is set to: {app.config.get('SECRET_KEY')}")


@app.shell_context_processor
def make_shell_context():
    """
    Make database models available in Flask shell.
    Run 'flask shell' to access these automatically.
    """
    return {
        'db': db,
        'User': User,
        'Post': Post,
        'Document': Document,
        'Comment': Comment,
        'Like': Like,
        'Purchase': Purchase,
        'Notification': Notification,
        'Subject': Subject
    }


@app.cli.command()
def create_admin():
    """
    Create an admin user from command line.
    Usage: flask create-admin
    """
    from getpass import getpass
    
    print("Creating admin user...")
    username = input("Username: ")
    email = input("Email: ")
    full_name = input("Full name: ")
    password = getpass("Password: ")
    
    # Check if user already exists
    if User.query.filter_by(username=username).first():
        print("Error: Username already exists!")
        return
    
    if User.query.filter_by(email=email).first():
        print("Error: Email already exists!")
        return
    
    # Create user
    user = User(username=username, email=email, full_name=full_name)
    user.set_password(password)
    
    db.session.add(user)
    db.session.commit()
    
    print(f"Admin user '{username}' created successfully!")


@app.cli.command()
def init_db():
    """
    Initialize the database.
    Usage: flask init-db
    """
    print("Creating database tables...")
    db.create_all()
    print("Database initialized successfully!")


@app.cli.command()
def seed_db():
    """
    Seed the database with sample data for testing.
    Usage: flask seed-db
    """
    print("Seeding database with sample data...")
    
    # Create sample subjects
    subjects_data = [
        {'name': 'Mathematics', 'slug': 'mathematics', 'icon': 'calculator', 'color': '#3b82f6', 'order': 1},
        {'name': 'Computer Science', 'slug': 'computer-science', 'icon': 'laptop-code', 'color': '#8b5cf6', 'order': 2},
        {'name': 'Physics', 'slug': 'physics', 'icon': 'atom', 'color': '#10b981', 'order': 3},
        {'name': 'Chemistry', 'slug': 'chemistry', 'icon': 'flask', 'color': '#f59e0b', 'order': 4},
        {'name': 'Biology', 'slug': 'biology', 'icon': 'dna', 'color': '#14b8a6', 'order': 5},
        {'name': 'Literature', 'slug': 'literature', 'icon': 'book-open', 'color': '#ec4899', 'order': 6},
        {'name': 'History', 'slug': 'history', 'icon': 'landmark', 'color': '#f97316', 'order': 7},
        {'name': 'Engineering', 'slug': 'engineering', 'icon': 'cogs', 'color': '#06b6d4', 'order': 8},
    ]
    
    subjects = []
    for subject_data in subjects_data:
        subject = Subject(**subject_data, description=f"Posts about {subject_data['name']}", is_active=True)
        subjects.append(subject)
        db.session.add(subject)
    
    db.session.commit()
    print(f"✅ Created {len(subjects)} subjects")
    
    # Create sample users
    users = [
        User(username='alice', email='alice@example.com', full_name='Alice Johnson', 
             bio='Computer Science student passionate about AI and machine learning.'),
        User(username='bob', email='bob@example.com', full_name='Bob Smith',
             bio='Mathematics enthusiast sharing educational resources.'),
        User(username='charlie', email='charlie@example.com', full_name='Charlie Davis',
             bio='Biology student documenting my learning journey.'),
    ]
    
    for user in users:
        user.set_password('password123')
        db.session.add(user)
    
    db.session.commit()
    print(f"✅ Created {len(users)} users")
    
    # Create sample posts with subjects
    posts = [
        Post(title='Introduction to Python Programming', 
             description='A comprehensive guide for beginners learning Python.',
             author=users[0],
             subject_id=subjects[1].id),  # Computer Science
        Post(title='Calculus Study Notes',
             description='My notes from Calculus I - derivatives and integrals.',
             author=users[1],
             subject_id=subjects[0].id),  # Mathematics
        Post(title='Biology Lab Report Template',
             description='A professional template for writing lab reports.',
             author=users[2],
             subject_id=subjects[4].id),  # Biology
    ]
    
    for post in posts:
        db.session.add(post)
    
    db.session.commit()
    print(f"✅ Created {len(posts)} posts")
    
    # Update subject post counts
    for subject in subjects:
        subject.update_post_count()
    
    # Create sample follows
    users[0].follow(users[1])
    users[0].follow(users[2])
    users[1].follow(users[0])
    users[2].follow(users[0])
    
    db.session.commit()
    print("✅ Created follow relationships")
    
    print("\n✅ Sample data created successfully!")
    print("\nSample accounts:")
    print("  - alice / password123")
    print("  - bob / password123")
    print("  - charlie / password123")
    print("\nAccess admin panel at: http://localhost:5000/admin")


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
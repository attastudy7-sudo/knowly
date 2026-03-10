import cloudinary.uploader
from flask import render_template, redirect, url_for, flash, request, current_app, session
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.users import bp
from app.forms import EditProfileForm, SearchForm
from app.models import User, Post, Bookmark

@bp.route('/profile/<username>')
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()

    page = request.args.get('page', 1, type=int)

    # Own profile: show all posts including pending/rejected
    # Anyone else's profile: only approved posts
    is_own_profile = current_user.is_authenticated and current_user.id == user.id
    if is_own_profile:
        posts = user.posts.order_by(Post.created_at.desc()).paginate(
            page=page,
            per_page=current_app.config['POSTS_PER_PAGE'],
            error_out=False
        )
    else:
        posts = user.posts.filter_by(status='approved').order_by(Post.created_at.desc()).paginate(
            page=page,
            per_page=current_app.config['POSTS_PER_PAGE'],
            error_out=False
        )

# Fetch quiz attempts — only shown on own profile
    quiz_attempts = []
    quiz_stats = {'total': 0, 'avg_score': 0, 'perfect': 0}
    if is_own_profile:
        from app.models import QuizAttempt
        quiz_attempts = (
            QuizAttempt.query
            .filter_by(user_id=user.id)
            .order_by(QuizAttempt.created_at.desc())
            .limit(20)
            .all()
        )
        if quiz_attempts:
            total   = len(quiz_attempts)
            avg     = round(sum(a.score_pct for a in quiz_attempts) / total, 1)
            perfect = sum(1 for a in quiz_attempts if a.score_pct >= 100)
            quiz_stats = {'total': total, 'avg_score': avg, 'perfect': perfect}

    return render_template('users/profile.html',
                           title=f'{user.username}\'s Profile',
                           user=user,
                           posts=posts,
                           is_own_profile=is_own_profile,
                           quiz_attempts=quiz_attempts,
                           quiz_stats=quiz_stats)

@bp.route('/bookmarks')
@login_required
def bookmarks():
    page = request.args.get('page', 1, type=int)
    bookmarks = Bookmark.query.filter_by(user_id=current_user.id)\
                              .order_by(Bookmark.created_at.desc())\
                              .paginate(page=page, per_page=15, error_out=False)
    return render_template('users/bookmarks.html', title='Saved Posts', bookmarks=bookmarks)


@bp.route('/save-education', methods=['POST'])
@login_required
def save_education():
    school = request.form.get('school', '').strip()
    programme = request.form.get('programme', '').strip()
    xp_earned = 0
    
    # Award XP for adding school (10 XP) - only if not already set
    if school and not current_user.school:
        current_user.school = school
        xp_earned += 10
    elif school:
        current_user.school = school
    
    # Award XP for adding programme (15 XP) - only if not already set
    if programme and not current_user.programme:
        current_user.programme = programme
        xp_earned += 15
    elif programme:
        current_user.programme = programme
    
    if xp_earned > 0:
        current_user.add_xp(xp_earned)
        flash(f'🎉 You earned {xp_earned} XP for completing your profile!', 'success')
    
    # Clear the session variable so the overlay won't reappear
    db.session.commit()
    return redirect(request.referrer or url_for('main.explore'))


@bp.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """
    Edit current user's profile.
    """
    form = EditProfileForm()

    if form.validate_on_submit():
        xp_earned = 0
        
        # Award XP for adding bio (5 XP) - only if not already set
        if form.bio.data and not current_user.bio:
            xp_earned += 5
        current_user.bio = form.bio.data
        
        # Award XP for adding school (10 XP) - only if not already set
        if form.school.data and not current_user.school:
            xp_earned += 10
        current_user.school = form.school.data
        
        # Award XP for adding programme (15 XP) - only if not already set
        if form.programme.data and not current_user.programme:
            xp_earned += 15
        current_user.programme = form.programme.data
        
        current_user.full_name = form.full_name.data

        # Handle profile picture upload
        if form.profile_picture.data and form.profile_picture.data.filename:
            file = form.profile_picture.data

            try:
                # Delete old profile picture from Cloudinary if not the default
                if current_user.profile_picture and current_user.profile_picture != 'default.jpg':
                    try:
                        cloudinary.uploader.destroy(
                            current_user.profile_picture,
                            resource_type='image'
                        )
                    except Exception as e:
                        current_app.logger.warning(f"Failed to delete old profile picture: {e}")

                # Upload new profile picture to Cloudinary
                result = cloudinary.uploader.upload(
                    file,
                    folder='knowly/profiles',
                    resource_type='image',
                    use_filename=True,
                    unique_filename=True,
                    transformation=[
                        {'width': 400, 'height': 400, 'crop': 'fill', 'gravity': 'face'}
                    ]
                )

                # Store the public_id so we can delete it later if needed
                current_user.profile_picture = result['secure_url']


            except Exception as e:
                current_app.logger.error(f"Cloudinary profile picture upload failed: {e}")
                flash('Profile picture upload failed. Please try again.', 'danger')
                return redirect(url_for('users.edit_profile'))

        if xp_earned > 0:
            current_user.add_xp(xp_earned)
            flash(f'🎉 You earned {xp_earned} XP for completing your profile!', 'success')
        else:
            flash('Your profile has been updated!', 'success')
        
        db.session.commit()
        return redirect(url_for('users.profile', username=current_user.username))

    elif request.method == 'GET':
        form.full_name.data = current_user.full_name
        form.bio.data = current_user.bio
        form.school.data = current_user.school
        form.programme.data = current_user.programme

    return render_template('users/edit_profile.html', title='Edit Profile', form=form)


@bp.route('/follow/<username>', methods=['POST'])
@login_required
def follow(username):
    """
    Follow a user.
    """
    user = User.query.filter_by(username=username).first_or_404()

    if user == current_user:
        flash('You cannot follow yourself!', 'warning')
        return redirect(url_for('users.profile', username=username))

    if current_user.is_following(user):
        flash('You are already following this user.', 'info')
    else:
        current_user.follow(user)
        db.session.commit()
        flash(f'You are now following {username}!', 'success')
        from app.models import create_notification
        create_notification(
            user_id=user.id,
            message=f'{current_user.username} started following you',
            notification_type='follow',
            link=f'/profile/{current_user.username}',
        )

    return redirect(url_for('users.profile', username=username))


@bp.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow(username):
    """
    Unfollow a user.
    """
    user = User.query.filter_by(username=username).first_or_404()

    if user == current_user:
        flash('You cannot unfollow yourself!', 'warning')
        return redirect(url_for('users.profile', username=username))

    if not current_user.is_following(user):
        flash('You are not following this user.', 'info')
    else:
        current_user.unfollow(user)
        db.session.commit()
        flash(f'You have unfollowed {username}.', 'success')

    return redirect(url_for('users.profile', username=username))


@bp.route('/followers/<username>')
def followers(username):
    """
    View a user's followers.
    """
    user = User.query.filter_by(username=username).first_or_404()

    page = request.args.get('page', 1, type=int)
    followers = user.followers.paginate(
        page=page,
        per_page=current_app.config['USERS_PER_PAGE'],
        error_out=False
    )

    return render_template('users/followers.html',
                           title=f'{username}\'s Followers',
                           user=user,
                           followers=followers)


@bp.route('/following/<username>')
def following(username):
    """
    View users that a user is following.
    """
    user = User.query.filter_by(username=username).first_or_404()

    page = request.args.get('page', 1, type=int)
    following = user.following.paginate(
        page=page,
        per_page=current_app.config['USERS_PER_PAGE'],
        error_out=False
    )

    return render_template('users/following.html',
                           title=f'{username} is Following',
                           user=user,
                           following=following)


@bp.route('/search')
def search():
    query        = request.args.get('q', '').strip()
    content_type = request.args.get('type', '')
    subject_id   = request.args.get('subject', type=int)

    from app.models import Subject
    subjects = Subject.query.filter_by(is_active=True).order_by(Subject.order, Subject.name).all()

    if not query:
        return render_template('users/search.html',
                               title='Search',
                               query='',
                               users=[],
                               posts=[],
                               subjects=subjects,
                               content_type=content_type,
                               subject_id=subject_id)

    # Search users
    users = User.query.filter(
        db.or_(
            User.username.contains(query),
            User.full_name.contains(query)
        )
    ).limit(12).all()

    # Search posts — approved only
    post_query = Post.query.filter(
        Post.status == 'approved',
        db.or_(
            Post.title.contains(query),
            Post.description.contains(query)
        )
    )

    if content_type in ('notes', 'cheatsheet', 'quiz', 'mixed'):
        post_query = post_query.filter(Post.content_type == content_type)

    if subject_id:
        post_query = post_query.filter(Post.subject_id == subject_id)

    posts = post_query.order_by(Post.created_at.desc()).limit(30).all()

    return render_template('users/search.html',
                           title=f'Results for "{query}"',
                           query=query,
                           users=users,
                           posts=posts,
                           subjects=subjects,
                           content_type=content_type,
                           subject_id=subject_id)
                           
@bp.route('/skip-education', methods=['POST'])
@login_required
def skip_education():
    """Mark education onboarding as permanently skipped in the DB."""
    current_user.onboarding_skipped = True
    db.session.commit()
    return '', 204
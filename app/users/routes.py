import cloudinary.uploader
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.users import bp
from app.forms import EditProfileForm, SearchForm
from app.models import User, Post


@bp.route('/profile/<username>')
def profile(username):
    """
    View a user's profile with their posts.
    """
    user = User.query.filter_by(username=username).first_or_404()

    page = request.args.get('page', 1, type=int)
    posts = user.posts.order_by(Post.created_at.desc()).paginate(
        page=page,
        per_page=current_app.config['POSTS_PER_PAGE'],
        error_out=False
    )

    return render_template('users/profile.html',
                           title=f'{user.username}\'s Profile',
                           user=user,
                           posts=posts)


@bp.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """
    Edit current user's profile.
    """
    form = EditProfileForm()

    if form.validate_on_submit():
        current_user.full_name = form.full_name.data
        current_user.bio = form.bio.data

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
                    folder='edushare/profiles',
                    resource_type='image',
                    use_filename=True,
                    unique_filename=True,
                    transformation=[
                        {'width': 400, 'height': 400, 'crop': 'fill', 'gravity': 'face'}
                    ]
                )

                # Store the public_id so we can delete it later if needed
                current_user.profile_picture = result['public_id']

            except Exception as e:
                current_app.logger.error(f"Cloudinary profile picture upload failed: {e}")
                flash('Profile picture upload failed. Please try again.', 'danger')
                return redirect(url_for('users.edit_profile'))

        db.session.commit()
        flash('Your profile has been updated!', 'success')
        return redirect(url_for('users.profile', username=current_user.username))

    elif request.method == 'GET':
        form.full_name.data = current_user.full_name
        form.bio.data = current_user.bio

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
    """
    Search for users and posts.
    """
    query = request.args.get('q', '')

    if not query:
        return render_template('users/search.html',
                               title='Search',
                               query='',
                               users=[],
                               posts=[])

    # Search users by username or full name
    users = User.query.filter(
        db.or_(
            User.username.contains(query),
            User.full_name.contains(query)
        )
    ).limit(20).all()

    # Search posts by title or description
    posts = Post.query.filter(
        db.or_(
            Post.title.contains(query),
            Post.description.contains(query)
        )
    ).order_by(Post.created_at.desc()).limit(20).all()

    return render_template('users/search.html',
                           title=f'Search Results for "{query}"' if query else 'Search',
                           query=query,
                           users=users,
                           posts=posts)
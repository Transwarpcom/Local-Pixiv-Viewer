from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.models import Work, Comment, User
from app.extensions import db

bp = Blueprint('api', __name__)

@bp.route('/work/<int:work_id>/like', methods=['POST'])
@login_required
def like_work(work_id):
    work = Work.query.get_or_404(work_id)
    # Optimized check
    is_liked = current_user.liked_works.filter_by(id=work.id).first() is not None
    
    if is_liked:
        current_user.liked_works.remove(work)
        liked = False
    else:
        current_user.liked_works.append(work)
        liked = True
    db.session.commit()
    return jsonify({'liked': liked, 'count': work.liked_by.count()})

@bp.route('/work/<int:work_id>/bookmark', methods=['POST'])
@login_required
def bookmark_work(work_id):
    work = Work.query.get_or_404(work_id)
    # Optimized check
    is_bookmarked = current_user.bookmarked_works.filter_by(id=work.id).first() is not None
    
    if is_bookmarked:
        current_user.bookmarked_works.remove(work)
        bookmarked = False
    else:
        current_user.bookmarked_works.append(work)
        bookmarked = True
    db.session.commit()
    return jsonify({'bookmarked': bookmarked})

@bp.route('/work/<int:work_id>/comment', methods=['POST'])
@login_required
def post_comment(work_id):
    content = request.json.get('content')
    if not content:
        return jsonify({'error': 'Empty content'}), 400
        
    comment = Comment(user_id=current_user.id, work_id=work_id, content=content)
    db.session.add(comment)
    db.session.commit()
    
    return jsonify({
        'id': comment.id,
        'user': current_user.username,
        'content': comment.content,
        'created_at': comment.created_at.isoformat()
    })

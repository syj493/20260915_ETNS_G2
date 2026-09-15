from functools import wraps

from flask import abort
from flask_login import current_user


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def can_access_issue(issue, user):
    """관리자는 전체 접근 가능, 담당자는 본인에게 배정된 이슈만 접근 가능."""
    if user.is_admin:
        return True
    return issue.assigned_user_id == user.id

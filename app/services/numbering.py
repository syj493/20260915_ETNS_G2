from datetime import datetime

from app.models import Issue, MovingCase


def next_case_number():
    year = datetime.utcnow().year
    count = MovingCase.query.filter(
        MovingCase.case_number.like(f"MC-{year}-%")
    ).count()
    return f"MC-{year}-{count + 1:04d}"


def next_issue_number():
    year = datetime.utcnow().year
    count = Issue.query.filter(Issue.issue_number.like(f"M-{year}-%")).count()
    return f"M-{year}-{count + 1:04d}"

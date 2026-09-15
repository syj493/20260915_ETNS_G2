"""초기 데이터 생성: 관리자/담당자 계정 + 이슈 유형."""
import os

from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import IssueType, User
from app.models.issue import DEFAULT_ISSUE_TYPES

ADMIN_EMAIL = os.environ.get("SEED_ADMIN_EMAIL", "admin@movingcs.local")
ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "mNb7-Qz3x-RtY2")

STAFF_USERS = [
    ("EMP1001", "신동욱", "staff.shin@movingcs.local"),
    ("EMP1002", "김하은", "staff.kim@movingcs.local"),
    ("EMP1003", "박지훈", "staff.park@movingcs.local"),
    ("EMP1004", "최수아", "staff.choi@movingcs.local"),
]
STAFF_PASSWORD = os.environ.get("SEED_STAFF_PASSWORD", "staff1234!")


def run():
    app = create_app()
    with app.app_context():
        if not User.query.filter_by(email=ADMIN_EMAIL).first():
            db.session.add(User(
                employee_id="ADMIN001", name="관리자", email=ADMIN_EMAIL,
                password_hash=generate_password_hash(ADMIN_PASSWORD),
                role="admin", department="무빙사업팀", is_active_flag=True,
            ))
            print(f"관리자 계정 생성: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
        else:
            print("관리자 계정이 이미 존재합니다.")

        for emp_id, name, email in STAFF_USERS:
            if not User.query.filter_by(email=email).first():
                db.session.add(User(
                    employee_id=emp_id, name=name, email=email,
                    password_hash=generate_password_hash(STAFF_PASSWORD),
                    role="staff", department="무빙사업팀", is_active_flag=True,
                ))
        print(f"담당자 계정 {len(STAFF_USERS)}명 생성 완료 (공통 비밀번호: {STAFF_PASSWORD})")

        for name in DEFAULT_ISSUE_TYPES:
            if not IssueType.query.filter_by(name=name).first():
                db.session.add(IssueType(name=name, is_active=True))
        print(f"이슈 유형 {len(DEFAULT_ISSUE_TYPES)}개 생성 완료")

        db.session.commit()


if __name__ == "__main__":
    run()

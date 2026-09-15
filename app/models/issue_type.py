from app.extensions import db


class IssueType(db.Model):
    __tablename__ = "issue_types"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

from datetime import datetime

from app.extensions import db

ACTION_LABELS = {
    "created": "이슈 생성",
    "assignee_changed": "담당자 변경",
    "status_changed": "상태 변경",
    "priority_changed": "우선순위 변경",
    "vendor_changed": "업체 변경",
    "customer_contact": "고객 응대",
    "vendor_inquiry": "업체 문의",
    "vendor_response": "업체 답변",
    "attachment_added": "파일 첨부",
    "closed": "이슈 종결",
}


class IssueLog(db.Model):
    __tablename__ = "issue_logs"

    id = db.Column(db.Integer, primary_key=True)
    issue_id = db.Column(db.Integer, db.ForeignKey("issues.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action_type = db.Column(db.String(30), nullable=False)
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User")

    @property
    def action_label(self):
        return ACTION_LABELS.get(self.action_type, self.action_type)

from datetime import datetime, timedelta

from app.extensions import db

PRIORITY_SLA_HOURS = {
    "URGENT": 4,
    "HIGH": 12,
    "MEDIUM": 24,
    "LOW": 72,
}

# MUST-05: SLA 초과 전 "임박" 상태로 미리 경고하기 위한 여유 시간
SLA_WARNING_HOURS = 2

# MUST-05: 우선순위/SLA와 무관하게, 접수 후 일정 기간 이상 미해결이면 "장기 미처리"로 표시
LONG_PENDING_HOURS = 72

PRIORITY_LABELS = {
    "URGENT": ("🔴", "긴급"),
    "HIGH": ("🟠", "높음"),
    "MEDIUM": ("🟡", "보통"),
    "LOW": ("⚪", "낮음"),
}

STATUS_LABELS = {
    "NEW": "신규 접수",
    "ASSIGNED": "담당자 배정",
    "IN_PROGRESS": "처리 중",
    "WAITING_VENDOR": "업체 답변 대기",
    "WAITING_CUSTOMER": "고객 답변 대기",
    "RESOLVED": "해결",
    "CLOSED": "종결",
}

OPEN_STATUSES = ["NEW", "ASSIGNED", "IN_PROGRESS", "WAITING_VENDOR", "WAITING_CUSTOMER"]
CLOSED_STATUSES = ["RESOLVED", "CLOSED"]

DEFAULT_ISSUE_TYPES = [
    "파손", "분실", "배송 지연", "일정 변경", "통관", "포장",
    "운송", "배송", "비용", "서류", "업체 대응", "고객 문의", "기타",
]


class Issue(db.Model):
    __tablename__ = "issues"

    id = db.Column(db.Integer, primary_key=True)
    issue_number = db.Column(db.String(30), unique=True, nullable=False)
    moving_case_id = db.Column(db.Integer, db.ForeignKey("moving_cases.id"), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"))
    assigned_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    issue_type = db.Column(db.String(50), nullable=False)
    priority = db.Column(db.String(20), nullable=False, default="MEDIUM")
    status = db.Column(db.String(30), nullable=False, default="NEW")
    occurred_at = db.Column(db.DateTime, default=datetime.utcnow)
    due_at = db.Column(db.DateTime)
    resolved_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = db.relationship("Customer")
    vendor = db.relationship("Vendor")
    assigned_user = db.relationship("User")
    logs = db.relationship(
        "IssueLog", backref="issue", lazy="dynamic", order_by="IssueLog.created_at"
    )
    customer_communications = db.relationship(
        "CustomerCommunication", backref="issue", lazy="dynamic",
        order_by="CustomerCommunication.created_at",
    )
    vendor_communications = db.relationship(
        "VendorCommunication", backref="issue", lazy="dynamic",
        order_by="VendorCommunication.created_at",
    )
    attachments = db.relationship("Attachment", backref="issue", lazy="dynamic")

    def recompute_due_at(self):
        base = self.occurred_at or datetime.utcnow()
        hours = PRIORITY_SLA_HOURS.get(self.priority, 24)
        self.due_at = base + timedelta(hours=hours)

    @property
    def is_open(self):
        return self.status not in CLOSED_STATUSES

    @property
    def is_sla_breached(self):
        if not self.is_open or not self.due_at:
            return False
        return datetime.utcnow() > self.due_at

    @property
    def is_sla_warning(self):
        """SLA 초과는 아니지만 곧(SLA_WARNING_HOURS 이내) 초과될 예정."""
        if not self.is_open or not self.due_at or self.is_sla_breached:
            return False
        return (self.due_at - datetime.utcnow()) <= timedelta(hours=SLA_WARNING_HOURS)

    @property
    def is_long_pending(self):
        """우선순위와 무관하게 접수 후 오래 방치된 이슈."""
        if not self.is_open or not self.occurred_at:
            return False
        return (datetime.utcnow() - self.occurred_at) >= timedelta(hours=LONG_PENDING_HOURS)

    @property
    def is_unassigned(self):
        return self.is_open and not self.assigned_user_id

    @property
    def hours_until_due(self):
        if not self.due_at:
            return None
        return round((self.due_at - datetime.utcnow()).total_seconds() / 3600, 1)

    @property
    def priority_display(self):
        icon, label = PRIORITY_LABELS.get(self.priority, ("⚪", self.priority))
        return f"{icon} {label}"

    @property
    def status_display(self):
        return STATUS_LABELS.get(self.status, self.status)

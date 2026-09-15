from datetime import datetime

from app.extensions import db


class MovingCase(db.Model):
    __tablename__ = "moving_cases"

    id = db.Column(db.Integer, primary_key=True)
    case_number = db.Column(db.String(30), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    departure_country = db.Column(db.String(100))
    departure_city = db.Column(db.String(100))
    arrival_country = db.Column(db.String(100))
    arrival_city = db.Column(db.String(100))
    scheduled_date = db.Column(db.Date)
    actual_moving_date = db.Column(db.Date)
    estimated_arrival_date = db.Column(db.Date)
    actual_arrival_date = db.Column(db.Date)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"))
    assigned_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    status = db.Column(db.String(30), default="IN_PROGRESS", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    vendor = db.relationship("Vendor")
    assigned_user = db.relationship("User")
    issues = db.relationship("Issue", backref="moving_case", lazy="dynamic")

    @property
    def route(self):
        return f"{self.departure_city or self.departure_country or '-'} → {self.arrival_city or self.arrival_country or '-'}"

from flask import Blueprint, render_template
from flask_login import login_required

from app.services.dashboard_service import build_dashboard_data

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    data = build_dashboard_data()
    return render_template("dashboard/index.html", data=data)

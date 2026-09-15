from flask import Blueprint, jsonify
from flask_login import login_required

from app.services.dashboard_service import build_dashboard_data

api_bp = Blueprint("api", __name__)


@api_bp.route("/dashboard/summary")
@login_required
def dashboard_summary():
    return jsonify(build_dashboard_data())

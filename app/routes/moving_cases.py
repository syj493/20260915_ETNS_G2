from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.decorators import admin_required
from app.extensions import db
from app.models import Customer, MovingCase, User, Vendor
from app.services.numbering import next_case_number

moving_cases_bp = Blueprint("moving_cases", __name__)


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


@moving_cases_bp.route("/")
@login_required
@admin_required
def list_view():
    cases = MovingCase.query.order_by(MovingCase.created_at.desc()).all()
    return render_template("moving_cases/list.html", cases=cases)


@moving_cases_bp.route("/new", methods=["GET", "POST"])
@login_required
@admin_required
def new_case():
    if request.method == "POST":
        customer_id = request.form.get("customer_id")
        customer = Customer.query.get(customer_id) if customer_id else None
        if not customer:
            flash("고객을 선택해주세요.", "error")
            return redirect(url_for("moving_cases.new_case"))

        vendor_id = request.form.get("vendor_id") or None
        assigned_user_id = request.form.get("assigned_user_id") or None

        case = MovingCase(
            case_number=next_case_number(),
            customer_id=customer.id,
            departure_country=request.form.get("departure_country") or None,
            departure_city=request.form.get("departure_city") or None,
            arrival_country=request.form.get("arrival_country") or None,
            arrival_city=request.form.get("arrival_city") or None,
            scheduled_date=_parse_date(request.form.get("scheduled_date")),
            actual_moving_date=_parse_date(request.form.get("actual_moving_date")),
            estimated_arrival_date=_parse_date(request.form.get("estimated_arrival_date")),
            actual_arrival_date=_parse_date(request.form.get("actual_arrival_date")),
            vendor_id=int(vendor_id) if vendor_id else None,
            assigned_user_id=int(assigned_user_id) if assigned_user_id else None,
            status=request.form.get("status", "IN_PROGRESS"),
        )
        db.session.add(case)
        db.session.commit()
        flash(f"이사 건 {case.case_number}이(가) 등록되었습니다.", "success")
        return redirect(url_for("moving_cases.list_view"))

    customers = Customer.query.order_by(Customer.name).all()
    vendors = Vendor.query.filter_by(is_active=True).order_by(Vendor.name).all()
    staff_users = User.query.filter_by(role="staff", is_active_flag=True).all()
    return render_template(
        "moving_cases/form.html", customers=customers, vendors=vendors, staff_users=staff_users,
    )


@moving_cases_bp.route("/<int:case_id>")
@login_required
@admin_required
def detail(case_id):
    case = MovingCase.query.get_or_404(case_id)
    return render_template("moving_cases/detail.html", case=case)

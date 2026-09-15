from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.decorators import admin_required
from app.extensions import db
from app.models import Vendor

vendors_bp = Blueprint("vendors", __name__)


@vendors_bp.route("/")
@login_required
@admin_required
def list_view():
    vendors = Vendor.query.order_by(Vendor.created_at.desc()).all()
    return render_template("vendors/list.html", vendors=vendors)


@vendors_bp.route("/new", methods=["GET", "POST"])
@login_required
@admin_required
def new_vendor():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("업체명은 필수입니다.", "error")
            return redirect(url_for("vendors.new_vendor"))
        vendor = Vendor(
            name=name,
            country=request.form.get("country") or None,
            city=request.form.get("city") or None,
            contact_name=request.form.get("contact_name") or None,
            email=request.form.get("email") or None,
            phone=request.form.get("phone") or None,
            service_area=request.form.get("service_area") or None,
            is_active=bool(request.form.get("is_active")),
        )
        db.session.add(vendor)
        db.session.commit()
        flash(f"업체 '{name}'이(가) 등록되었습니다.", "success")
        return redirect(url_for("vendors.list_view"))
    return render_template("vendors/form.html")


@vendors_bp.route("/<int:vendor_id>")
@login_required
@admin_required
def detail(vendor_id):
    vendor = Vendor.query.get_or_404(vendor_id)
    from app.models import Issue
    related_issues = Issue.query.filter_by(vendor_id=vendor.id).order_by(Issue.occurred_at.desc()).all()
    total = len(related_issues)
    sla_over = sum(1 for i in related_issues if i.is_sla_breached)
    resolved = [i for i in related_issues if i.resolved_at]
    avg_hours = (
        round(sum((i.resolved_at - i.occurred_at).total_seconds() for i in resolved) / len(resolved) / 3600, 1)
        if resolved else None
    )
    sla_rate = round(100 * (total - sla_over) / total) if total else None
    return render_template(
        "vendors/detail.html", vendor=vendor, issues=related_issues,
        total=total, sla_over=sla_over, avg_hours=avg_hours, sla_rate=sla_rate,
    )

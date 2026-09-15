from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.decorators import admin_required
from app.extensions import db
from app.models import Customer

customers_bp = Blueprint("customers", __name__)


@customers_bp.route("/")
@login_required
@admin_required
def list_view():
    customers = Customer.query.order_by(Customer.created_at.desc()).all()
    return render_template("customers/list.html", customers=customers)


@customers_bp.route("/new", methods=["GET", "POST"])
@login_required
@admin_required
def new_customer():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("고객명은 필수입니다.", "error")
            return redirect(url_for("customers.new_customer"))
        customer = Customer(
            employee_id=request.form.get("employee_id") or None,
            name=name,
            email=request.form.get("email") or None,
            phone=request.form.get("phone") or None,
            nationality=request.form.get("nationality") or None,
        )
        db.session.add(customer)
        db.session.commit()
        flash(f"고객 '{name}'이(가) 등록되었습니다.", "success")
        return redirect(url_for("customers.list_view"))
    return render_template("customers/form.html")


@customers_bp.route("/<int:customer_id>")
@login_required
@admin_required
def detail(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    return render_template("customers/detail.html", customer=customer)

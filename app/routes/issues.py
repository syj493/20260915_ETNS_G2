import csv
import io
import os
import uuid
from datetime import datetime, timedelta

from flask import (
    Blueprint, abort, current_app, flash, redirect,
    render_template, request, send_file, url_for,
)
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename

from app.decorators import admin_required, can_access_issue
from app.extensions import db
from app.models import (
    Attachment, Customer, CustomerCommunication, Issue, IssueLog,
    IssueType, MovingCase, User, Vendor, VendorCommunication,
)
from app.models.issue import (
    CLOSED_STATUSES, LONG_PENDING_HOURS, PRIORITY_LABELS,
    SLA_WARNING_HOURS, STATUS_LABELS,
)
from app.services.numbering import next_issue_number

issues_bp = Blueprint("issues", __name__)


def _base_query():
    q = Issue.query
    if not current_user.is_admin:
        q = q.filter(Issue.assigned_user_id == current_user.id)
    return q


def _apply_filters(query):
    keyword = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    issue_type = request.args.get("issue_type", "")
    priority = request.args.get("priority", "")
    assignee_id = request.args.get("assignee_id", "")
    period = request.args.get("period", "")

    if keyword:
        like = f"%{keyword}%"
        query = query.join(Customer, Issue.customer_id == Customer.id).filter(
            db.or_(
                Issue.issue_number.like(like),
                Issue.title.like(like),
                Issue.description.like(like),
                Customer.name.like(like),
                Customer.employee_id.like(like),
            )
        )
    if status:
        query = query.filter(Issue.status == status)
    if issue_type:
        query = query.filter(Issue.issue_type == issue_type)
    if priority:
        query = query.filter(Issue.priority == priority)
    if assignee_id:
        query = query.filter(Issue.assigned_user_id == int(assignee_id))

    if period:
        now = datetime.utcnow()
        if period == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.filter(Issue.occurred_at >= start)
        elif period == "7d":
            query = query.filter(Issue.occurred_at >= now - timedelta(days=7))
        elif period == "30d":
            query = query.filter(Issue.occurred_at >= now - timedelta(days=30))
        elif period == "month":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            query = query.filter(Issue.occurred_at >= start)

    # MUST-02/05: 대시보드/사이드바에서 바로 연결되는 업무 현황별 빠른 필터
    view = request.args.get("view", "")
    if view:
        now = datetime.utcnow()
        if view == "urgent":
            query = query.filter(Issue.priority.in_(["URGENT", "HIGH"]), ~Issue.status.in_(CLOSED_STATUSES))
        elif view == "sla_over":
            query = query.filter(Issue.due_at < now, ~Issue.status.in_(CLOSED_STATUSES))
        elif view == "sla_warning":
            query = query.filter(
                Issue.due_at >= now,
                Issue.due_at <= now + timedelta(hours=SLA_WARNING_HOURS),
                ~Issue.status.in_(CLOSED_STATUSES),
            )
        elif view == "waiting_vendor":
            query = query.filter(Issue.status == "WAITING_VENDOR")
        elif view == "waiting_customer":
            query = query.filter(Issue.status == "WAITING_CUSTOMER")
        elif view == "long_pending":
            query = query.filter(
                Issue.occurred_at <= now - timedelta(hours=LONG_PENDING_HOURS),
                ~Issue.status.in_(CLOSED_STATUSES),
            )
        elif view == "unassigned":
            query = query.filter(Issue.assigned_user_id.is_(None), ~Issue.status.in_(CLOSED_STATUSES))

    return query


VIEW_TITLES = {
    "urgent": "긴급 이슈 (URGENT/HIGH)",
    "sla_over": "⚠ SLA 초과 이슈",
    "sla_warning": "⏰ SLA 임박 이슈",
    "waiting_vendor": "업체 답변 대기 이슈",
    "waiting_customer": "고객 답변 대기 이슈",
    "long_pending": "장기 미처리 이슈",
    "unassigned": "미배정 이슈",
}


ISSUES_PER_PAGE = 25


@issues_bp.route("/")
@login_required
def list_view():
    query = _apply_filters(_base_query()).options(
        joinedload(Issue.customer), joinedload(Issue.assigned_user)
    )
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Issue.occurred_at.desc()).paginate(
        page=page, per_page=ISSUES_PER_PAGE, error_out=False
    )
    staff_users = User.query.filter_by(role="staff").all()
    issue_types = IssueType.query.filter_by(is_active=True).order_by(IssueType.name).all()
    view = request.args.get("view", "")
    return render_template(
        "issues/list.html",
        issues=pagination.items,
        pagination=pagination,
        total_count=pagination.total,
        staff_users=staff_users,
        issue_types=issue_types,
        status_labels=STATUS_LABELS,
        priority_labels=PRIORITY_LABELS,
        filters=request.args,
        view_title=VIEW_TITLES.get(view),
    )


@issues_bp.route("/export.csv")
@login_required
def export_csv():
    query = _apply_filters(_base_query()).options(
        joinedload(Issue.customer), joinedload(Issue.moving_case),
        joinedload(Issue.assigned_user), joinedload(Issue.vendor),
    )
    issue_list = query.order_by(Issue.occurred_at.desc()).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "이슈ID", "고객", "출발지", "도착지", "이슈유형", "우선순위", "상태",
        "담당자", "업체", "발생일", "처리완료일", "처리시간(시간)", "SLA상태",
    ])
    for i in issue_list:
        mc = i.moving_case
        elapsed_hours = ""
        if i.resolved_at and i.occurred_at:
            elapsed_hours = round((i.resolved_at - i.occurred_at).total_seconds() / 3600, 1)
        writer.writerow([
            i.issue_number,
            i.customer.name if i.customer else "",
            f"{mc.departure_country} {mc.departure_city}" if mc else "",
            f"{mc.arrival_country} {mc.arrival_city}" if mc else "",
            i.issue_type,
            i.priority,
            i.status_display,
            i.assigned_user.name if i.assigned_user else "",
            i.vendor.name if i.vendor else "",
            i.occurred_at.strftime("%Y-%m-%d %H:%M") if i.occurred_at else "",
            i.resolved_at.strftime("%Y-%m-%d %H:%M") if i.resolved_at else "",
            elapsed_hours,
            "SLA 초과" if i.is_sla_breached else "정상",
        ])

    mem = io.BytesIO(buf.getvalue().encode("utf-8-sig"))
    return send_file(
        mem, mimetype="text/csv", as_attachment=True,
        download_name=f"issues_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv",
    )


@issues_bp.route("/new", methods=["GET", "POST"])
@login_required
def new_issue():
    if request.method == "POST":
        moving_case_id = request.form.get("moving_case_id")
        title = request.form.get("title", "").strip()
        issue_type = request.form.get("issue_type")
        priority = request.form.get("priority", "MEDIUM")
        description = request.form.get("description", "").strip()
        assigned_user_id = request.form.get("assigned_user_id") or None
        vendor_id = request.form.get("vendor_id") or None
        occurred_at_raw = request.form.get("occurred_at")

        mc = MovingCase.query.get(moving_case_id)
        if not mc or not title or not issue_type:
            flash("이사 건, 제목, 이슈 유형은 필수입니다.", "error")
            return redirect(url_for("issues.new_issue"))

        occurred_at = datetime.utcnow()
        if occurred_at_raw:
            try:
                occurred_at = datetime.strptime(occurred_at_raw, "%Y-%m-%dT%H:%M")
            except ValueError:
                pass

        issue = Issue(
            issue_number=next_issue_number(),
            moving_case_id=mc.id,
            customer_id=mc.customer_id,
            vendor_id=int(vendor_id) if vendor_id else mc.vendor_id,
            assigned_user_id=int(assigned_user_id) if assigned_user_id else None,
            title=title,
            description=description,
            issue_type=issue_type,
            priority=priority,
            status="ASSIGNED" if assigned_user_id else "NEW",
            occurred_at=occurred_at,
        )
        issue.recompute_due_at()
        db.session.add(issue)
        db.session.flush()

        db.session.add(
            IssueLog(issue_id=issue.id, user_id=current_user.id, action_type="created",
                     content=f"이슈 등록: {title}")
        )
        db.session.commit()
        flash(f"이슈 {issue.issue_number}가 등록되었습니다.", "success")
        return redirect(url_for("issues.detail", issue_id=issue.id))

    moving_cases = MovingCase.query.order_by(MovingCase.created_at.desc()).all()
    issue_types = IssueType.query.filter_by(is_active=True).order_by(IssueType.name).all()
    staff_users = User.query.filter_by(role="staff", is_active_flag=True).all()
    vendors = Vendor.query.filter_by(is_active=True).order_by(Vendor.name).all()
    return render_template(
        "issues/form.html", moving_cases=moving_cases, issue_types=issue_types,
        staff_users=staff_users, vendors=vendors,
    )


@issues_bp.route("/<int:issue_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_issue(issue_id):
    issue = Issue.query.get_or_404(issue_id)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        issue_type = request.form.get("issue_type")
        description = request.form.get("description", "").strip()
        occurred_at_raw = request.form.get("occurred_at")

        if not title or not issue_type:
            flash("제목과 이슈 유형은 필수입니다.", "error")
            return redirect(url_for("issues.edit_issue", issue_id=issue_id))

        occurred_at = issue.occurred_at
        if occurred_at_raw:
            try:
                occurred_at = datetime.strptime(occurred_at_raw, "%Y-%m-%dT%H:%M")
            except ValueError:
                pass

        old_occurred_display = issue.occurred_at.strftime("%Y-%m-%d %H:%M") if issue.occurred_at else "-"
        new_occurred_display = occurred_at.strftime("%Y-%m-%d %H:%M") if occurred_at else "-"

        changes = []
        if title != issue.title:
            changes.append(f"제목: {issue.title} → {title}")
        if issue_type != issue.issue_type:
            changes.append(f"유형: {issue.issue_type} → {issue_type}")
        if old_occurred_display != new_occurred_display:
            changes.append(f"발생일: {old_occurred_display} → {new_occurred_display}")

        issue.title = title
        issue.issue_type = issue_type
        issue.description = description
        issue.occurred_at = occurred_at
        issue.recompute_due_at()

        if changes:
            db.session.add(IssueLog(
                issue_id=issue.id, user_id=current_user.id, action_type="edited",
                content=" / ".join(changes),
            ))
        db.session.commit()
        flash("이슈 정보가 수정되었습니다.", "success")
        return redirect(url_for("issues.detail", issue_id=issue_id))

    issue_types = IssueType.query.filter_by(is_active=True).order_by(IssueType.name).all()
    return render_template("issues/edit.html", issue=issue, issue_types=issue_types)


@issues_bp.route("/<int:issue_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_issue(issue_id):
    issue = Issue.query.get_or_404(issue_id)
    issue_number = issue.issue_number

    for att in Attachment.query.filter_by(issue_id=issue.id).all():
        try:
            if os.path.exists(att.file_path):
                os.remove(att.file_path)
        except OSError:
            pass
        db.session.delete(att)

    IssueLog.query.filter_by(issue_id=issue.id).delete()
    CustomerCommunication.query.filter_by(issue_id=issue.id).delete()
    VendorCommunication.query.filter_by(issue_id=issue.id).delete()
    db.session.delete(issue)
    db.session.commit()

    flash(f"이슈 {issue_number}가 삭제되었습니다.", "success")
    return redirect(url_for("issues.list_view"))


@issues_bp.route("/<int:issue_id>")
@login_required
def detail(issue_id):
    issue = Issue.query.get_or_404(issue_id)
    if not can_access_issue(issue, current_user):
        abort(403)
    staff_users = User.query.filter_by(role="staff", is_active_flag=True).all()
    vendors = Vendor.query.filter_by(is_active=True).order_by(Vendor.name).all()
    return render_template(
        "issues/detail.html", issue=issue, staff_users=staff_users, vendors=vendors,
        status_labels=STATUS_LABELS,
    )


@issues_bp.route("/<int:issue_id>/status", methods=["POST"])
@login_required
def change_status(issue_id):
    issue = Issue.query.get_or_404(issue_id)
    if not can_access_issue(issue, current_user):
        abort(403)
    new_status = request.form.get("status")
    if new_status not in STATUS_LABELS:
        flash("잘못된 상태값입니다.", "error")
        return redirect(url_for("issues.detail", issue_id=issue_id))

    old_status = issue.status
    issue.status = new_status
    if new_status == "RESOLVED" and not issue.resolved_at:
        issue.resolved_at = datetime.utcnow()
    elif new_status == "CLOSED" and not issue.closed_at:
        issue.closed_at = datetime.utcnow()
        if not issue.resolved_at:
            issue.resolved_at = issue.closed_at
    elif new_status not in CLOSED_STATUSES:
        # 잘못 눌러서 해결/종결로 바꿨다가 되돌리는 경우, 남아있는 처리완료 시각을 정리한다.
        issue.resolved_at = None
        issue.closed_at = None

    db.session.add(IssueLog(
        issue_id=issue.id, user_id=current_user.id, action_type="status_changed",
        content=f"{STATUS_LABELS.get(old_status, old_status)} → {STATUS_LABELS.get(new_status, new_status)}",
    ))
    db.session.commit()
    flash("상태가 변경되었습니다.", "success")
    return redirect(url_for("issues.detail", issue_id=issue_id))


@issues_bp.route("/<int:issue_id>/priority", methods=["POST"])
@login_required
@admin_required
def change_priority(issue_id):
    issue = Issue.query.get_or_404(issue_id)
    new_priority = request.form.get("priority")
    if new_priority not in PRIORITY_LABELS:
        flash("잘못된 우선순위입니다.", "error")
        return redirect(url_for("issues.detail", issue_id=issue_id))

    old_priority = issue.priority
    issue.priority = new_priority
    issue.recompute_due_at()
    db.session.add(IssueLog(
        issue_id=issue.id, user_id=current_user.id, action_type="priority_changed",
        content=f"{old_priority} → {new_priority}",
    ))
    db.session.commit()
    flash("우선순위가 변경되었습니다.", "success")
    return redirect(url_for("issues.detail", issue_id=issue_id))


@issues_bp.route("/<int:issue_id>/assignee", methods=["POST"])
@login_required
@admin_required
def change_assignee(issue_id):
    issue = Issue.query.get_or_404(issue_id)
    assigned_user_id = request.form.get("assigned_user_id") or None
    old_user = issue.assigned_user.name if issue.assigned_user else "미배정"
    issue.assigned_user_id = int(assigned_user_id) if assigned_user_id else None
    if issue.assigned_user_id and issue.status == "NEW":
        issue.status = "ASSIGNED"
    new_user = User.query.get(issue.assigned_user_id).name if issue.assigned_user_id else "미배정"

    db.session.add(IssueLog(
        issue_id=issue.id, user_id=current_user.id, action_type="assignee_changed",
        content=f"{old_user} → {new_user}",
    ))
    db.session.commit()
    flash("담당자가 변경되었습니다.", "success")
    return redirect(url_for("issues.detail", issue_id=issue_id))


@issues_bp.route("/<int:issue_id>/vendor", methods=["POST"])
@login_required
@admin_required
def change_vendor(issue_id):
    issue = Issue.query.get_or_404(issue_id)
    vendor_id = request.form.get("vendor_id") or None
    old_vendor = issue.vendor.name if issue.vendor else "미지정"
    issue.vendor_id = int(vendor_id) if vendor_id else None
    new_vendor = Vendor.query.get(issue.vendor_id).name if issue.vendor_id else "미지정"

    db.session.add(IssueLog(
        issue_id=issue.id, user_id=current_user.id, action_type="vendor_changed",
        content=f"{old_vendor} → {new_vendor}",
    ))
    db.session.commit()
    flash("관련 업체가 변경되었습니다.", "success")
    return redirect(url_for("issues.detail", issue_id=issue_id))


@issues_bp.route("/<int:issue_id>/customer-communication", methods=["POST"])
@login_required
def add_customer_communication(issue_id):
    issue = Issue.query.get_or_404(issue_id)
    if not can_access_issue(issue, current_user):
        abort(403)
    comm_type = request.form.get("communication_type", "기타")
    content = request.form.get("content", "").strip()
    if not content:
        flash("응대 내용을 입력해주세요.", "error")
        return redirect(url_for("issues.detail", issue_id=issue_id))

    db.session.add(CustomerCommunication(
        issue_id=issue.id, user_id=current_user.id,
        communication_type=comm_type, content=content,
    ))
    db.session.add(IssueLog(
        issue_id=issue.id, user_id=current_user.id, action_type="customer_contact",
        content=f"[{comm_type}] {content[:60]}",
    ))
    db.session.commit()
    flash("고객 응대 내역이 기록되었습니다.", "success")
    return redirect(url_for("issues.detail", issue_id=issue_id))


@issues_bp.route("/<int:issue_id>/vendor-inquiry", methods=["POST"])
@login_required
def add_vendor_inquiry(issue_id):
    issue = Issue.query.get_or_404(issue_id)
    if not can_access_issue(issue, current_user):
        abort(403)
    content = request.form.get("content", "").strip()
    if not content:
        flash("문의 내용을 입력해주세요.", "error")
        return redirect(url_for("issues.detail", issue_id=issue_id))

    db.session.add(VendorCommunication(
        issue_id=issue.id, user_id=current_user.id, content=content, status="대기",
    ))
    if issue.status not in CLOSED_STATUSES:
        issue.status = "WAITING_VENDOR"
    db.session.add(IssueLog(
        issue_id=issue.id, user_id=current_user.id, action_type="vendor_inquiry",
        content=content[:80],
    ))
    db.session.commit()
    flash("업체 문의가 등록되었습니다.", "success")
    return redirect(url_for("issues.detail", issue_id=issue_id))


@issues_bp.route("/<int:issue_id>/vendor-inquiry/<int:vc_id>/response", methods=["POST"])
@login_required
def add_vendor_response(issue_id, vc_id):
    issue = Issue.query.get_or_404(issue_id)
    if not can_access_issue(issue, current_user):
        abort(403)
    vc = VendorCommunication.query.get_or_404(vc_id)
    response_content = request.form.get("response_content", "").strip()
    if not response_content:
        flash("업체 답변 내용을 입력해주세요.", "error")
        return redirect(url_for("issues.detail", issue_id=issue_id))

    vc.response_content = response_content
    vc.status = "답변 완료"
    vc.responded_at = datetime.utcnow()
    db.session.add(IssueLog(
        issue_id=issue.id, user_id=current_user.id, action_type="vendor_response",
        content=response_content[:80],
    ))
    db.session.commit()
    flash("업체 답변이 등록되었습니다.", "success")
    return redirect(url_for("issues.detail", issue_id=issue_id))


def _allowed_file(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config["ALLOWED_EXTENSIONS"]


@issues_bp.route("/<int:issue_id>/attachments", methods=["POST"])
@login_required
def upload_attachment(issue_id):
    issue = Issue.query.get_or_404(issue_id)
    if not can_access_issue(issue, current_user):
        abort(403)
    file = request.files.get("file")
    if not file or file.filename == "":
        flash("첨부할 파일을 선택해주세요.", "error")
        return redirect(url_for("issues.detail", issue_id=issue_id))
    if not _allowed_file(file.filename):
        flash("허용되지 않은 파일 형식입니다. (jpg, jpeg, png, pdf, xlsx, docx만 가능)", "error")
        return redirect(url_for("issues.detail", issue_id=issue_id))

    original = secure_filename(file.filename)
    ext = original.rsplit(".", 1)[-1].lower()
    stored = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], stored)
    file.save(save_path)
    size = os.path.getsize(save_path)

    db.session.add(Attachment(
        issue_id=issue.id, uploaded_by=current_user.id, original_filename=original,
        stored_filename=stored, file_path=save_path, file_size=size, mime_type=file.mimetype,
    ))
    db.session.add(IssueLog(
        issue_id=issue.id, user_id=current_user.id, action_type="attachment_added",
        content=original,
    ))
    db.session.commit()
    flash("파일이 첨부되었습니다.", "success")
    return redirect(url_for("issues.detail", issue_id=issue_id))


@issues_bp.route("/<int:issue_id>/attachments/<int:att_id>/download")
@login_required
def download_attachment(issue_id, att_id):
    issue = Issue.query.get_or_404(issue_id)
    if not can_access_issue(issue, current_user):
        abort(403)
    att = Attachment.query.filter_by(id=att_id, issue_id=issue_id).first_or_404()
    return send_file(att.file_path, as_attachment=True, download_name=att.original_filename)

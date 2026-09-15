from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import joinedload

from app.models import Issue, User
from app.models.issue import STATUS_LABELS

PRIORITY_RANK = {"URGENT": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def _hours_ago(dt):
    if not dt:
        return None
    delta = datetime.utcnow() - dt
    hours = int(delta.total_seconds() // 3600)
    if hours < 1:
        minutes = int(delta.total_seconds() // 60)
        return f"{max(minutes, 0)}분 전"
    return f"{hours}시간 전"


def _issue_payload(i, tag=None):
    return {
        "id": i.id,
        "issue_number": i.issue_number,
        "title": i.title,
        "issue_type": i.issue_type,
        "priority": i.priority,
        "priority_display": i.priority_display,
        "status": i.status,
        "status_display": i.status_display,
        "customer_name": i.customer.name if i.customer else "-",
        "assignee_name": i.assigned_user.name if i.assigned_user else "미배정",
        "elapsed": _hours_ago(i.occurred_at),
        "sla_breached": i.is_sla_breached,
        "sla_warning": i.is_sla_warning,
        "tag": tag,
    }


def build_dashboard_data():
    # customer/assigned_user는 action_needed 목록 생성 시 접근하므로 미리 JOIN해서 N+1을 방지
    all_issues = Issue.query.options(
        joinedload(Issue.customer), joinedload(Issue.assigned_user)
    ).all()
    open_issues = [i for i in all_issues if i.is_open]

    total_count = len(all_issues)
    in_progress_count = sum(1 for i in all_issues if i.status == "IN_PROGRESS")
    urgent_open_count = sum(1 for i in open_issues if i.priority in ("URGENT", "HIGH"))
    sla_breached = [i for i in open_issues if i.is_sla_breached]
    sla_warning = [i for i in open_issues if i.is_sla_warning]
    waiting_vendor = [i for i in open_issues if i.status == "WAITING_VENDOR"]
    waiting_customer = [i for i in open_issues if i.status == "WAITING_CUSTOMER"]
    long_pending = [i for i in open_issues if i.is_long_pending]
    unassigned = [i for i in open_issues if i.is_unassigned]

    # MUST-02/05: 지금 당장 확인해야 할 이슈 — SLA 초과 > SLA 임박 > 긴급(URGENT/HIGH) > 장기 미처리 순으로 태깅
    seen = set()
    action_needed = []
    for i in sorted(open_issues, key=lambda x: x.due_at or datetime.max):
        if i.is_sla_breached:
            tag = "SLA 초과"
        elif i.is_sla_warning:
            tag = "SLA 임박"
        elif i.priority in ("URGENT", "HIGH"):
            tag = "긴급"
        elif i.is_long_pending:
            tag = "장기 미처리"
        else:
            continue
        if i.id in seen:
            continue
        seen.add(i.id)
        action_needed.append(_issue_payload(i, tag=tag))
    action_needed.sort(key=lambda p: (
        0 if p["tag"] == "SLA 초과" else 1 if p["tag"] == "SLA 임박" else 2 if p["tag"] == "긴급" else 3,
        PRIORITY_RANK.get(p["priority"], 9),
    ))

    # 이슈 유형별 현황
    type_counts = defaultdict(int)
    for i in all_issues:
        type_counts[i.issue_type] += 1
    type_chart = [{"label": k, "value": v} for k, v in sorted(type_counts.items(), key=lambda x: -x[1])]

    # 상태별 현황
    status_counts = defaultdict(int)
    for i in all_issues:
        status_counts[i.status] += 1
    status_chart = [
        {"label": STATUS_LABELS.get(s, s), "value": status_counts.get(s, 0)}
        for s in list(STATUS_LABELS.keys())
    ]

    # 담당자별 처리 현황 (열린 이슈 기준) — MUST-05: 담당자별 미처리 이슈
    staff_users = User.query.filter_by(role="staff").all()
    assignee_rows = []
    for u in staff_users:
        assigned_open = [i for i in open_issues if i.assigned_user_id == u.id]
        sla_over = sum(1 for i in assigned_open if i.is_sla_breached)
        assignee_rows.append(
            {"name": u.name, "in_progress": len(assigned_open), "sla_over": sla_over}
        )
    assignee_rows.sort(key=lambda r: -r["in_progress"])

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "kpi": {
            "total": total_count,
            "in_progress": in_progress_count,
            "urgent": urgent_open_count,
            "sla_over": len(sla_breached),
            "sla_warning": len(sla_warning),
            "waiting_vendor": len(waiting_vendor),
            "waiting_customer": len(waiting_customer),
            "long_pending": len(long_pending),
            "unassigned": len(unassigned),
        },
        "action_needed": action_needed[:10],
        "type_chart": type_chart,
        "status_chart": status_chart,
        "assignee_rows": assignee_rows,
    }

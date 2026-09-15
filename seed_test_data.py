"""테스트용 가상 데이터 생성 (실제 고객 개인정보 사용 금지)."""
import random
from datetime import date, datetime, timedelta

from app import create_app
from app.extensions import db
from app.models import (
    Customer, CustomerCommunication, Issue, IssueLog, MovingCase,
    User, Vendor, VendorCommunication,
)
from app.models.issue import DEFAULT_ISSUE_TYPES, PRIORITY_SLA_HOURS, SLA_WARNING_HOURS
from app.services.numbering import next_case_number, next_issue_number

ROUTES = [
    ("대한민국", "서울", "미국", "뉴욕"),
    ("대한민국", "서울", "미국", "LA"),
    ("대한민국", "부산", "독일", "프랑크푸르트"),
    ("대한민국", "서울", "영국", "런던"),
    ("대한민국", "인천", "싱가포르", "싱가포르"),
    ("대한민국", "서울", "베트남", "호치민"),
    ("대한민국", "대전", "일본", "도쿄"),
    ("대한민국", "서울", "호주", "시드니"),
]

VENDOR_NAMES = [
    ("ABC Moving USA", "미국", "뉴욕"),
    ("Pacific Relocation", "미국", "LA"),
    ("EuroMove GmbH", "독일", "프랑크푸르트"),
    ("Britannia Movers", "영국", "런던"),
    ("Lion City Movers", "싱가포르", "싱가포르"),
    ("Saigon Logistics", "베트남", "호치민"),
    ("Tokyo Cargo Service", "일본", "도쿄"),
    ("Sydney Interstate Movers", "호주", "시드니"),
    ("Global Door-to-Door", "미국", "시카고"),
    ("SkyBridge Relocation", "대한민국", "서울"),
]

CUSTOMER_NAMES = [
    "김민준", "이서연", "박도윤", "최지우", "정하준", "강서준", "조은우", "윤지호",
    "장하윤", "임서윤", "한도현", "오유진", "신재원", "권나은", "황시우", "안수빈",
    "송민서", "전예준", "홍지안", "배주원",
]

PRIORITY_WEIGHTS = {"URGENT": 8, "HIGH": 22, "MEDIUM": 42, "LOW": 28}
STATUS_POOL = [
    "NEW", "ASSIGNED", "IN_PROGRESS", "IN_PROGRESS",
    "WAITING_VENDOR", "WAITING_CUSTOMER", "RESOLVED", "CLOSED", "CLOSED",
]

ISSUE_TITLE_TEMPLATES = {
    "파손": "물품 파손 신고",
    "분실": "박스 일부 분실",
    "배송 지연": "현지 배송 일정 지연",
    "일정 변경": "이사 일정 변경 요청",
    "통관": "통관 절차 지연",
    "포장": "포장 상태 불량 문의",
    "운송": "운송 중 화물 상태 문의",
    "배송": "배송 완료 확인 요청",
    "비용": "추가 비용 청구 문의",
    "서류": "필요 서류 미비 안내",
    "업체 대응": "현지 업체 응답 지연",
    "고객 문의": "일반 진행 상황 문의",
    "기타": "기타 문의사항",
}

VENDOR_INQUIRY_TEXT = "현재 화물의 위치와 예상 처리 일정을 확인해 주세요."
VENDOR_RESPONSE_TEXT = "현재 확인 중이며, 영업일 기준 1~2일 내 처리 예정입니다."
CUSTOMER_COMM_TEXT = "고객에게 현재 진행 상황을 안내하고 추가 확인 후 다시 연락드리기로 함."


def weighted_priority():
    items = list(PRIORITY_WEIGHTS.items())
    return random.choices([k for k, _ in items], weights=[v for _, v in items])[0]


def run(num_issues=55):
    app = create_app()
    with app.app_context():
        staff_users = User.query.filter_by(role="staff").all()
        if not staff_users:
            print("먼저 seed.py를 실행해서 담당자 계정을 생성해주세요.")
            return

        # --- 업체 ---
        vendors = []
        for name, country, city in VENDOR_NAMES:
            v = Vendor.query.filter_by(name=name).first()
            if not v:
                v = Vendor(
                    name=name, country=country, city=city,
                    contact_name=f"{name.split()[0]} Coordinator",
                    email=f"contact@{name.split()[0].lower()}.example.com",
                    phone="+1-555-0100", service_area=f"{country} 전역", is_active=True,
                )
                db.session.add(v)
                db.session.flush()
            vendors.append(v)

        # --- 고객 ---
        customers = []
        for idx, name in enumerate(CUSTOMER_NAMES):
            c = Customer.query.filter_by(name=name, employee_id=f"EMP{2000 + idx}").first()
            if not c:
                c = Customer(
                    employee_id=f"EMP{2000 + idx}", name=name,
                    email=f"user{2000 + idx}@example.com", phone="010-0000-0000",
                    nationality="대한민국",
                )
                db.session.add(c)
                db.session.flush()
            customers.append(c)
        db.session.commit()

        # --- 이사 건 ---
        cases = []
        for i in range(20):
            customer = customers[i % len(customers)]
            dep_c, dep_ci, arr_c, arr_ci = random.choice(ROUTES)
            vendor = next((v for v in vendors if v.country == arr_c), random.choice(vendors))
            assignee = random.choice(staff_users)
            scheduled = date.today() - timedelta(days=random.randint(-10, 60))
            case = MovingCase(
                case_number=next_case_number(),
                customer_id=customer.id,
                departure_country=dep_c, departure_city=dep_ci,
                arrival_country=arr_c, arrival_city=arr_ci,
                scheduled_date=scheduled,
                actual_moving_date=scheduled,
                estimated_arrival_date=scheduled + timedelta(days=14),
                vendor_id=vendor.id,
                assigned_user_id=assignee.id,
                status="IN_PROGRESS" if scheduled >= date.today() - timedelta(days=20) else "COMPLETED",
            )
            db.session.add(case)
            db.session.flush()
            cases.append(case)
        db.session.commit()

        # --- 이슈 ---
        created = 0
        for n in range(num_issues):
            case = random.choice(cases)
            issue_type = random.choice(DEFAULT_ISSUE_TYPES)
            priority = weighted_priority()
            status = random.choice(STATUS_POOL)
            sla_hours = PRIORITY_SLA_HOURS.get(priority, 24)

            roll = random.random()
            if status in ("RESOLVED", "CLOSED"):
                # 종결/해결 건은 SLA 판정에서 제외되므로 발생 시점은 폭넓게 분포
                occurred_at = datetime.utcnow() - timedelta(hours=random.randint(1, 400))
            elif roll < 0.20:
                # SLA 초과 시연
                occurred_at = datetime.utcnow() - timedelta(hours=sla_hours * random.uniform(1.5, 4))
            elif roll < 0.35:
                # SLA 임박(초과까지 SLA_WARNING_HOURS 이내) 시연
                remaining = random.uniform(0.2, SLA_WARNING_HOURS - 0.1)
                occurred_at = datetime.utcnow() - timedelta(hours=sla_hours - remaining)
            else:
                # 나머지 열린 이슈는 아직 SLA 이내
                occurred_at = datetime.utcnow() - timedelta(hours=sla_hours * random.uniform(0.05, 0.8))

            assignee = None if status == "NEW" else random.choice(staff_users)

            issue = Issue(
                issue_number=next_issue_number(),
                moving_case_id=case.id,
                customer_id=case.customer_id,
                vendor_id=case.vendor_id,
                assigned_user_id=assignee.id if assignee else None,
                title=ISSUE_TITLE_TEMPLATES.get(issue_type, "문의사항"),
                description=f"{case.route} 구간 이사 진행 중 발생한 {issue_type} 관련 이슈입니다.",
                issue_type=issue_type,
                priority=priority,
                status=status,
                occurred_at=occurred_at,
            )
            issue.recompute_due_at()
            if status == "RESOLVED":
                issue.resolved_at = occurred_at + timedelta(hours=random.randint(2, 48))
            elif status == "CLOSED":
                issue.resolved_at = occurred_at + timedelta(hours=random.randint(2, 48))
                issue.closed_at = issue.resolved_at + timedelta(hours=random.randint(1, 24))

            db.session.add(issue)
            db.session.flush()

            db.session.add(IssueLog(
                issue_id=issue.id, user_id=assignee.id if assignee else staff_users[0].id,
                action_type="created", content=f"이슈 등록: {issue.title}",
                created_at=occurred_at,
            ))
            if assignee:
                db.session.add(IssueLog(
                    issue_id=issue.id, user_id=assignee.id, action_type="assignee_changed",
                    content=f"미배정 → {assignee.name}", created_at=occurred_at + timedelta(minutes=20),
                ))

            if status in ("WAITING_VENDOR", "RESOLVED", "CLOSED") and random.random() < 0.7:
                vc = VendorCommunication(
                    issue_id=issue.id, user_id=assignee.id if assignee else staff_users[0].id,
                    content=VENDOR_INQUIRY_TEXT,
                    requested_at=occurred_at + timedelta(hours=1),
                )
                if status != "WAITING_VENDOR":
                    vc.status = "답변 완료"
                    vc.response_content = VENDOR_RESPONSE_TEXT
                    vc.responded_at = occurred_at + timedelta(hours=random.randint(2, 10))
                db.session.add(vc)

            if status in ("WAITING_CUSTOMER", "RESOLVED", "CLOSED") and random.random() < 0.6:
                db.session.add(CustomerCommunication(
                    issue_id=issue.id, user_id=assignee.id if assignee else staff_users[0].id,
                    communication_type=random.choice(["전화", "이메일", "메신저"]),
                    content=CUSTOMER_COMM_TEXT, created_at=occurred_at + timedelta(hours=3),
                ))

            created += 1

        db.session.commit()
        print(f"업체 {len(vendors)}개, 고객 {len(customers)}명, 이사 건 {len(cases)}건, 이슈 {created}건 생성 완료.")


if __name__ == "__main__":
    run()

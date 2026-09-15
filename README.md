# Moving CS Control Tower

해외이사 서비스 운영 중 발생하는 이슈와 고객 문의(CS)를 하나의 시스템에서 접수 → 배정 → 처리 → 종결까지 관리하는 웹 애플리케이션입니다.

## 설치 및 실행

```bash
cd MOVING_CS_MANAGER
pip install -r requirements.txt
python seed.py            # 관리자/담당자 계정, 이슈 유형 생성
python seed_test_data.py  # 테스트용 고객/업체/이사건/이슈 생성 (선택)
python run.py
```

브라우저에서 `http://127.0.0.1:5000` 접속.

## 계정 (seed.py 실행 후 콘솔에 출력됨)

- 관리자: `admin@movingcs.local`
- 담당자: `staff.shin@movingcs.local` 외 3명 (공통 비밀번호는 seed.py 출력 참고)

## 주요 기능 (MVP)

- 관리자 / 담당자 로그인 (세션 기반, 권한별 접근 제어)
- 이슈 등록 · 목록 · 상세 · 상태/우선순위/담당자/업체 변경
- 이슈 처리 Timeline, 고객 응대 기록, 업체 문의/답변 기록, 파일 첨부
- 우선순위 기반 SLA 자동 계산 및 초과 표시
- Dashboard (KPI 카드, 유형별/상태별 Chart.js 차트, 담당자별 현황, 10초 주기 자동 갱신)
- 검색/필터, CSV 다운로드
- 고객/이사 건/업체 관리 (관리자 전용)

## 권한

- **관리자**: 전체 이슈 조회/수정, 담당자·우선순위·업체 변경, 고객/이사건/업체 관리
- **담당자**: 본인에게 배정된 이슈만 조회/처리 가능 (서버 측에서 URL 조작으로 타인 이슈 접근 시 403 차단)

## 이번 버전에서 제외한 기능

실제 이메일/SMS 발송, 실제 AI API 연동, WebSocket/SSE 실시간 갱신(현재는 10초 polling), Excel(xlsx) 포맷 다운로드(현재는 Excel에서 바로 열리는 CSV)는 지시서의 MVP 제외 대상 또는 향후 확장 항목으로 이번 버전에는 포함하지 않았습니다.

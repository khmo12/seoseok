# 서석고등학교 교장 시뮬레이션 (웹 배포판)

원본 Colab/ipywidgets 스크립트를 **Flask 웹서버 + 순수 HTML/JS**로 새로 짠 버전입니다.
게임 데이터(12개월 이벤트, 캐릭터, 돌발 이벤트, 엔딩 로직)는 원본을 그대로 재사용했고,
UI와 서버 구조만 배포 가능한 형태로 다시 만들었습니다. Gemini API 키는 서버에서만 사용하며
브라우저(클라이언트)에는 절대 노출되지 않습니다.

## 파일 구조
```
app.py              Flask 서버 (API 라우트)
game_core.py         게임 데이터/로직/Gemini 연동 (원본 로직 재사용 + 버그 수정)
templates/index.html 메인 페이지
static/script.js     프론트엔드 게임 로직
static/style.css     스타일
requirements.txt     의존 패키지
.replit               Replit 배포 설정
```

## 원본 대비 고친 부분
1. `SIDE_EVENTS["goodwill"]` 블록에 있던 따옴표 이스케이프 오류로 인한 **실제 SyntaxError** 수정.
2. Gemini 모델 목록을 `gemini-1.5-flash` / `gemini-2.0-flash`(둘 다 2026년 기준 서비스 종료)에서
   **`gemini-2.5-flash` → `gemini-2.5-flash-lite`** 로 교체. (API 연동이 계속 실패하고
   키워드 판정으로만 빠지던 핵심 원인일 가능성이 높습니다.)
3. ipywidgets/Colab 전용 코드를 제거하고 Flask API + 세션 기반 상태 관리로 재구성.

## 로컬에서 실행하기
```bash
pip install -r requirements.txt
export GEMINI_API_KEY="여기에_키_입력"
python3 app.py
```
브라우저에서 http://localhost:5000 접속.

## Replit에 배포하기
1. 이 폴더 전체를 새 Replit 프로젝트(Python 템플릿)에 업로드 (또는 파일 하나씩 복붙).
2. 왼쪽 자물쇠(Secrets) 탭에서 `GEMINI_API_KEY` 등록 (Google AI Studio에서 발급한 키).
   - `SESSION_SECRET`도 임의의 랜덤 문자열로 등록해두면 더 안전합니다 (선택 사항).
3. 상단 "Run" 버튼으로 먼저 로컬 테스트 → 정상 작동 확인.
4. "Publish" 버튼으로 배포. **Secrets를 나중에 추가/수정했다면 반드시 Republish를 눌러
   재배포해야 배포본에도 반영됩니다.**
5. 배포 후 첫 화면에서 "AI(Gemini) 연결 테스트" 버튼으로 정상 연동 여부를 바로 확인할 수 있습니다.

## 다른 곳에 배포하고 싶다면
Flask + gunicorn 표준 구조라 Render, Railway, Fly.io, PythonAnywhere 등 어디든
`gunicorn app:app` 명령과 `GEMINI_API_KEY` 환경변수만 설정하면 동일하게 배포 가능합니다.

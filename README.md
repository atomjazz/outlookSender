# 로컬 Outlook 메일 발송기 (Outlook Mail Sender)

PySide6(Qt)와 Windows Outlook API를 결합하여 메일 템플릿 작성 및 일괄/개인화 메일 발송을 간편하게 처리해 주는 데스크톱 애플리케이션입니다.

## 🚀 주요 기능
- **Outlook 자동 연동**: Windows Outlook 프로그램과 연동하여 별도의 메일 서버 설정(SMTP/IMAP) 및 API 키 입력 없이 사용자의 메일 계정으로 안전하게 메일을 발송합니다.
- **다중 계정 지원**: Outlook에 등록된 다수의 발송 계정 중 원하는 계정을 선택하여 메일을 발송할 수 있습니다.
- **플레이스홀더 기능**: 메일 본문이나 제목에 `{고객명}`, `{회사명}` 등 사용자 정의 플레이스홀더를 삽입하여 동적인 개인화 메일을 구성할 수 있습니다.
- **서식 있는 메일 에디터**: HTML 메일 편집기를 내장하여 이미지 첨부, 링크 추가, 표(Table) 작성이 용이합니다.
- **로컬 템플릿 관리**: 자주 쓰는 메일 양식을 템플릿으로 저장하고 필요할 때마다 바로 불러올 수 있습니다.

## 🛠️ 개발 환경 및 요구 사항
- **OS**: Windows (pywin32를 이용하므로 Windows 환경에서만 작동합니다.)
- **필수 소프트웨어**: Microsoft Outlook 데스크톱 앱 (로그인 및 사용 가능한 상태여야 함)
- **Python**: v3.8 이상 추천
- **주요 의존성**:
  - `PySide6` (GUI 프레임워크)
  - `pywin32` (Windows Outlook COM 제어용)

## 📦 설치 및 실행 방법

### 1. 가상 환경 생성 및 진입 (선택 사항)
```bash
python -m venv .venv
.venv\Scripts\activate
```

### 2. 의존 라이브러리 설치
```bash
pip install -r requirements.txt
```

### 3. 프로그램 실행
```bash
python main.py
```

## 🏗️ 빌드 방법 (단일 실행 파일 생성)
이 프로젝트는 PyInstaller를 이용해 단독 실행형 `.exe` 파일로 빌드할 수 있습니다.

### 단일 파일로 빌드 (`OutlookMailSender.exe`)
```bash
pyinstaller build.spec
```
빌드가 완료되면 `dist/OutlookMailSender.exe` 파일이 생성됩니다.

### 폴더 구조 형태로 빌드
```bash
pyinstaller OutlookMailSender_Folder.spec
```

## 📂 프로젝트 디렉토리 구조
```text
email/
│
├── main.py                       # 프로그램 진입점
├── build.spec                    # PyInstaller 빌드 스펙 (단일 파일)
├── OutlookMailSender_Folder.spec # PyInstaller 빌드 스펙 (폴더 형태)
├── requirements.txt              # 파이썬 라이브러리 의존성 목록
├── .gitignore                    # Git 제외 설정 파일
│
└── app/                          # 애플리케이션 소스 디렉토리
    ├── core/                     # 핵심 로직 (Outlook 연동, 템플릿 병합, 로거 등)
    │   ├── logger.py
    │   ├── merge_engine.py
    │   ├── outlook_service.py
    │   ├── placeholder_manager.py
    │   └── template_manager.py
    │
    ├── storage/                  # 템플릿 및 설정 정보 로컬 저장공간
    │   ├── config.json           # 템플릿 메타데이터 저장 파일
    │   └── templates/            # 템플릿 본문(HTML) 저장 폴더
    │
    ├── ui/                       # PySide6 기반 UI 컴포넌트
    │   ├── main_window.py        # 메인 윈도우
    │   ├── editor_panel.py       # HTML 에디터 패널
    │   ├── placeholder_panel.py  # 플레이스홀더 목록 및 값 입력 패널
    │   ├── send_bar.py           # 수신인/참조/제목 입력 및 발송 영역
    │   └── template_list.py      # 메일 템플릿 목록 위젯
    │
    └── web/                      # 에디터 렌더링에 사용되는 웹 리소스 (HTML/CSS/JS)
```

## 🔒 보안 및 개인정보 관련 안내
- 본 프로그램은 사용자의 로컬에 설치된 Microsoft Outlook의 COM 인터페이스를 호출하여 작동하므로, **사용자의 계정 비밀번호나 API 토큰을 외부 서버 또는 로컬 파일에 임의로 저장하지 않습니다.**
- 메일 템플릿 파일(`app/storage/templates/`) 및 설정 파일(`app/storage/config.json`)은 로컬 PC에만 안전하게 보관되며, 기본적으로 Git 커밋 대상에서 제외(`.gitignore` 적용)되어 안심하고 GitHub에 프로젝트를 호스팅할 수 있습니다.

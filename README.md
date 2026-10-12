# Codex Toolbox MCP

Codex에서 쓰는 로컬 통합 MCP 서버입니다. Python 공식 MCP SDK의 stdio 전송을 사용하며, **57개 도구 · 자료 2개 · 작업 템플릿 3개**를 제공합니다. 파일·문서·데이터·Git·이미지·메모 기능은 별도 AI API 키 없이 실행됩니다.

## 빠른 시작

Windows와 Python 3.10 이상, Codex CLI가 필요합니다.

```powershell
git clone https://github.com/lshmax1104/codex-toolbox.git
cd codex-toolbox
.\Install-Codex.ps1
```

설치 스크립트가 전용 가상환경을 만들고 의존성을 설치한 뒤 `codex-toolbox`라는 이름으로 Codex에 등록합니다. `settings.example.json`에서 개인 설정인 `settings.json`을 생성합니다. 설치 후 Codex를 재시작하거나 MCP 연결을 다시 로드하세요.

사용 예시:

- “codex-toolbox의 toolbox_health로 기능과 허용 폴더를 확인해줘.”
- “이 폴더의 중복 파일을 찾아 목록으로 보여줘.”
- “이 CSV의 누락값과 숫자 통계를 분석해 엑셀로 저장해줘.”
- “이 PDF에서 1·3·5페이지만 새 파일로 저장해줘.”
- “이 저장소의 변경 내역과 최근 커밋을 확인해줘.”
- “프로젝트 결정 사항을 memory_put으로 저장해줘.”

기본 허용 폴더는 사용자 홈 아래 `Documents/Codex`입니다. 다른 프로젝트는 `settings.json`의 `allowed_roots`에 절대 경로를 추가하세요. 상대 경로는 첫 번째 허용 폴더를 기준으로 해석합니다.

## 구현된 기능

| 모듈 | 개수 | 도구 |
|---|---:|---|
| 시스템 | 5 | 상태·기능 조회, OS/CPU/메모리/디스크, 프로세스, 열린 포트, 실행 기록 |
| 파일 | 14 | 목록·내용 검색·읽기·쓰기·정확한 치환·복사·이동·폴더 생성·정보·해시·비교·중복 찾기·백업 목록·복구 |
| 압축 | 3 | ZIP 목록·생성·압축 해제 |
| 데이터 | 7 | JSON 읽기·쓰기, CSV 읽기·쓰기·통계, XLSX 읽기·쓰기 |
| 문서 | 3 | PDF/DOCX/텍스트 추출, PDF 병합, 페이지 선택·재정렬 |
| 이미지 | 3 | 이미지 정보, 크기 변경, PNG/JPEG/WEBP 변환 |
| SQLite | 3 | 스키마 조회, 매개변수 쿼리, 선택적으로 쓰기 |
| Git | 5 | 상태, diff, log, 커밋/파일 조회, 브랜치 목록 |
| 웹 | 2 | HTTP(S) 페이지 읽기·HTML 텍스트 추출, 파일 다운로드 |
| API 연동 | 2 | 설정된 서비스 목록, REST API 호출 |
| 메모 | 4 | 이름 공간별 저장·조회·검색·삭제, 재시작 후 유지 |
| 개발·작업 | 6 | 등록 명령 목록·실행, 백그라운드 시작·상태·취소·목록 |

전체 도구의 입력 스키마는 MCP 도구 검색으로 제공됩니다. `toolbox://capabilities` 자료에서도 이름과 설명을 확인할 수 있습니다.

자료: `toolbox://capabilities`, `toolbox://configuration`.

작업 템플릿: `inspect_project(path)`, `analyze_table(path)`, `research_documents(path, question)`.

## 재설치·다른 PC에서 설치

Windows, Python 3.10 이상, Codex CLI가 필요합니다. 소스 폴더를 원하는 위치에 놓고 PowerShell에서 실행하세요. `.venv`는 PC 간 복사하지 말고 다시 생성하세요.

```powershell
.\Install-Codex.ps1
# 프로젝트 폴더를 지정해서 설치
.\Install-Codex.ps1 -AllowedRoot 'D:\projects', 'C:\Users\사용자\Documents\Codex'
# 연결 등록 없이 환경만 설치
.\Install-Codex.ps1 -SkipRegister
```

`requirements.lock.txt`는 이 Windows/Python 3.10 환경에서 검증한 의존성 버전입니다. `requirements.txt`는 직접 의존성의 호환 범위입니다.

수동 연결:

```powershell
codex mcp add codex-toolbox -- '서버폴더\.venv\Scripts\python.exe' '서버폴더\server.py'
codex mcp get codex-toolbox
codex mcp list
```

설치 스크립트는 Codex 사용자 설정에 연결을 등록합니다. 개인 `settings.json`은 Git에서 제외하며, 공유할 설정 예제는 `settings.example.json`에 보관합니다.

## 기능 설정

설치 시 생성된 `settings.json`을 직접 편집하고 MCP 서버를 다시 로드하세요. 별도의 설정 파일을 쓰려면 서버 환경 변수 `TOOLBOX_CONFIG`를 해당 파일의 절대 경로로 설정합니다.

- `allowed_roots`: 읽기·쓰기 가능한 폴더. 최소 1개이며 모두 존재해야 합니다.
- `modules`: 활성화할 모듈 이름. 제외한 모듈은 도구 목록에서 빠집니다.
- `max_file_bytes`: 파일 입력·출력 및 HTTP 응답의 기본 제한, 20 MiB.
- `max_text_chars`: 텍스트 결과 제한, 60,000자. 페이지 방식으로 추가 내용을 읽으세요.
- `sqlite_writes`: 기본 `false`. `true`이면 DB 쓰기 도구를 사용할 수 있습니다.
- `network_allowed_hosts`: 웹·공개 API 요청에 허용할 호스트. 빈 배열이면 공개 호스트를 허용합니다.
- `web_allow_private_network`: 기본 `false`. `true`이면 `web_fetch`/`web_download`로 localhost·사설망에 접근할 수 있습니다.
- `services`: 외부 REST 서비스 설정.
- `tasks`: 실행할 고정 명령 배열과 타임아웃.
- `state_dir`: 선택 항목. 기본은 서버 폴더의 `.state`이며 메모·백업·실행 기록을 저장합니다.

서버 소스·설정·내부 상태와 `.git`, `.ssh`, `.codex`, `.venv`, `node_modules` 내부는 파일 도구에서 제외합니다. 기존 파일 덮어쓰기는 `overwrite=true`가 필요하며 이전 파일을 백업합니다. 이동 전에도 원본을 백업합니다. 백업은 `backups_restore`로 지정 경로에 복구합니다. SQLite 쓰기는 온라인 백업으로 기존의 커밋된 데이터를 저장합니다. 외부 프로그램의 변경에는 이 파일 백업이 적용되지 않습니다.

쓰기·삭제·외부 요청 도구에는 MCP 분류 정보를 붙였습니다. 실제 승인 동작은 Codex 설정을 따릅니다. 이 서버의 경로·네트워크 검사는 운영상의 접근 제한이며 별도의 OS 샌드박스를 대신하지 않습니다.

## 개발 명령 추가

기본 등록 명령은 Python·Node.js·Git 버전 확인입니다. 실제 테스트·빌드를 수행하려면 `tasks`에 고정 명령을 추가하세요.

```json
{
  "project-tests": {
    "description": "프로젝트 테스트 실행",
    "command": ["D:/projects/demo/.venv/Scripts/python.exe", "-m", "pytest", "-q"],
    "cwd": "D:/projects/demo",
    "timeout_seconds": 300
  }
}
```

`{python}`은 MCP 서버의 Python 실행 경로로 바뀝니다. 명령은 셸 문자열 대신 인수 배열로 실행합니다. 인수 자체에 사용자 입력을 붙이지 않습니다. `.cmd` 파일이나 셸 문법이 필요한 명령은 신뢰하는 실행 래퍼를 별도로 작성하세요. 설정된 명령은 프로젝트 코드 등을 실행할 수 있으므로 신뢰하는 프로젝트에 등록하세요.

`task_run`은 최대 30초 동안 기다립니다. 작업이 계속되면 반환된 ID를 `job_status`로 조회하거나 `job_cancel`로 취소합니다. 작업은 동시에 최대 4개, 기본 타임아웃은 120초, 최대 설정값은 3,600초입니다. 출력은 제한되며 완료된 작업을 포함해 최근 작업 기록을 메모리에 보관합니다. 작업은 MCP 연결 세션에 속하며 서버가 종료되면 실행 중인 작업을 정리합니다. 예약 실행과 재부팅 후 작업 복구는 구현하지 않았습니다.

## 외부 API 추가

예를 들어 GitHub 조회 기능을 추가하려면 `services`에 다음 항목을 넣습니다. 서버 자체가 GitHub OAuth 로그인을 수행하는 구조는 아닙니다.

```json
{
  "github": {
    "description": "GitHub REST API 조회",
    "base_url": "https://api.github.com",
    "methods": ["GET"],
    "token_env": "GITHUB_TOKEN",
    "token_prefix": "Bearer ",
    "headers": {"Accept": "application/vnd.github+json"}
  }
}
```

토큰은 설정 JSON에 넣지 말고 환경 변수로 설정하세요. Codex 사용자 설정의 `[mcp_servers.codex-toolbox]`에 `env_vars = ["GITHUB_TOKEN"]`도 추가해야 서버로 전달됩니다. 환경 변수 변경 후 Codex를 재시작하세요. 이후 `service_request(service="github", path="repos/소유자/저장소/issues")`로 호출할 수 있습니다. REST 쓰기가 필요한 서비스는 지원하는 메서드를 `methods`에 명시적으로 추가합니다.

서비스별 `allow_private_network=true`는 해당 서비스의 사설망 접근을 허용합니다. 인증 정보가 다른 주소로 전달되지 않도록 API 호출에서 HTTP 리다이렉트를 따라가지 않습니다.

## 검증

```powershell
.\.venv\Scripts\python.exe .\server.py --check
.\.venv\Scripts\python.exe .\smoke_test.py --workdir '테스트용폴더'
```

검증은 새 하위 폴더에서 별도 설정과 로컬 HTTP 테스트 서버를 사용합니다. 실제 stdio MCP 연결로 초기화·57개 도구 호출·자료·작업 템플릿을 검증하고, 파일·ZIP·JSON·CSV·XLSX·문서·이미지·SQLite·Git·HTTP·메모·작업 취소와 타임아웃을 확인합니다. 메모를 저장한 뒤 서버를 재시작해 유지되는지도 검사합니다. 인터넷 서비스의 실제 계정 연결을 검증하는 테스트는 아닙니다.

검증 결과를 파일로 남기려면 `--report verification.json`을 추가하세요. 검증 보고서와 임시 테스트 폴더는 Git에서 제외합니다.

## 범위와 제한

- 문서 요약·보고서 작성은 Codex가 추출 도구의 결과를 이용해 수행합니다. 서버에 별도 LLM API는 연결하지 않았습니다.
- 스캔 PDF OCR, 음성 받아쓰기·영상 처리, AI 이미지 생성, 브라우저 클릭 자동화, 이메일·캘린더 전용 연결, PostgreSQL/MySQL, 예약 스케줄러는 이번 버전에 포함하지 않았습니다.
- XLSX 수식을 재계산하지 않습니다. `xlsx_read(values_only=true)`는 저장된 계산값을 읽으며 값이 없거나 오래되었을 수 있습니다. `xlsx_write`는 문자열을 수식으로 실행하지 않고 그대로 저장합니다.
- DOCX는 문단·표 내용을 추출하며 원문 블록 순서와 레이아웃을 완전히 재현하지 않습니다. PDF 결과에는 OCR이 적용되지 않습니다.
- 파일 검색은 UTF-8 텍스트이며 디렉터리 스캔은 5,000개 항목으로 제한합니다. 대규모 자료는 하위 폴더로 나누어 조회하세요.
- 백업·메모는 로컬 디스크에 저장되며 자동 만료는 없습니다. 실행 기록은 도구 이름·성공 여부·시간만 기록하고 순환 저장합니다.
- 외부 서비스는 `services`에 추가하기 전까지 연결되지 않습니다. 웹 도구는 URL을 읽는 기능이며 검색 엔진을 제공하지 않습니다.

## 근거 문서

- [OpenAI 공식 MCP 연결 문서](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- [OpenAI 공식 MCP 서버 개발 문서](https://developers.openai.com/plugins/build/mcp-server)
- [공식 Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk)

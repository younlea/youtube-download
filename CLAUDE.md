# youtube-download

단일 파일 서비스 `app.py` (stdlib `http.server` + `yt-dlp` 서브프로세스). 의존성 추가 금지(가능한 stdlib 우선).

## 구조
- `JOBS`/`SEQ`: 진행 중 다운로드 상태. 성공 시 `SEQ` 증가 → 페이지 JS가 `/jobs` 폴링하다가 변화 감지 시 새로고침.
- 라우트: `GET /`(목록), `/files/<name>`(다운로드), `/jobs`; `POST /dl`(작업 시작), `/zip`, `/rm`.
- 인증: `AUTH="admin:pw,guest:pw"`, 첫 계정만 쓰기 가능(`self.ro`), 나머지는 `/dl`·`/rm` 403.
- 저장 폴더: `app.py` 옆 `download/` (gitignore).

## 주의할 점 (함정)
- yt-dlp는 `--js-runtimes node` 필요. `node`는 nvm 경로라 cron/systemd에선 PATH를 명시해야 함(`run.sh` 참고).
- `--progress-template "download:..."` 의 `download:` 접두어는 출력에 안 나옴 → 줄이 `  12.4%` 형태.
- Python 3.10: f-string 표현식 안에 백슬래시 불가 → 변수로 미리 계산.
- 파일명은 `os.path.basename` + 실제 존재 검사로 검증(경로 탈출 방지). 이 검증 유지.
- 포트 8765는 다른 서비스(jasna_gate)가 사용 중 → 이 서비스는 8780.

## 운영
- 부팅 자동 시작: user crontab `@reboot` → `run.sh`(비밀번호 포함, gitignore, `run.sh.example` 참고).
- 재시작: 8780 점유 PID를 kill 후 `./run.sh &`.
- 비밀번호/토큰을 코드·커밋에 넣지 말 것.
- 테스트 중 `download/` 안의 사용자 파일을 지우거나 옮기지 말 것(테스트는 임시 폴더/별도 파일 사용).

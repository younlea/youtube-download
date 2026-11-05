# YouTube → MP3

YouTube 링크를 넣으면 음원(mp3)만 받아서 `download/` 폴더에 저장하고, 웹에서 목록을 보고 내려받는 작은 웹 서비스.
파이썬 표준 라이브러리 + `yt-dlp` + `ffmpeg` 만 사용 (Flask 등 불필요).

## 기능
- 링크 붙여넣기 → 동시에 여러 개 다운로드, 링크별 `%` 진행 막대
- 저장 파일 목록 (날짜순 / 이름순), 개별·선택 개별·zip 다운로드, 선택 삭제
- 계정: 첫 번째 계정 = 관리자(저장·삭제 가능), 나머지 = 읽기 전용(보기·다운로드만)
- 페이지 아래에 아이들용 사용 가이드

## 준비
```
pip install -U --pre "yt-dlp[default]"   # YouTube가 자주 바뀌므로 최신 유지
sudo apt install ffmpeg
# Node.js 필요 (yt-dlp의 JS 챌린지 해결용, --js-runtimes node)
```

## 실행
```
AUTH='admin:비밀번호,guest:비밀번호' PORT=8780 python3 app.py
```
`http://서버IP:8780` 으로 접속. `AUTH` 없이 실행하면 누구나 접속 가능하니 외부 공개 시 반드시 설정.

## 부팅 시 자동 시작
`run.sh.example` 을 `run.sh` 로 복사해 계정/경로를 고친 뒤 (`chmod 700`), crontab에 추가:
```
@reboot sleep 20 && /경로/youtube-download/run.sh
```

## 주의
- HTTPS 미지원: 인터넷에 직접 열면 비밀번호가 평문 전송됨 → VPN(Tailscale/WireGuard) 권장.
- 다운로드가 403으로 실패하면 yt-dlp 업데이트부터.
- 저장 폴더 `download/` 는 git에 포함되지 않음.

#!/usr/bin/env python3
"""YouTube -> mp3 web service. Stdlib + yt-dlp + ffmpeg.
Run: AUTH=user:pass PORT=8765 python3 app.py
"""
import base64, html, io, json, os, re, subprocess, sys, threading, time, zipfile
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, quote, unquote, urlparse

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "download")
PORT = int(os.environ.get("PORT", 8765))
AUTH = os.environ.get("AUTH", "")  # "admin:pw,kid:pw"; first = admin, others read-only. REQUIRED if exposed to the internet
USERS = dict(u.split(":", 1) for u in AUTH.split(",") if u)
YT = re.compile(r"^https?://(www\.|m\.|music\.)?(youtube\.com|youtu\.be)/\S+$")
os.makedirs(DIR, exist_ok=True)

JOBS, SEQ = {}, [0]  # job id -> state; SEQ bumps on each success so the page knows to reload the file list

GUIDE = """<hr><h3>📖 사용 방법</h3>
<h4>1단계. YouTube에서 링크 복사하기</h4>
<p><b>📱 휴대폰·태블릿</b></p><ol>
<li>YouTube 앱에서 듣고 싶은 노래 영상을 엽니다.</li>
<li>영상 아래의 <b>공유</b>(↗ 화살표 모양) 버튼을 누릅니다.</li>
<li><b>링크 복사</b>를 누릅니다. 복사 끝!</li></ol>
<p><b>💻 컴퓨터</b></p><ol>
<li>영상을 연 뒤, 맨 위 주소창(https://www.youtube.com/... 으로 시작하는 줄)을 한 번 클릭합니다.</li>
<li>글자가 전부 파랗게 선택되면 <b>Ctrl + C</b> 를 누릅니다. (맥은 ⌘ + C)</li></ol>
<h4>2단계. 이 페이지에 붙여넣고 저장하기</h4><ol>
<li>맨 위 칸을 누르고 <b>붙여넣기</b>를 합니다. (<b>Ctrl + V</b> / 휴대폰은 칸을 길게 눌러 '붙여넣기')</li>
<li><b>저장</b> 버튼을 누릅니다.</li>
<li>초록색 막대가 100%까지 차면 아래 목록에 노래가 나타나요. 조금만 기다려 주세요! ⏳</li></ol>
<p>※ <b>sulac 계정</b>은 노래 듣기·받기만 할 수 있어요. 새 노래가 필요하면 복사한 링크를 부모님께 보내 주세요.</p>
<h4>3단계. 노래 파일 받기</h4><ul>
<li>노래 <b>제목을 누르면</b> 그 노래 하나를 받아요.</li>
<li>여러 곡은 ☑ 칸을 체크한 뒤 <b>선택 개별 다운로드</b>(곡마다 따로) 또는 <b>선택 zip으로 다운로드</b>(한 꾸러미로)를 누르세요.</li></ul>
<p>💡 <b>꼭 지켜요</b>: 이름 앞의 ☑를 잘못 눌러도 괜찮지만, 지우기 버튼은 부모님만 쓸 수 있어요.</p>"""

SCRIPT = """<script>
const esc=s=>s.replace(/[&<>"]/g,c=>'&#'+c.charCodeAt(0)+';'), q=document.getElementById('f1');
if(q)q.onsubmit=async e=>{e.preventDefault();const r=await fetch('/dl',{method:'POST',body:new URLSearchParams(new FormData(q))});
 document.getElementById('m').textContent=r.ok?'':await r.text();if(r.ok)q.reset();poll()};
async function dlEach(){const c=[...document.querySelectorAll('[name=f]:checked')];
 if(!c.length)return alert('선택된 파일이 없습니다');
 for(const x of c){const a=document.createElement('a');a.href='/files/'+encodeURIComponent(x.value);a.download=x.value;
  document.body.appendChild(a);a.click();a.remove();await new Promise(r=>setTimeout(r,400))}}
let seq=null;
async function poll(){const d=await (await fetch('/jobs')).json();
 if(seq!==null&&d.seq!==seq)return location.reload();seq=d.seq;
 document.getElementById('jobs').innerHTML=d.jobs.map(j=>`<div style="margin:8px 0;max-width:500px">${esc(j.url)}<br>
 ${j.err?'<b style="color:#c00">실패: '+esc(j.err)+'</b>':j.state+' '+j.pct+'%'}
 <div style="background:#ddd"><div style="background:#4a8;height:10px;width:${j.pct}%"></div></div></div>`).join('')}
setInterval(poll,1000);poll();
</script>"""


def run(jid, url):
    j = JOBS[jid]
    p = subprocess.Popen(
        ["yt-dlp", "--js-runtimes", "node", "--no-playlist", "-x", "--audio-format", "mp3", "--newline",
         "--progress-template", "download:%(progress._percent_str)s", "-o", f"{DIR}/%(title)s.%(ext)s", "--", url],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    for line in p.stdout:
        m = re.match(r"\s*([\d.]+)%\s*$", line)
        if m:
            j["pct"] = min(int(float(m[1])), 99)
        elif line.startswith("[ExtractAudio]"):
            j["state"] = "변환 중"
        elif "ERROR" in line:
            j["err"] = line.strip()[-200:]
    if p.wait() == 0:
        del JOBS[jid]
        SEQ[0] += 1
    else:
        j.setdefault("err", "알 수 없는 오류")
        j["t"] = time.time()


def page(msg="", sort="date", ro=False):
    files = [f for f in os.listdir(DIR) if not f.endswith((".part", ".ytdl"))]
    mt = lambda f: os.path.getmtime(os.path.join(DIR, f))
    files.sort(key=(lambda f: f.lower()) if sort == "name" else (lambda f: -mt(f)))
    rows = "".join(
        f'<li><label><input type=checkbox name=f value="{html.escape(f)}"> </label>'
        f'<a href="/files/{quote(f)}">{html.escape(f)}</a> <small>{time.strftime("%Y-%m-%d %H:%M", time.localtime(mt(f)))}</small></li>'
        for f in files
    )
    add = "" if ro else '<form id=f1><input name=url size=50 placeholder="https://youtu.be/..." required> <button>저장</button></form>'
    rm = "" if ro else f"<button formaction='/rm?sort={sort}' onclick=\"return confirm('선택한 파일을 삭제할까요?')\">선택 삭제</button>"
    return f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width">
<title>YT Audio</title><h2>YouTube → MP3</h2>
{add}
<p id=m style="color:#c00"></p><div id=jobs></div><p>{html.escape(msg)}</p><h3>저장된 파일 ({len(files)})</h3>
정렬: <a href="/?sort=date">날짜순</a> | <a href="/?sort=name">이름순</a>
<form method=post>
<p><label><input type=checkbox onclick="document.querySelectorAll('[name=f]').forEach(c=>c.checked=this.checked)"> 전체선택</label>
<button type=button onclick="dlEach()">선택 개별 다운로드</button>
<button formaction="/zip?sort={sort}">선택 zip으로 다운로드</button>
{rm}</p>
<ul>{rows}</ul></form>{GUIDE}{SCRIPT}""".encode()


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=DIR, **k)

    def ok(self):
        self.ro = False
        if not USERS:
            return True
        h = self.headers.get("Authorization", "")
        if h.startswith("Basic "):
            user, _, pw = base64.b64decode(h[6:] + "==").decode(errors="ignore").partition(":")
            if USERS.get(user) == pw and pw:
                self.ro = user != next(iter(USERS))  # only the first account may add/delete
                return True
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="yt"')
        self.end_headers()
        return False

    def page(self, msg="", sort="date"):
        return page(msg, sort, self.ro)

    def html(self, body):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.ok():
            return
        u = urlparse(self.path)
        if u.path.startswith("/files/"):
            self.path = "/" + u.path[7:]  # SimpleHTTPRequestHandler blocks ../ traversal
            return super().do_GET()
        if u.path == "/jobs":
            for k in [k for k, j in JOBS.items() if j.get("t", time.time()) < time.time() - 60]:
                del JOBS[k]  # drop failed jobs after 60s
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            return self.wfile.write(json.dumps({"seq": SEQ[0], "jobs": [] if self.ro else list(JOBS.values())}).encode())
        self.html(self.page(sort=parse_qs(u.query).get("sort", ["date"])[0]))

    def do_POST(self):
        if not self.ok():
            return
        u = urlparse(self.path)
        sort = parse_qs(u.query).get("sort", ["date"])[0]
        form = parse_qs(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 1 << 20)).decode())
        # only names that really exist directly in DIR (no path tricks)
        sel = [f for f in form.get("f", []) if f == os.path.basename(f) and os.path.isfile(os.path.join(DIR, f))]
        if self.ro and u.path in ("/dl", "/rm"):
            return self.send_error(403)
        if u.path == "/dl":
            url = form.get("url", [""])[0].strip()
            if not YT.match(url):
                self.send_response(400)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                return self.wfile.write("유효한 YouTube 링크가 아닙니다".encode())
            jid = str(time.time_ns())
            JOBS[jid] = {"url": url, "pct": 0, "state": "다운로드 중"}
            threading.Thread(target=run, args=(jid, url), daemon=True).start()
            self.send_response(204)
            return self.end_headers()
        if not sel:
            return self.html(self.page("선택된 파일이 없습니다", sort))
        if u.path == "/rm":
            for f in sel:
                os.remove(os.path.join(DIR, f))
            return self.html(self.page(f"{len(sel)}개 삭제됨", sort))
        if u.path == "/zip":  # ponytail: zip built in memory, fine for a few dozen mp3s
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
                for f in sel:
                    z.write(os.path.join(DIR, f), f)
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", "attachment; filename=audio.zip")
            self.send_header("Content-Length", str(buf.tell()))
            self.end_headers()
            self.wfile.write(buf.getvalue())


if __name__ == "__main__":
    if not AUTH:
        print("WARNING: AUTH not set -> no password!", file=sys.stderr)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()

#!/usr/bin/env python3
"""늘품컨설팅 홈페이지 - 유튜브 인증 영상 라이브러리 생성기

1) 채널 RSS에서 새 영상을 찾아 data/videos.json 에 추가합니다. (#shorts 는 짝이 되는 본편에 연결)
2) videos.html (영상 라이브러리)을 만들고, index.html 의 영상 섹션과 sitemap.xml 을 갱신합니다.

  python3 scripts/videos.py            # RSS 확인 + 페이지 생성
  python3 scripts/videos.py --offline  # RSS 없이 페이지만 다시 생성
"""
import html, json, re, sys, urllib.request, xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data' / 'videos.json'
CHANNEL_ID = 'UCMfy-g8mWkfncvQ9UUp9QLA'
HANDLE = '%EB%8A%98%ED%92%88%EC%BB%A8%EC%84%A4%ED%8C%85'  # @늘품컨설팅
CHANNEL_URL = f'https://www.youtube.com/@{HANDLE}'
SUB_URL = CHANNEL_URL + '?sub_confirmation=1'
SITE = 'https://npconsulting.biz/'

SERIES = {
    'c4': {'name': '4주기 요양병원 인증 기본강의', 'short': '4주기 요양병원', 'pl': 'PLA9V9Y0gsKzc', 'shorts_pl': 'PLM0ff1NZOSo4'},
    'basic': {'name': '기본인증제 조사항목·규정 핵심 정리', 'short': '기본인증제', 'pl': 'PLLCaJkXeSUIk', 'shorts_pl': 'PLEXTdGp6i53o'},
    'app': {'name': '손위생 모니터링 앱', 'short': '손위생 앱', 'pl': 'PLIjaHnsx7GLU'},
}
CHAPTERS = {
    'c4': {1: ('환자안전보장활동', 'PLLqwpDsfdu8Q'), 2: ('진료전달체계와 평가', 'PLPkxjz-OJlmA'), 3: ('환자진료', 'PLVOGX89HRV9M'),
           4: ('의약품관리', 'PLWw05Xu1jTEc'), 5: ('환자권리존중 및 보호', 'PLVTB6MeomK1s'), 6: ('질 향상 및 환자안전 활동', 'PLLeN9IUwj8xE'),
           7: ('감염관리', 'PLHpUt4esq-pU'), 8: ('경영 및 조직운영', 'PLOH3imnjDDks'), 9: ('인적자원관리', 'PLC9d3v_d1w-s'),
           10: ('시설 및 환경관리', 'PLIy-XBn3moQQ'), 11: ('의료정보·의무기록 관리', 'PLLvXDM_ug6AI'), 12: ('성과관리', 'PLWn21s_BAAak')},
    'basic': {0: ('기본인증제 개요', ''), 1: ('환자안전보장활동', 'PLRd0XtsCOVS4'), 2: ('진료전달체계와 평가', 'PLfLVaOMe6Acs'), 3: ('환자진료', 'PLA6uJhUbidEU'),
              4: ('의약품관리', 'PLTcyvUHLvBm8'), 5: ('수술 및 마취진정관리', 'PLHyrvRbsl5_k'), 6: ('환자권리존중 및 보호', 'PLZReKpNHtNOM'),
              7: ('환자안전 및 의료 질 향상 활동', 'PLe-NmTkzwndA'), 8: ('감염관리', 'PLAGonCb2iOpg'), 9: ('경영 및 조직운영', 'PLbQMRFVd3HfM'),
              10: ('인적자원관리', 'PLevMf3U0IHWE'), 11: ('시설 및 환경관리', 'PLUsMbmQbbvtE'), 12: ('의료정보·의무기록 관리', 'PLC4gNRfeLNgo')},
    'app': {'app': ('손위생 모니터링 앱', 'PLIjaHnsx7GLU')},
}
e = lambda s: html.escape(str(s), quote=True)


# ---------------------------------------------------------------- data
def parse_title(title):
    """채널 제목 규칙에 맞춰 시리즈·기준번호·질문·답·기준명을 나눕니다. 규칙에 안 맞으면 None."""
    title = re.sub(r'\s+', ' ', title).strip()
    if ' | ' not in title:
        return None
    left, right = [x.strip() for x in title.split(' | ', 1)]
    right = re.sub(r'\s*조사항목·규정 핵심 정리$|\s*\[4주기 요양병원 인증 기본강의\]$', '', right).strip()
    m = re.match(r'\[기본인증제 ([^\]]+)\]\s*(.*)', left)
    if m:
        code = m.group(1).strip()
        ch = 0 if code == '개요' else int(code.split('.')[0])
        return dict(s='basic', c=code, q=m.group(2), a='', i=right, ch=ch)
    if '손위생' in left and '앱' in left:
        return dict(s='app', c='', q=left, a='', i=right, ch='app')
    m = re.match(r'(\d+(?:\.\d+)+)\s+(.*)', right)
    if m:
        code, item = m.group(1), m.group(2)
        qa = re.match(r'(.*?\?)\s*(.*)', left)
        q, a = (qa.group(1), qa.group(2)) if qa else (left, '')
        return dict(s='c4', c=code, q=q, a=a, i=item, ch=int(code.split('.')[0]))
    return None


def norm(s):
    return re.sub(r'\s|#shorts', '', s, flags=re.I)


def update_from_rss(videos):
    url = f'https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (npconsulting.biz video sync)'})
    xml_text = urllib.request.urlopen(req, timeout=30).read()
    ns = {'a': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015'}
    entries = []
    for en in ET.fromstring(xml_text).findall('a:entry', ns):
        entries.append((en.find('yt:videoId', ns).text, en.find('a:title', ns).text or '', (en.find('a:published', ns).text or '')[:10]))
    known = {v['id'] for v in videos}
    known_shorts = {v.get('sh') for v in videos}
    added = 0
    top = min((v['n'] for v in videos), default=0)
    # 오래된 것부터 추가해야 최신 영상이 맨 앞(n이 가장 작음)에 옵니다
    for vid, title, pub in reversed(entries):
        if vid in known or vid in known_shorts or re.search(r'#shorts', title, re.I):
            continue
        p = parse_title(title)
        if not p:
            continue
        top -= 1
        videos.append(dict(id=vid, d='', **p, n=top, date=pub))
        added += 1
    # 쇼츠를 본편에 연결 (질문 앞부분이 같으면 짝)
    for vid, title, _ in entries:
        if not re.search(r'#shorts', title, re.I) or vid in known_shorts:
            continue
        k = norm(title)[:8]
        for v in videos:
            if 'sh' not in v and norm(v['q']).startswith(k):
                v['sh'] = vid
                break
    return added


# ---------------------------------------------------------------- helpers
def code_key(v):
    c = v['c']
    if not c or c == '개요':
        return (-1,)
    return tuple(int(x) for x in c.split('.'))


def watch_url(v, chapter_list=True):
    pl = CHAPTERS.get(v['s'], {}).get(v['ch'], ('', ''))[1] if chapter_list else ''
    return f'https://www.youtube.com/watch?v={v["id"]}' + (f'&list={pl}' if pl else '')


def chapter_name(v):
    return CHAPTERS[v['s']].get(v['ch'], ('', ''))[0]


YT_ICON = ('<svg class="yt" width="{w}" height="{w}" viewBox="0 0 24 24" aria-hidden="true"><path fill="#FF0033" d="M23 7.2a3 3 0 0 0-2.1-2.1C19 4.6 12 4.6 12 4.6s-7 0-8.9.5A3 3 0 0 0 1 7.2 31 31 0 0 0 .5 12 '
           '31 31 0 0 0 1 16.8a3 3 0 0 0 2.1 2.1c1.9.5 8.9.5 8.9.5s7 0 8.9-.5a3 3 0 0 0 2.1-2.1c.4-1.6.5-4.8.5-4.8s0-3.2-.5-4.8z"/><path fill="#fff" d="M9.8 15.1 15.5 12 9.8 8.9z"/></svg>')
yt_icon = lambda w=18: YT_ICON.format(w=w)


def card(v, lazy=True):
    sname = SERIES[v['s']]['short']
    code = f'<span class="vc-code">{e(v["c"])}</span>' if v['c'] else ''
    ans = f'<p class="vc-ans"><b>답</b>{e(v["a"])}</p>' if v['a'] else ''
    dur = f'<span class="vc-dur">{e(v["d"])}</span>' if v.get('d') else ''
    short = (f'<a class="vc-short" href="https://www.youtube.com/shorts/{v["sh"]}" target="_blank" rel="noopener">'
             f'{yt_icon(14)}1분 쇼츠로 보기</a>') if v.get('sh') else ''
    lazy_attr = ' loading="lazy"' if lazy else ''
    search = ' '.join([v['q'], v['a'], v['i'], v['c'], chapter_name(v), sname]).lower()
    return (f'<article class="vc" data-s="{v["s"]}" data-ch="{v["s"]}-{v["ch"]}" data-n="{v["n"]}" data-k="{e(search)}">'
            f'<a class="vc-link" href="{e(watch_url(v))}" target="_blank" rel="noopener" aria-label="{e(v["q"])} - 유튜브에서 보기">'
            f'<span class="vc-thumb"><img src="https://i.ytimg.com/vi/{v["id"]}/mqdefault.jpg" alt="" width="320" height="180"{lazy_attr}>'
            f'{dur}<span class="vc-play">{yt_icon(46)}</span></span>'
            f'<span class="vc-meta"><span class="vc-tag vc-{v["s"]}">{e(sname)}</span>{code}</span>'
            f'<span class="vc-q">{e(v["q"])}</span></a>{ans}<p class="vc-item">{e(v["i"])}</p>{short}</article>')


# ---------------------------------------------------------------- videos.html
PAGE_CSS = r'''
:root{--ink:#1F1D17;--paper:#FFFFFF;--stone:#F2F2EF;--line:#E3E1DA;--muted:#6B675C;--brass:#93762A;--brass-hi:#D2B65C;--wrap:1240px;--gut:32px}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:150px}
body{margin:0;background:var(--paper);color:var(--ink);font-family:"Pretendard Variable",Pretendard,-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;font-size:16px;line-height:1.6;letter-spacing:-0.01em;word-break:keep-all;-webkit-font-smoothing:antialiased}
a{color:inherit}button{font:inherit;color:inherit}
h1,h2,h3,p{margin:0}
:focus-visible{outline:2px solid var(--brass);outline-offset:3px;border-radius:6px}
.wrap{max-width:var(--wrap);margin:0 auto;padding:0 var(--gut)}
.hd{position:sticky;top:0;z-index:40;background:rgba(255,255,255,.88);-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);border-bottom:1px solid var(--line)}
.hd-in{height:68px;display:flex;align-items:center;gap:24px}
.hd img{height:28px;width:auto}
.hd-nav{margin-left:auto;display:flex;gap:22px;font-size:15px;font-weight:600}
.hd-nav a{text-decoration:none;color:#45423A}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:48px;padding:0 20px;border-radius:999px;font-size:15px;font-weight:700;text-decoration:none;border:0;cursor:pointer}
.btn-sub{background:#FF0033;color:#fff}.btn-sub:hover{background:#E0002D}
.btn-sub .yt path:first-child{fill:#fff}.btn-sub .yt path:last-child{fill:#FF0033}
.btn-ink{background:var(--ink);color:#fff}
.btn-line{border:1px solid #CFCBBF;background:#fff}
.hd .btn{min-height:40px;padding:0 16px;font-size:14px}
.top{padding:60px 0 40px}
.top-in{display:grid;grid-template-columns:6fr 6fr;gap:28px 56px;align-items:end}
.top h1{font-size:clamp(34px,4.6vw,58px);font-weight:700;line-height:1.15;letter-spacing:-0.05em}
.top-lead{margin-top:16px;font-size:18px;color:var(--muted);max-width:30em}
.top-cta{margin-top:28px;display:flex;flex-wrap:wrap;gap:10px}
.series{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.sc{display:flex;flex-direction:column;gap:6px;padding:22px;border-radius:22px;border:1px solid var(--line);background:#fff;text-align:left;cursor:pointer;transition:border-color .15s,background-color .15s}
.sc:hover{border-color:#CDBF94}
.sc[aria-pressed=true]{background:var(--ink);border-color:var(--ink);color:#fff}
.sc-num{font-size:34px;font-weight:700;letter-spacing:-0.05em;line-height:1}
.sc-num small{font-size:16px;margin-left:2px}
.sc b{font-size:16px;letter-spacing:-0.03em;line-height:1.4}
.sc span{font-size:13px;color:var(--muted)}
.sc[aria-pressed=true] span{color:#BDB8A8}
.bar{position:sticky;top:68px;z-index:30;background:rgba(255,255,255,.95);-webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.bar-in{display:flex;flex-direction:column;gap:10px;padding-top:12px;padding-bottom:12px}
.bar-row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.search{flex:1 1 300px;min-width:0;display:flex;align-items:center;gap:10px;min-height:46px;padding:0 16px;border:1px solid #D6D3C9;border-radius:12px;background:#fff}
.search input{flex:1;border:0;outline:0;font:inherit;font-size:16px;background:transparent;min-width:0}
.search svg{color:var(--muted);flex:0 0 auto}
.seg{display:inline-flex;padding:4px;border-radius:12px;background:var(--stone)}
.seg button{min-height:38px;padding:0 14px;border:0;border-radius:9px;background:transparent;font-size:14px;font-weight:600;color:#4A473E;cursor:pointer}
.seg button[aria-pressed=true]{background:#fff;color:var(--ink);box-shadow:0 1px 3px rgba(31,29,23,.15)}
.chips{display:flex;gap:8px;overflow-x:auto;scrollbar-width:none;padding-bottom:2px}
.chips::-webkit-scrollbar{display:none}
.chip{flex:0 0 auto;min-height:36px;padding:0 14px;border-radius:999px;border:1px solid var(--line);background:#fff;font-size:14px;font-weight:600;color:#4A473E;cursor:pointer;white-space:nowrap}
.chip small{margin-left:6px;font-weight:700;color:var(--brass)}
.chip[aria-pressed=true]{background:var(--ink);border-color:var(--ink);color:#fff}
.chip[aria-pressed=true] small{color:var(--brass-hi)}
.res{padding:24px 0 72px}
.res-count{font-size:15px;color:var(--muted);margin-bottom:8px}
.res-count b{color:var(--ink)}
.grp{padding-top:28px}
.grp[hidden]{display:none}
.grp-hd{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:8px 16px;padding-bottom:14px;margin-bottom:20px;border-bottom:2px solid var(--ink)}
.grp-hd h2{font-size:22px;font-weight:700;letter-spacing:-0.04em}
.grp-hd h2 span{font-size:14px;font-weight:700;color:var(--brass);margin-right:8px}
.grp-hd h2 small{font-size:14px;font-weight:600;color:var(--muted);margin-left:8px}
.grp-pl{display:inline-flex;align-items:center;gap:6px;font-size:14px;font-weight:700;text-decoration:none;color:#4A473E;min-height:36px}
.grp-pl:hover{color:var(--ink);text-decoration:underline}
.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:30px 20px}
.vc{display:flex;flex-direction:column;gap:8px;min-width:0}
.vc[hidden]{display:none}
.vc-link{display:flex;flex-direction:column;gap:10px;text-decoration:none}
.vc-thumb{position:relative;display:block;aspect-ratio:16/9;border-radius:14px;overflow:hidden;background:var(--stone)}
.vc-thumb img{width:100%;height:100%;object-fit:cover;transition:transform .35s}
.vc-link:hover .vc-thumb img{transform:scale(1.04)}
.vc-dur{position:absolute;right:8px;bottom:8px;padding:2px 7px;border-radius:6px;background:rgba(20,19,15,.82);color:#fff;font-size:12px;font-weight:700;font-variant-numeric:tabular-nums}
.vc-play{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;opacity:0;transition:opacity .2s;background:rgba(20,19,15,.18)}
.vc-link:hover .vc-play,.vc-link:focus-visible .vc-play{opacity:1}
.vc-meta{display:flex;gap:6px;align-items:center}
.vc-tag{display:inline-flex;align-items:center;min-height:22px;padding:0 8px;border-radius:999px;font-size:12px;font-weight:700}
.vc-basic{background:var(--ink);color:var(--brass-hi)}
.vc-c4{background:#EFE8D3;color:#6E5718}
.vc-app{background:#E3EEE6;color:#2E5A3B}
.vc-code{font-size:13px;font-weight:700;color:var(--brass);font-variant-numeric:tabular-nums}
.vc-q{font-size:17px;font-weight:700;line-height:1.45;letter-spacing:-0.03em}
.vc-link:hover .vc-q{text-decoration:underline;text-underline-offset:3px}
.vc-ans{font-size:14px;color:#4A473E;line-height:1.5}
.vc-ans b{color:var(--brass);margin-right:5px}
.vc-item{font-size:13px;color:var(--muted)}
.vc-short{align-self:flex-start;display:inline-flex;align-items:center;gap:6px;min-height:32px;padding:0 10px 0 8px;border-radius:999px;background:var(--stone);font-size:13px;font-weight:600;text-decoration:none;color:#4A473E}
.vc-short:hover{background:#E8E6DF}
.empty{padding:56px 0;text-align:center;color:var(--muted)}
.empty[hidden]{display:none}
.empty button{margin-top:14px;min-height:44px;padding:0 18px;border-radius:999px;border:1px solid var(--ink);background:transparent;font-weight:700;cursor:pointer}
.outro{background:var(--ink);color:#fff;padding:64px 0}
.outro-in{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:24px}
.outro h2{font-size:clamp(24px,3vw,34px);font-weight:700;letter-spacing:-0.04em;line-height:1.3}
.outro p{margin-top:8px;color:#BDB8A8}
.outro .btn-line{background:transparent;color:#fff;border-color:rgba(255,255,255,.4)}
.ft{padding:28px 0 40px;font-size:13px;color:var(--muted)}
@media (max-width:1080px){.grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media (max-width:860px){.top-in{grid-template-columns:1fr}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.hd-nav{display:none}.hd .btn{margin-left:auto}}
@media (max-width:560px){:root{--gut:20px}.bar{position:static}.search{flex-basis:100%}.bar-row .seg{flex:1 1 auto}.bar-row .seg button{flex:1}html{scroll-padding-top:84px !important}.grid{grid-template-columns:1fr}.top{padding-top:36px}.series{grid-template-columns:1fr 1fr;gap:10px}.sc{padding:16px}.sc-num{font-size:28px}}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}.vc-thumb img{transition:none}}
'''

PAGE_JS = r'''
(function(){
const st={s:'all',ch:'all',q:'',sort:'code'};
const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const cards=$$('.vc'),groups=$$('.grp'),flat=$('#flat');
const order=new Map(cards.map((c,i)=>[c,i]));
function chips(){
  const vis=cards.filter(c=>st.s==='all'||c.dataset.s===st.s);
  const counts={};vis.forEach(c=>counts[c.dataset.ch]=(counts[c.dataset.ch]||0)+1);
  const opts=[['all','전체',vis.length]];
  groups.forEach(g=>{if(counts[g.dataset.ch])opts.push([g.dataset.ch,g.dataset.label,counts[g.dataset.ch]])});
  if(!opts.some(o=>o[0]===st.ch))st.ch='all';
  $('#chips').innerHTML=opts.map(([k,l,n])=>`<button type="button" class="chip" data-chip="${k}" aria-pressed="${k===st.ch}">${l}<small>${n}</small></button>`).join('');
}
function apply(){
  chips();
  const q=st.q.trim().toLowerCase().split(/\s+/).filter(Boolean);
  let shown=0;
  cards.forEach(c=>{const ok=(st.s==='all'||c.dataset.s===st.s)&&(st.ch==='all'||c.dataset.ch===st.ch)&&q.every(w=>c.dataset.k.includes(w));c.hidden=!ok;if(ok)shown++;});
  if(st.sort==='new'){
    const list=cards.filter(c=>!c.hidden).sort((a,b)=>a.dataset.n-b.dataset.n);
    flat.querySelector('.grid').append(...list);flat.hidden=false;groups.forEach(g=>g.hidden=true);
  }else{
    cards.slice().sort((a,b)=>order.get(a)-order.get(b)).forEach(c=>c._home.append(c));flat.hidden=true;
    groups.forEach(g=>g.hidden=!g.querySelector('.vc:not([hidden])'));
  }
  $('#count').innerHTML=`<b>${shown}편</b>의 영상`+(st.q?` · “${st.q.replace(/[<>&"]/g,'')}” 검색 결과`:'');
  $('#empty').hidden=shown>0;
  $$('[data-series]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.series===st.s));
  $$('[data-sort]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.sort===st.sort));
  const u=new URL(location);['s','ch','q'].forEach(k=>{const v=st[k];if(v&&v!=='all')u.searchParams.set(k,v);else u.searchParams.delete(k)});history.replaceState(null,'',u);
}
cards.forEach(c=>c._home=c.parentElement);
document.addEventListener('click',ev=>{
  const s=ev.target.closest('[data-series]');if(s){st.s=s.dataset.series;st.ch='all';apply();return}
  const ch=ev.target.closest('[data-chip]');if(ch){st.ch=ch.dataset.chip;apply();if(st.ch!=='all'&&st.sort==='code'){const g=document.querySelector(`.grp[data-ch="${st.ch}"]`);if(g)g.scrollIntoView({block:'start'})}return}
  const o=ev.target.closest('[data-sort]');if(o){st.sort=o.dataset.sort;apply();return}
  if(ev.target.closest('#reset')){st.s='all';st.ch='all';st.q='';$('#q').value='';apply()}
});
let t;$('#q').addEventListener('input',ev=>{clearTimeout(t);t=setTimeout(()=>{st.q=ev.target.value;apply()},150)});
const p=new URLSearchParams(location.search);
if(['c4','basic','app'].includes(p.get('s')))st.s=p.get('s');
if(p.get('ch'))st.ch=p.get('ch');
if(p.get('q')){st.q=p.get('q');$('#q').value=st.q}
apply();
})();
'''


def build_videos_page(videos):
    total = len(videos)
    n_sh = sum(1 for v in videos if v.get('sh'))
    cnt = {s: sum(1 for v in videos if v['s'] == s) for s in SERIES}
    groups_html = []
    for s in ('basic', 'c4', 'app'):
        chs = sorted({v['ch'] for v in videos if v['s'] == s}, key=lambda x: -1 if x == 'app' else x)
        for ch in chs:
            items = sorted([v for v in videos if v['s'] == s and v['ch'] == ch], key=code_key)
            name, pl = CHAPTERS[s].get(ch, ('', ''))
            label = (f'{SERIES[s]["short"]} {ch}장' if isinstance(ch, int) and ch > 0 else name)
            num = f'<span>{SERIES[s]["short"]} {ch}장</span>' if isinstance(ch, int) and ch > 0 else f'<span>{SERIES[s]["short"]}</span>'
            first = items[0]['id']
            pl_link = (f'<a class="grp-pl" href="https://www.youtube.com/watch?v={first}&amp;list={pl}" target="_blank" rel="noopener">'
                       f'{yt_icon(16)}재생목록으로 이어 보기</a>') if pl else ''
            groups_html.append(
                f'<section class="grp" data-ch="{s}-{ch}" data-label="{e(label)}" aria-labelledby="g-{s}-{ch}">'
                f'<div class="grp-hd"><h2 id="g-{s}-{ch}">{num}{e(name)}<small>{len(items)}편</small></h2>{pl_link}</div>'
                f'<div class="grid">{"".join(card(v) for v in items)}</div></section>')
    ld = {
        '@context': 'https://schema.org', '@type': 'CollectionPage', 'name': '의료기관 인증 영상 라이브러리',
        'url': SITE + 'videos.html', 'inLanguage': 'ko',
        'publisher': {'@type': 'Organization', 'name': '늘품컨설팅', 'url': SITE, 'sameAs': [CHANNEL_URL]},
        'mainEntity': {'@type': 'ItemList', 'numberOfItems': total, 'itemListElement': [
            {'@type': 'ListItem', 'position': i + 1, 'url': f'https://www.youtube.com/watch?v={v["id"]}',
             'name': (f'[{SERIES[v["s"]]["short"]} {v["c"]}] ' if v['c'] else '') + v['q']}
            for i, v in enumerate(sorted(videos, key=lambda v: v['n']))]},
    }
    head_title = '의료기관 인증 영상 라이브러리 | 4주기 요양병원·기본인증제 | 늘품컨설팅'
    desc = (f'4주기 요양병원 인증 기본강의 {cnt["c4"]}편, 기본인증제 조사항목·규정 핵심 정리 {cnt["basic"]}편. '
            '조사위원이 실제로 묻는 질문을 기준 번호와 장별로 골라 유튜브에서 바로 보세요.')
    return f'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(head_title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{SITE}videos.html">
<meta property="og:type" content="website">
<meta property="og:title" content="의료기관 인증 영상 라이브러리 | 늘품컨설팅">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{SITE}videos.html">
<meta property="og:image" content="https://i.ytimg.com/vi/{sorted(videos, key=lambda v: v['n'])[0]['id']}/hqdefault.jpg">
<meta property="og:locale" content="ko_KR">
<link rel="icon" href="favicon.png">
<link rel="preconnect" href="https://i.ytimg.com">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">
<style>{PAGE_CSS}</style>
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
</head>
<body>
<header class="hd"><div class="wrap hd-in">
  <a href="./" aria-label="늘품컨설팅 홈으로"><img src="neulpum-logo.png" alt="늘품 NEULPUM Medical Total Solutions"></a>
  <nav class="hd-nav" aria-label="주요 메뉴"><a href="./#services">컨설팅 서비스</a><a href="./#basic">기본인증</a><a href="./#contact">상담 신청</a></nav>
  <a class="btn btn-sub" href="{SUB_URL}" target="_blank" rel="noopener">{yt_icon(18)}채널 구독하기</a>
</div></header>
<main>
<section class="top"><div class="wrap top-in">
  <div>
    <h1>영상으로 보는<br>의료기관 인증 기준</h1>
    <p class="top-lead">조사위원이 실제로 묻는 질문을 기준별 10분 안팎의 영상으로 정리했습니다. 기준 번호나 궁금한 내용으로 찾아 유튜브에서 바로 보세요.</p>
    <div class="top-cta">
      <a class="btn btn-sub" href="{SUB_URL}" target="_blank" rel="noopener">{yt_icon(20)}유튜브 채널 구독하기</a>
      <a class="btn btn-line" href="{CHANNEL_URL}/playlists" target="_blank" rel="noopener">재생목록 전체 보기</a>
    </div>
  </div>
  <div class="series" role="group" aria-label="시리즈 선택">
    <button type="button" class="sc" data-series="basic" aria-pressed="false"><span class="sc-num">{cnt["basic"]}<small>편</small></span><b>기본인증제<br>조사항목·규정 핵심 정리</b><span>2026년 11월 시행 기본인증 대비</span></button>
    <button type="button" class="sc" data-series="c4" aria-pressed="false"><span class="sc-num">{cnt["c4"]}<small>편</small></span><b>4주기 요양병원<br>인증 기본강의</b><span>기준별 Q&amp;A 강의</span></button>
  </div>
</div></section>

<div class="bar"><div class="wrap bar-in">
  <div class="bar-row">
    <label class="search"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg><input id="q" type="search" placeholder="예) 낙상, 손위생, 동의서, 7.3" aria-label="영상 검색"></label>
    <div class="seg" role="group" aria-label="시리즈"><button type="button" data-series="all" aria-pressed="true">전체</button><button type="button" data-series="basic" aria-pressed="false">기본인증제</button><button type="button" data-series="c4" aria-pressed="false">4주기 요양병원</button></div>
    <div class="seg" role="group" aria-label="정렬"><button type="button" data-sort="code" aria-pressed="true">기준 순서</button><button type="button" data-sort="new" aria-pressed="false">최신순</button></div>
  </div>
  <div class="chips" id="chips" role="group" aria-label="장 선택"></div>
</div></div>

<div class="res"><div class="wrap">
  <p class="res-count" id="count" aria-live="polite"><b>{total}편</b>의 영상 · 쇼츠 요약 {n_sh}편</p>
  <section class="grp" id="flat" hidden aria-label="최신순"><div class="grid"></div></section>
  {"".join(groups_html)}
  <div class="empty" id="empty" hidden><p>찾는 영상이 없습니다. 다른 단어로 검색하거나 필터를 해제해 보세요.</p><button type="button" id="reset">필터 해제</button></div>
</div></div>

<section class="outro"><div class="wrap outro-in">
  <div><h2>새 강의가 올라오면 바로 알려 드릴게요</h2><p>채널을 구독하고 알림을 켜 두시면 기준별 새 영상을 가장 먼저 받아 볼 수 있습니다.</p></div>
  <div class="top-cta" style="margin-top:0">
    <a class="btn btn-sub" href="{SUB_URL}" target="_blank" rel="noopener">{yt_icon(20)}채널 구독하기</a>
    <a class="btn btn-line" href="./#contact">인증 컨설팅 상담 신청</a>
  </div>
</div></section>
</main>
<footer class="ft"><div class="wrap">© NEULPUM Consulting · <a href="./">npconsulting.biz</a> · 유튜브 <a href="{CHANNEL_URL}" target="_blank" rel="noopener">의료기관 인증 스토리</a></div></footer>
<script>{PAGE_JS}</script>
</body>
</html>
'''


# ---------------------------------------------------------------- index.html teaser
TEASER_CSS = r'''
.vt{background:var(--stone,#F2F2EF)}
.vt-head{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:end;gap:20px 48px;margin-bottom:40px}
.vt-head p{margin-top:16px;max-width:32em;font-size:18px;color:#6B675C}
.vt-cta{display:flex;flex-wrap:wrap;gap:10px}
.vt-sub{background:#FF0033;color:#fff}.vt-sub:hover{background:#E0002D}
.vt-sub .yt path:first-child{fill:#fff}.vt-sub .yt path:last-child{fill:#FF0033}
.vt-series{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:44px}
.vt-sc{display:flex;align-items:center;gap:20px;padding:24px 26px;border-radius:24px;background:#fff;text-decoration:none;border:1px solid #E3E1DA;transition:border-color .2s}
.vt-sc:hover{border-color:#CDBF94}
.vt-sc b{display:block;font-size:20px;letter-spacing:-0.035em;line-height:1.35}
.vt-sc span{font-size:14px;color:#6B675C}
.vt-num{margin-left:auto;font-size:40px;font-weight:700;letter-spacing:-0.05em;line-height:1;white-space:nowrap}
.vt-num small{font-size:16px;margin-left:2px}
.vt-latest h3{font-size:18px;font-weight:700;letter-spacing:-0.03em;margin-bottom:18px}
.vt-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:24px 20px}
.vt .vc{display:flex;flex-direction:column;gap:8px;min-width:0}
.vt .vc-link{display:flex;flex-direction:column;gap:10px;text-decoration:none}
.vt .vc-thumb{position:relative;display:block;aspect-ratio:16/9;border-radius:14px;overflow:hidden;background:#E8E6DF}
.vt .vc-thumb img{width:100%;height:100%;object-fit:cover;transition:transform .35s}
.vt .vc-link:hover .vc-thumb img{transform:scale(1.04)}
.vt .vc-dur{position:absolute;right:8px;bottom:8px;padding:2px 7px;border-radius:6px;background:rgba(20,19,15,.82);color:#fff;font-size:12px;font-weight:700}
.vt .vc-play{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;opacity:0;transition:opacity .2s;background:rgba(20,19,15,.18)}
.vt .vc-link:hover .vc-play{opacity:1}
.vt .vc-meta{display:flex;gap:6px;align-items:center}
.vt .vc-tag{display:inline-flex;align-items:center;min-height:22px;padding:0 8px;border-radius:999px;font-size:12px;font-weight:700}
.vt .vc-basic{background:#1F1D17;color:#D2B65C}.vt .vc-c4{background:#EFE8D3;color:#6E5718}.vt .vc-app{background:#E3EEE6;color:#2E5A3B}
.vt .vc-code{font-size:13px;font-weight:700;color:#93762A}
.vt .vc-q{font-size:16px;font-weight:700;line-height:1.45;letter-spacing:-0.03em;color:#1F1D17}
.vt .vc-ans{font-size:14px;color:#4A473E;line-height:1.5}.vt .vc-ans b{color:#93762A;margin-right:5px}
.vt .vc-item{font-size:13px;color:#6B675C}
.vt .vc-short{align-self:flex-start;display:inline-flex;align-items:center;gap:6px;min-height:32px;padding:0 10px 0 8px;border-radius:999px;background:#fff;font-size:13px;font-weight:600;text-decoration:none;color:#4A473E}
.vt-more{margin-top:36px;display:flex;justify-content:center}
@media (max-width:960px){.vt-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.vt-series{grid-template-columns:1fr}}
@media (max-width:640px){.vt-grid{grid-template-columns:1fr}.vt-grid .vc:nth-child(n+3){display:none}.vt-sc{padding:20px}.vt-num{font-size:32px}}
'''


def build_teaser(videos):
    cnt = {s: sum(1 for v in videos if v['s'] == s) for s in SERIES}
    latest = sorted(videos, key=lambda v: v['n'])[:4]
    return f'''<!--VIDEOS-START-->
<style>{TEASER_CSS}</style>
<section class="sec vt" id="videos">
  <div class="wrap">
    <div class="vt-head">
      <div><h2 class="h2">영상으로 보는<br>의료기관 인증 기준</h2>
      <p>조사위원이 실제로 묻는 질문을 기준별 영상으로 정리했습니다. 늘품 유튜브 채널 '의료기관 인증 스토리'에서 무료로 보실 수 있습니다.</p></div>
      <div class="vt-cta">
        <a class="btn vt-sub" href="{SUB_URL}" target="_blank" rel="noopener">{yt_icon(20)}채널 구독하기</a>
        <a class="btn btn-ink" href="videos.html">영상 {len(videos)}편 전체 보기</a>
      </div>
    </div>
    <div class="vt-series">
      <a class="vt-sc" href="videos.html?s=basic"><div><b>기본인증제<br>조사항목·규정 핵심 정리</b><span>1장~12장 · 2026년 11월 시행 대비</span></div><span class="vt-num">{cnt["basic"]}<small>편</small></span></a>
      <a class="vt-sc" href="videos.html?s=c4"><div><b>4주기 요양병원<br>인증 기본강의</b><span>1장~12장 · 기준별 Q&amp;A</span></div><span class="vt-num">{cnt["c4"]}<small>편</small></span></a>
    </div>
    <div class="vt-latest"><h3>최근 올라온 영상</h3>
      <div class="vt-grid">{"".join(card(v) for v in latest)}</div>
    </div>
    <div class="vt-more"><a class="btn btn-line" href="videos.html">장별·기준별로 골라 보기</a></div>
  </div>
</section>
<!--VIDEOS-END-->'''


def update_index(videos):
    p = ROOT / 'index.html'
    s = p.read_text(encoding='utf-8')
    block = build_teaser(videos)
    new = re.sub(r'<!--VIDEOS-START-->.*?<!--VIDEOS-END-->', lambda m: block, s, flags=re.S)
    if new == s and '<!--VIDEOS-START-->' not in s:
        raise SystemExit('index.html 에 <!--VIDEOS-START--> 표시가 없습니다')
    p.write_text(new, encoding='utf-8')


def build_sitemap():
    today = date.today().isoformat()
    urls = [('', '1.0'), ('videos.html', '0.9'), ('app.html', '0.6'), ('privacy.html', '0.3')]
    body = ''.join(f'<url><loc>{SITE}{u}</loc><lastmod>{today}</lastmod><priority>{pr}</priority></url>' for u, pr in urls)
    (ROOT / 'sitemap.xml').write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>\n', encoding='utf-8')


def main():
    before = DATA.read_text(encoding='utf-8')
    videos = json.loads(before)
    if '--offline' not in sys.argv:
        try:
            added = update_from_rss(videos)
            print(f'새 영상 {added}편')
        except Exception as ex:  # RSS 실패해도 페이지는 다시 만듭니다
            print('RSS 확인 실패:', ex)
    after = json.dumps(videos, ensure_ascii=False, indent=1)
    DATA.write_text(after, encoding='utf-8')
    (ROOT / 'videos.html').write_text(build_videos_page(videos), encoding='utf-8')
    update_index(videos)
    if after != before or not (ROOT / 'sitemap.xml').exists() or '--sitemap' in sys.argv:
        build_sitemap()
    print('완료:', len(videos), '편')


if __name__ == '__main__':
    main()

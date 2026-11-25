#!/usr/bin/env python3
"""Serve the whytea-dielpea library to a local web browser."""
from __future__ import annotations

import json

import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlparse

from library import ROOT, delete_video, load_config, scan_library, set_watched
from web_search import change_block, fetch_thumbnail, get_blocks, get_downloads, search_videos, start_download

HOST = "127.0.0.1"
PORT = 8765

HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>whytea-dielpea</title>
<style>
body{font-family:Arial,sans-serif;max-width:1200px;margin:28px auto;padding:0 18px;background:#111;color:#eee}
h1{font-size:24px;margin-bottom:4px}.sub{color:#999;margin-bottom:22px}
.toolbar{display:flex;gap:8px;margin-bottom:22px;flex-wrap:wrap}
button{background:#292929;color:#eee;border:1px solid #444;padding:7px 11px;cursor:pointer;border-radius:3px}
button:hover{background:#333}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:22px}.card{min-width:0}.card.watched{opacity:.58}
.thumb-wrap{position:relative;width:100%;aspect-ratio:16/9;background:#222;border-radius:5px;overflow:hidden}.thumb{display:block;width:100%;height:100%;object-fit:cover}.placeholder{display:flex;align-items:center;justify-content:center;color:#777}.duration{position:absolute;right:7px;bottom:7px;background:rgba(0,0,0,.85);color:#fff;font-size:13px;font-weight:600;line-height:1;padding:4px 6px;border-radius:3px;text-shadow:0 1px 1px #000}
a{color:inherit;text-decoration:none}.card-info{display:flex;align-items:flex-start;gap:8px;margin-top:8px}.card-text{display:block;flex:1;min-width:0}.title{font-size:16px;font-weight:600;line-height:1.3;margin-top:0}.channel{color:#aaa;font-size:14px;margin-top:5px}.date{color:#888;font-size:13px;margin-top:4px}.badge{font-size:11px;border:1px solid #555;padding:2px 5px;margin-left:6px;color:#aaa}.empty{color:#999;padding:30px 0}
.menu{position:relative;display:block;flex:none;margin:0;height:32px;width:32px;z-index:2}
.menu summary{display:flex;align-items:center;justify-content:center;list-style:none;cursor:pointer;color:#ddd;font-size:22px;line-height:1;width:32px;height:32px;padding:0;border-radius:50%;user-select:none}
.menu summary::-webkit-details-marker{display:none}.menu[open] summary,.menu summary:hover{background:#333}
.menu-pop{position:absolute;right:0;top:29px;min-width:145px;padding:5px;background:#252525;border:1px solid #484848;border-radius:5px;box-shadow:0 5px 18px #0009}
.menu-pop button{display:block;width:100%;text-align:left;border:0;background:transparent;padding:9px 11px;color:#f2aaaa}
.menu-pop button:hover{background:#3a2929}
.player{max-width:1000px;margin:auto}.player video{width:100%;max-height:75vh;background:#000}.back{display:inline-block;margin-bottom:14px;color:#aaa}.watch-title{font-size:21px;margin:12px 0 5px}.watch-meta{color:#999;margin-bottom:15px}.actions{display:flex;gap:8px;margin-bottom:25px}
.search-results{display:flex;flex-direction:column;gap:22px}.search-card{display:flex;align-items:flex-start;gap:16px;min-width:0;width:100%;padding-bottom:18px;border-bottom:1px solid #292929}.search-thumb-wrap{position:relative;width:360px;max-width:42%;aspect-ratio:16/9;flex:none;overflow:hidden;border-radius:5px;background:#222}.search-thumb{position:absolute;inset:0;display:block;width:100%;height:100%;object-fit:cover}.search-info{flex:1;min-width:0}.search-info .title{margin:0 0 8px;font-size:18px}.search-actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:12px}.search-toolbar input[type="text"],.search-toolbar input[type="search"]{background:#202020;color:#eee;border:1px solid #444;padding:9px 10px;border-radius:3px;min-width:150px}.search-toolbar #search-query{flex:1}.proxy-control{display:flex;align-items:center;gap:7px;color:#bbb;font-size:13px;white-space:nowrap}.proxy-control input{accent-color:#aaa}.status{font-size:12px;color:#aaa;margin-top:7px}.status.running{color:#e7c36b}.status.completed{color:#8bd49b}.status.failed{color:#f29b9b}.blocked-row{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px 0;border-bottom:1px solid #333}.blocked-name{min-width:0;overflow-wrap:anywhere}.nav{display:flex;gap:8px;margin:0 0 18px}.nav button.active{background:#454545;border-color:#777}@media(max-width:650px){body{margin-top:18px}.grid{grid-template-columns:1fr}.search-card{gap:10px}.search-thumb-wrap{width:180px;max-width:44%}.search-info .title{font-size:15px}}
</style>
</head>
<body>
<div id="app"></div>
<script>
let videos=[],filter='all',sortBy='downloaded-desc',searchQuery='';
let view='library',searchResults=[],searchTerm='',searchProxy='socks5://127.0.0.1:10808',proxyEnabled=true,searchLoading=false,searchError='',blocked={videos:[],channels:[]},downloadJobs=[];
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function videoUrl(v){return '/video/'+encodeURIComponent(v.path);}
function thumbUrl(v){return v.thumbnail?'/thumb/'+encodeURIComponent(v.thumbnail):null;}
function views(n){if(n===null||n===undefined||n==='')return '';n=Number(n);if(!Number.isFinite(n))return '';return `${n.toLocaleString()} views`;}
function duration(s){if(!s)return '';s=Number(s);if(!Number.isFinite(s))return '';let h=Math.floor(s/3600),m=Math.floor((s%3600)/60),sec=Math.floor(s%60);return h?`${h}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`:`${m}:${String(sec).padStart(2,'0')}`;}
function thumb(v){return `<div class="thumb-wrap">${v.thumbnail?`<img class="thumb" src="${thumbUrl(v)}" loading="eager" decoding="async" alt="">`:'<div class="thumb placeholder">No thumbnail</div>'}${duration(v.duration)?`<span class="duration">${duration(v.duration)}</span>`:''}</div>`;}
function home(){history.pushState({},'', '/');render();}
function openVideo(id){history.pushState({},'', '/watch/'+encodeURIComponent(id));render();}
function render(){
 const app=document.getElementById('app'); const path=location.pathname;
 if(view==='search'){renderSearchView(app);return;}
 if(view==='blocked'){renderBlockedView(app);return;}
 const searchHadFocus=document.activeElement?.id==='search';
 const searchCursor=searchHadFocus?document.activeElement.selectionStart:null;
 if(path.startsWith('/watch/')){let id=decodeURIComponent(path.slice(7)),v=videos.find(x=>x.id===id);if(!v){app.innerHTML='<div class="empty">Video not found.</div>';return;}
   app.innerHTML=`<div class="player"><a class="back" href="/" onclick="event.preventDefault();home()">← Back to library</a><video id="player" controls autoplay preload="metadata" src="${videoUrl(v)}" onended="mark('${esc(v.id)}',true)"></video><div class="watch-title">${esc(v.title)}</div><div class="watch-meta">${esc(v.channel)} · ${esc(views(v.view_count))}${views(v.view_count)?' · ':''}${esc(v.upload_date||'Unknown upload date')}${duration(v.duration)?' · '+duration(v.duration):''}</div><div class="actions"><button onclick="mark('${esc(v.id)}',${!v.watched})">${v.watched?'Mark unwatched':'Mark watched'}</button><button onclick="deleteVideo('${esc(v.id)}')" style="color:#f2aaaa">Delete video</button></div></div>`;
   return;
 }
 const query=searchQuery.trim().toLocaleLowerCase();
 const matchesQuery=v=>!query||[v.title,v.channel,v.path].some(value=>String(value||'').toLocaleLowerCase().includes(query));
 const matchingCount=videos.filter(matchesQuery).length;
 let a=videos.filter(v=>
  (filter==='all'||(filter==='watched'?v.watched:!v.watched)) && matchesQuery(v)
 );
 const sorters={
  'downloaded-desc':(x,y)=>(y.downloaded_at||0)-(x.downloaded_at||0),
  'downloaded-asc':(x,y)=>(x.downloaded_at||0)-(y.downloaded_at||0),
  'upload-desc':(x,y)=>(y.upload_date||'').localeCompare(x.upload_date||''),
  'upload-asc':(x,y)=>(x.upload_date||'').localeCompare(y.upload_date||''),
  'title-asc':(x,y)=>(x.title||'').localeCompare(y.title||'',undefined,{sensitivity:'base'}),
  'title-desc':(x,y)=>(y.title||'').localeCompare(x.title||'',undefined,{sensitivity:'base'})
 };
 a.sort(sorters[sortBy]||sorters['downloaded-desc']);
 app.innerHTML=`<h1>whytea-dielpea</h1><div class="sub">Local YouTube library · ${videos.filter(v=>!v.watched).length} unwatched</div><div class="nav"><button class="active" onclick="view='library';render()">Library</button><button onclick="view='search';render()">Search YouTube</button><button onclick="showBlocked()">Blocked content</button></div><div class="toolbar"><input id="search" type="search" placeholder="Search videos or channels…" aria-label="Search videos or channels" value="${esc(searchQuery)}" oninput="searchQuery=this.value;render()" style="flex:1;min-width:220px;max-width:420px;background:#202020;color:#eee;border:1px solid #444;padding:7px 10px;border-radius:3px"><button onclick="filter='all';render()">All</button><button onclick="filter='unwatched';render()">Unwatched</button><button onclick="filter='watched';render()">Watched</button><label for="sort" style="align-self:center;color:#aaa">Sort by</label><select id="sort" onchange="sortBy=this.value;render()" style="background:#292929;color:#eee;border:1px solid #444;padding:7px 9px;border-radius:3px"><option value="downloaded-desc" ${sortBy==='downloaded-desc'?'selected':''}>Recently downloaded</option><option value="downloaded-asc" ${sortBy==='downloaded-asc'?'selected':''}>Oldest downloaded</option><option value="upload-desc" ${sortBy==='upload-desc'?'selected':''}>Recently uploaded</option><option value="upload-asc" ${sortBy==='upload-asc'?'selected':''}>Oldest uploaded</option><option value="title-asc" ${sortBy==='title-asc'?'selected':''}>Title (A–Z)</option><option value="title-desc" ${sortBy==='title-desc'?'selected':''}>Title (Z–A)</option></select><button onclick="load()">Refresh</button></div><div class="sub" style="margin-top:-12px;margin-bottom:16px">${query?`Search results for “${esc(searchQuery.trim())}”: <strong>${matchingCount.toLocaleString()}</strong> video${matchingCount===1?'':'s'} in archive`:`${matchingCount.toLocaleString()} videos in archive`}${filter!=='all'?` · ${a.length.toLocaleString()} ${filter} result${a.length===1?'':'s'} shown`:''}</div><div class="grid">${a.length?a.map(v=>`<article class="card ${v.watched?'watched':''}"><a href="/watch/${encodeURIComponent(v.id)}" onclick="event.preventDefault();openVideo('${esc(v.id)}')">${thumb(v)}</a><div class="card-info"><a class="card-text" href="/watch/${encodeURIComponent(v.id)}" onclick="event.preventDefault();openVideo('${esc(v.id)}')"><div class="title">${esc(v.title)}${v.watched?'<span class="badge">watched</span>':''}</div><div class="channel">${esc(v.channel)}</div><div class="date">${esc(views(v.view_count))}${views(v.view_count)?' · ':''}${esc(v.upload_date||'Unknown upload date')}</div></a><details class="menu"><summary aria-label="Video options" title="More options">⋮</summary><div class="menu-pop"><button onclick="deleteVideo('${esc(v.id)}')">Delete</button></div></details></div></article>`).join(''):'<div class="empty">No matching videos.</div>'}</div>`;
 if(searchHadFocus){const search=document.getElementById('search');if(search){search.focus();if(searchCursor!==null)search.setSelectionRange(searchCursor,searchCursor);}}
}
function searchMenu(v){return '<details class="menu"><summary aria-label="Video options" title="More options">⋮</summary><div class="menu-pop"><button onclick="startDownload(\''+esc(v.id)+'\')">Download</button><button onclick="blockItem(\'video\',\''+esc(v.id)+'\',decodeURIComponent(\''+encodeURIComponent(v.title||'')+'\'))">Block video</button>'+(v.channel_id?'<button onclick="blockItem(\'channel\',\''+esc(v.channel_id)+'\',decodeURIComponent(\''+encodeURIComponent(v.channel||'')+'\'))">Block channel</button>':'')+'</div></details>'; }
function jobFor(id){return downloadJobs.find(x=>x.video_id===id);}
function searchProxyEnabled(){return proxyEnabled;}
function renderSearchView(app){
 const nav='<div class="nav"><button onclick="view=\'library\';render()">Library</button><button class="active" onclick="view=\'search\';render()">Search YouTube</button><button onclick="showBlocked()">Blocked content</button></div>';
 const cards=searchResults.map(v=>{const job=jobFor(v.id);const thumb='<div class="search-thumb-wrap"><img class="search-thumb" src="/ytthumb/'+encodeURIComponent(v.id)+'?proxy='+encodeURIComponent(searchProxyEnabled()?searchProxy:'')+'" loading="lazy" decoding="async" alt="" onerror="this.style.display=\'none\'"></div>';return '<article class="search-card">'+thumb+'<div class="search-info"><div class="title">'+esc(v.title)+'</div><div class="channel">'+esc(v.channel)+'</div><div class="date">'+(v.duration?esc(duration(v.duration))+' · ':'')+esc(views(v.view_count))+'</div>'+(job?'<div class="status '+esc(job.status)+'">Download: '+esc(job.status)+(job.error?' — '+esc(job.error):'')+'</div>':'')+'<div class="search-actions"><button onclick="startDownload(\''+esc(v.id)+'\')">Download</button><a href="'+esc(v.url)+'" target="_blank" rel="noopener noreferrer"><button>Open YouTube</button></a></div></div>'+searchMenu(v)+'</article>';}).join('');

 app.innerHTML=nav+'<h1>YouTube search</h1><div class="sub">Find videos, download them, or block unwanted videos and channels.</div><div class="toolbar search-toolbar"><input id="search-query" type="search" placeholder="Search YouTube..." value="'+esc(searchTerm)+'" onkeydown="if(event.key===\'Enter\')searchVideos()"><label class="proxy-control"><input id="proxy-enabled" type="checkbox" '+(proxyEnabled?'checked':'')+' onchange="searchProxy=document.getElementById(&quot;search-proxy&quot;).value.trim()||searchProxy;proxyEnabled=this.checked;render()"> Use proxy</label><input id="search-proxy" type="text" placeholder="SOCKS5 proxy" value="'+esc(searchProxy)+'" '+(proxyEnabled?'':'disabled')+' style="max-width:220px"><button onclick="searchVideos()" '+(searchLoading?'disabled':'')+'>'+(searchLoading?'Searching…':'Search')+'</button></div>'+(searchError?'<div class="empty">'+esc(searchError)+'</div>':'')+(searchLoading?'<div class="empty">Searching YouTube…</div>':'')+'<div class="sub">'+(searchResults.length?searchResults.length+' results':'')+'</div><div class="search-results">'+(cards||(!searchLoading?'<div class="empty">Enter a search term to find videos.</div>':''))+'</div>';
}
async function searchVideos(){
 const queryInput=document.getElementById('search-query');searchTerm=queryInput?queryInput.value:searchTerm;
 const proxyInput=document.getElementById('search-proxy');if(proxyInput)searchProxy=proxyInput.value.trim();
 const proxyToggle=document.getElementById('proxy-enabled');if(proxyToggle)proxyEnabled=proxyToggle.checked;
 if(!searchTerm.trim()){searchError='Enter a search query.';render();return;}
 searchLoading=true;searchError='';render();
 try{
  const params=new URLSearchParams({q:searchTerm,limit:'20',proxy:proxyEnabled?searchProxy:''});
  const response=await fetch('/api/search?'+params.toString());const data=await response.json();
  if(!response.ok)throw new Error(data.error||'Search failed.');
  searchResults=data.results||[];
 }catch(error){searchError=error.message;searchResults=[];}
 searchLoading=false;await refreshDownloads();render();
}
async function blockItem(kind,id,name){
 if(!confirm(kind==='video'?'Hide this video from future searches?':'Hide all videos from this channel in future searches?'))return;
 const response=await fetch('/api/block',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind,id,name})});
 const data=await response.json();if(!response.ok){alert(data.error||'Could not block item.');return;}
 blocked=data.blocks||blocked;
 searchResults=searchResults.filter(v=>kind==='video'?v.id!==id:v.channel_id!==id);
 document.querySelectorAll('.menu[open]').forEach(x=>x.removeAttribute('open'));render();
}
async function showBlocked(){view='blocked';try{const r=await fetch('/api/blocks');blocked=await r.json();}catch(e){}render();}
function renderBlockedView(app){
 const nav='<div class="nav"><button onclick="view=\'library\';render()">Library</button><button onclick="view=\'search\';render()">Search YouTube</button><button class="active" onclick="showBlocked()">Blocked content</button></div>';
 const rows=(items,kind)=>items.length?items.map(x=>'<div class="blocked-row"><div class="blocked-name"><strong>'+esc(x.name||x.id)+'</strong><div class="date">'+esc(x.id)+'</div></div><button onclick="unblockItem(\''+kind+'\',\''+esc(x.id)+'\')">Unblock</button></div>').join(''):'<div class="empty">Nothing blocked.</div>';
 app.innerHTML=nav+'<h1>Blocked content</h1><div class="sub">Blocked items are filtered out of future YouTube searches.</div><h2>Videos</h2>'+rows(blocked.videos||[],'video')+'<h2>Channels</h2>'+rows(blocked.channels||[],'channel');
}
async function unblockItem(kind,id){
 const response=await fetch('/api/unblock',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind,id})});
 const data=await response.json();if(!response.ok){alert(data.error||'Could not unblock item.');return;}
 blocked=data.blocks||blocked;render();
}
async function startDownload(id){
 try{
  const response=await fetch('/api/download',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,proxy:searchProxyEnabled()?searchProxy:''})});
  const data=await response.json();if(!response.ok)throw new Error(data.error||'Could not start download.');
  await refreshDownloads();render();
 }catch(error){alert(error.message);}
}
async function refreshDownloads(){try{const r=await fetch('/api/downloads');if(r.ok)downloadJobs=await r.json();}catch(e){}}
async function load(){let r=await fetch('/api/videos');videos=await r.json();render();}
async function mark(id,watched){await fetch('/api/watch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,watched})});await load();if(location.pathname.startsWith('/watch/'))render();}
async function deleteVideo(id){
 const v=videos.find(x=>x.id===id);
 if(!v||!confirm('Permanently delete "'+v.title+'" and all associated files? This cannot be undone.'))return;
 // Remove it from the page immediately; do not wait for the library rescan.
 videos=videos.filter(x=>x.id!==id);
 document.querySelectorAll('.menu[open]').forEach(menu=>menu.removeAttribute('open'));
 if(location.pathname.startsWith('/watch/'))home();else render();
 try{
  const response=await fetch('/api/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});
  const result=await response.json().catch(()=>({}));
  if(!response.ok){alert(result.error||'Could not delete this video.');await load();}
 }catch(error){alert('Could not reach the library server. The video may still be on disk.');await load();}
}
document.addEventListener('click',event=>{
 if(!event.target.closest('.menu'))document.querySelectorAll('.menu[open]').forEach(menu=>menu.removeAttribute('open'));
});
document.addEventListener('keydown',event=>{
 if(event.key==='Escape')document.querySelectorAll('.menu[open]').forEach(menu=>menu.removeAttribute('open'));
});
window.onpopstate=render;load();window.setInterval(async()=>{await refreshDownloads();if(view==='search'&&document.activeElement?.id!=='search-query'&&document.activeElement?.id!=='search-proxy')render();},2500);
</script>
</body></html>'''

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def handle(self):
        # Browsers may close a request before the response is written.
        # Treat that as a normal client disconnect, not a server traceback.
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def log_message(self, fmt, *args): print(fmt % args)
    def send_json(self, data, status=200):
        raw=json.dumps(data).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        parsed=urlparse(self.path)
        if parsed.path=='/favicon.ico':
            self.send_response(204);self.end_headers();return
        if parsed.path in ('/','/watch') or parsed.path.startswith('/watch/'):
            raw=HTML.encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
        if parsed.path=='/api/videos': self.send_json(scan_library_with_thumbnails());return
        if parsed.path=='/api/blocks': self.send_json(get_blocks());return
        if parsed.path=='/api/downloads': self.send_json(get_downloads());return
        if parsed.path.startswith('/ytthumb/'):
            video_id=unquote(parsed.path[len('/ytthumb/'):]);params=parse_qs(parsed.query);proxy=params.get('proxy',[''])[0]
            try:
                image_data,content_type=fetch_thumbnail(video_id,proxy)
                self.send_response(200);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(image_data)));self.send_header('Cache-Control','public, max-age=86400');self.end_headers();self.wfile.write(image_data)
            except Exception as exc:
                print(f"Thumbnail fetch failed for {video_id}: {exc}")
                self.send_error(502, "Thumbnail fetch failed")
            return
        if parsed.path=='/api/search':
            params=parse_qs(parsed.query);query=params.get('q',[''])[0];proxy=params.get('proxy',[''])[0]
            try:self.send_json({'results':search_videos(query,20,proxy)})
            except (ValueError,RuntimeError,TimeoutError) as exc:self.send_json({'error':str(exc)},400)
            return
        if parsed.path.startswith('/video/'): self.serve_file(unquote(parsed.path[7:]),'video');return
        if parsed.path.startswith('/thumb/'): self.serve_file(unquote(parsed.path[7:]),'thumb');return
        self.send_error(404)
    def do_POST(self):
        endpoint=urlparse(self.path).path
        try:
            length=int(self.headers.get('Content-Length','0'))
            data=json.loads(self.rfile.read(length))
            if endpoint in ('/api/block','/api/unblock'):
                kind=str(data.get('kind',''));item_id=str(data.get('id',''));name=str(data.get('name',''))
                blocks=change_block(kind,item_id,name,endpoint=='/api/block')
                self.send_json({'ok':True,'blocks':blocks});return
            if endpoint=='/api/download':
                job=start_download(str(data.get('id','')),data.get('proxy'))
                self.send_json(job,202);return
            if endpoint=='/api/watch':
                ok=set_watched(str(data['id']),bool(data.get('watched',True)))
                self.send_json({'ok':ok},200 if ok else 404)
                return
            if endpoint=='/api/delete':
                result=delete_video(str(data['id']))
                self.send_json(result or {'error':'Video not found or could not be deleted.'},200 if result else 404)
                return
            self.send_error(404)
        except (ValueError,KeyError,json.JSONDecodeError) as exc:
            self.send_json({'error':str(exc)},400)
        except Exception as exc:
            self.send_json({'error':str(exc)},500)
    def serve_file(self,relative,kind):
        cfg=load_config();root=(ROOT/str(cfg['download_dir'])).resolve();target=(root/relative).resolve()
        if not target.is_file() or root not in target.parents:self.send_error(404);return
        size=target.stat().st_size;start,end=0,size-1;range_header=self.headers.get('Range')
        if range_header and range_header.startswith('bytes='):
            try:
                spec=range_header[6:].split(',',1)[0];left,right=spec.split('-',1)
                if left:start=int(left);end=int(right) if right else size-1
                else:start=max(0,size-int(right))
                end=min(end,size-1)
                if start>end or start>=size:raise ValueError
            except ValueError:self.send_error(416);return
            status=HTTPStatus.PARTIAL_CONTENT
        else:status=HTTPStatus.OK
        length=end-start+1;mime=mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
        self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Accept-Ranges','bytes');self.send_header('Content-Length',str(length));self.send_header('Cache-Control','public, max-age=86400' if kind=='thumb' else 'no-cache')
        if status==HTTPStatus.PARTIAL_CONTENT:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.end_headers()
        with target.open('rb') as f:
            f.seek(start);remaining=length
            while remaining:
                chunk=f.read(min(1024*1024,remaining))
                if not chunk:break
                self.wfile.write(chunk);remaining-=len(chunk)

def scan_library_with_thumbnails():
    items=scan_library();cfg=load_config();root=(ROOT/str(cfg['download_dir'])).resolve()
    for item in items:
        video=(root/item['path']).resolve();thumb=None
        for suffix in ('.jpg','.jpeg','.png','.webp'):
            candidate=video.with_suffix(suffix)
            if candidate.is_file():thumb=str(candidate.relative_to(root)).replace('\\','/');break
        item['thumbnail']=thumb
        try:
            # Filesystem modification time is the best available download-time proxy.
            item['downloaded_at']=video.stat().st_mtime
        except OSError:
            item['downloaded_at']=0
    return items

def main():
    server=ThreadingHTTPServer((HOST,PORT),Handler);print(f'whytea-dielpea library: http://{HOST}:{PORT}');print('Press Ctrl+C to stop.')
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()

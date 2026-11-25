#!/usr/bin/env python3
"""Serve the whytea-dielpea library to a local web browser."""
from __future__ import annotations

import json

import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlparse
from pathlib import Path

from library import ROOT, delete_video, load_config, scan_library, set_watched
from web_search import change_block, fetch_thumbnail, get_blocks, get_download_log, get_downloads, search_videos, start_download, cancel_download, get_search_progress, extract_youtube_page, start_batch_download

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
.search-live-log{max-height:220px;overflow:auto;text-align:left;font-family:monospace;font-size:12px;white-space:pre-wrap;word-break:break-word;padding:10px;background:#111;color:#b8d8b8;border-radius:6px;}
.search-results{display:flex;flex-direction:column;gap:22px}.search-card{display:flex;align-items:flex-start;gap:16px;min-width:0;width:100%;padding-bottom:18px;border-bottom:1px solid #292929}.search-thumb-wrap{position:relative;width:360px;max-width:42%;aspect-ratio:16/9;flex:none;overflow:hidden;border-radius:5px;background:#222}.search-thumb{position:absolute;inset:0;display:block;width:100%;height:100%;object-fit:cover}.search-info{flex:1;min-width:0}.search-info .title{margin:0 0 8px;font-size:18px}.search-actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:12px}.search-toolbar input[type="text"],.search-toolbar input[type="search"]{background:#202020;color:#eee;border:1px solid #444;padding:9px 10px;border-radius:3px;min-width:150px}.search-toolbar #search-query{flex:1}.proxy-control{display:flex;align-items:center;gap:7px;color:#bbb;font-size:13px;white-space:nowrap}.proxy-control input{accent-color:#aaa}.status{font-size:12px;color:#aaa;margin-top:7px}.status.running{color:#e7c36b}.status.completed{color:#8bd49b}.status.failed{color:#f29b9b}.progress-track{height:6px;background:#333;border-radius:4px;overflow:hidden;margin-top:8px;max-width:420px}.progress-fill{height:100%;background:#8bd49b;transition:width .2s}.progress-label{font-size:12px;color:#bbb;margin-top:4px;font-variant-numeric:tabular-nums}.blocked-row{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px 0;border-bottom:1px solid #333}.blocked-name{min-width:0;overflow-wrap:anywhere}body{margin-left:88px}.nav{position:fixed;left:12px;top:18px;width:32px;display:flex;flex-direction:column;align-items:center;gap:14px;z-index:5}.nav button{appearance:none;-webkit-appearance:none;width:32px;height:32px;min-width:0;padding:5px;margin:0;border:0!important;border-radius:0!important;background:transparent!important;box-shadow:none!important;color:#858585;display:grid;place-items:center;cursor:pointer;outline-offset:3px}.nav button svg{display:block;width:22px;height:22px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}.nav button:hover,.nav button.active{color:#f0f0f0}.nav button:focus-visible{outline:1px solid #888}.more-results{display:block;margin:24px auto;padding:11px 22px}.log-modal{position:fixed;inset:0;background:#000b;z-index:20;display:flex;align-items:center;justify-content:center;padding:18px}.log-panel{width:min(900px,96vw);max-height:85vh;background:#1b1b1b;border:1px solid #555;border-radius:8px;padding:16px;display:flex;flex-direction:column;gap:10px}.log-content{overflow:auto;white-space:pre-wrap;background:#101010;padding:12px;max-height:65vh;font:12px/1.5 Consolas,monospace}.settings-form{max-width:620px;display:grid;gap:14px}.settings-form label{display:grid;gap:6px;color:#bbb}.settings-form input{background:#202020;color:#eee;border:1px solid #444;padding:9px;border-radius:4px}.settings-form .check{display:flex;align-items:center;gap:9px}@media(max-width:650px){body{margin:76px 12px 18px;padding:0 10px}.nav{left:10px;right:10px;top:8px;bottom:auto;width:auto;flex-direction:row;justify-content:flex-start;gap:16px;background:transparent}.nav button{height:32px;width:32px;margin:0}.grid{grid-template-columns:1fr}.search-card{gap:10px}.search-thumb-wrap{width:180px;max-width:44%}.search-info .title{font-size:15px}}
.channel-header{padding:10px 0 18px}.channel-tabs{display:flex;gap:6px;flex-wrap:wrap;border-bottom:1px solid #333;margin:14px 0 18px}.channel-tabs button{border:0;border-bottom:2px solid transparent;border-radius:0;background:transparent;color:#aaa}.channel-tabs button.active-tab{color:#fff;border-bottom-color:#fff}.about-panel{max-width:900px;line-height:1.6}.about-panel p{white-space:pre-wrap;overflow-wrap:anywhere}.about-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin-top:20px}.about-grid>div{padding:12px;background:#1b1b1b;border:1px solid #333;border-radius:6px;overflow-wrap:anywhere}.about-grid strong{color:#aaa;font-size:13px}.search-card .search-info{overflow-wrap:anywhere}</style>
</head>
<body>
<div id="app"></div>
<script>
let videos=[],filter='all',sortBy='downloaded-desc',searchQuery='';
let view='library',searchResults=[],searchTerm='',searchProxy='socks5://127.0.0.1:10808',proxyEnabled=true,searchLoading=false,searchError='',blocked={videos:[],channels:[]},downloadJobs=[],searchOffset=0,hasMoreResults=false,loadingMore=false,settings={};let logTimer=null,searchProgressKey='',searchProgressLines=[];
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
 if(view==='search'){renderSearchView(app);return;} if(view==='channel'){renderChannelView(app);return;} if(view==='playlist'){renderPlaylistView(app);return;} if(view==='queue'){renderQueueView(app);return;}
 if(view==='blocked'){renderBlockedView(app);return;}if(view==='settings'){renderSettings();return;}
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
 app.innerHTML=`<h1>whytea-dielpea</h1><div class="sub">Local YouTube library · ${videos.filter(v=>!v.watched).length} unwatched</div><div class="nav"><button class="active" title="Library" onclick="view='library';render()"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5.5h5v13H4zM10 4h5v14.5h-5zM16 6h4v12.5h-4zM3 20.5h18"/></svg></button><button title="YouTube search" onclick="view='search';render()"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 4.5 4.5"/></svg></button><button title="Blocked content" onclick="showBlocked()"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m5.6 5.6 12.8 12.8"/></svg></button><button title="Settings" onclick="showSettings()"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3.5"/><path d="M19 13.5a7.5 7.5 0 0 0 0-3l1.4-1.1-1.8-3.1-1.7.6a7.5 7.5 0 0 0-2.6-1.5L14 3.5h-4l-.3 1.9a7.5 7.5 0 0 0-2.6 1.5l-1.7-.6-1.8 3.1L5 10.5a7.5 7.5 0 0 0 0 3l-1.4 1.1 1.8 3.1 1.7-.6a7.5 7.5 0 0 0 2.6 1.5l.3 1.9h4l.3-1.9a7.5 7.5 0 0 0 2.6-1.5l1.7.6 1.8-3.1z"/></svg></button></div><div class="toolbar"><input id="search" type="search" placeholder="Search videos or channels…" aria-label="Search videos or channels" value="${esc(searchQuery)}" oninput="searchQuery=this.value;render()" style="flex:1;min-width:220px;max-width:420px;background:#202020;color:#eee;border:1px solid #444;padding:7px 10px;border-radius:3px"><button onclick="filter='all';render()">All</button><button onclick="filter='unwatched';render()">Unwatched</button><button onclick="filter='watched';render()">Watched</button><label for="sort" style="align-self:center;color:#aaa">Sort by</label><select id="sort" onchange="sortBy=this.value;render()" style="background:#292929;color:#eee;border:1px solid #444;padding:7px 9px;border-radius:3px"><option value="downloaded-desc" ${sortBy==='downloaded-desc'?'selected':''}>Recently downloaded</option><option value="downloaded-asc" ${sortBy==='downloaded-asc'?'selected':''}>Oldest downloaded</option><option value="upload-desc" ${sortBy==='upload-desc'?'selected':''}>Recently uploaded</option><option value="upload-asc" ${sortBy==='upload-asc'?'selected':''}>Oldest uploaded</option><option value="title-asc" ${sortBy==='title-asc'?'selected':''}>Title (A–Z)</option><option value="title-desc" ${sortBy==='title-desc'?'selected':''}>Title (Z–A)</option></select><button onclick="load()">Refresh</button></div><div class="sub" style="margin-top:-12px;margin-bottom:16px">${query?`Search results for “${esc(searchQuery.trim())}”: <strong>${matchingCount.toLocaleString()}</strong> video${matchingCount===1?'':'s'} in archive`:`${matchingCount.toLocaleString()} videos in archive`}${filter!=='all'?` · ${a.length.toLocaleString()} ${filter} result${a.length===1?'':'s'} shown`:''}</div><div class="grid">${a.length?a.map(v=>`<article class="card ${v.watched?'watched':''}"><a href="/watch/${encodeURIComponent(v.id)}" onclick="event.preventDefault();openVideo('${esc(v.id)}')">${thumb(v)}</a><div class="card-info"><a class="card-text" href="/watch/${encodeURIComponent(v.id)}" onclick="event.preventDefault();openVideo('${esc(v.id)}')"><div class="title">${esc(v.title)}${v.watched?'<span class="badge">watched</span>':''}</div><div class="channel">${esc(v.channel)}</div><div class="date">${esc(views(v.view_count))}${views(v.view_count)?' · ':''}${esc(v.upload_date||'Unknown upload date')}</div></a><details class="menu"><summary aria-label="Video options" title="More options">⋮</summary><div class="menu-pop"><button onclick="deleteVideo('${esc(v.id)}')">Delete</button></div></details></div></article>`).join(''):'<div class="empty">No matching videos.</div>'}</div>`;
 if(searchHadFocus){const search=document.getElementById('search');if(search){search.focus();if(searchCursor!==null)search.setSelectionRange(searchCursor,searchCursor);}}
}
function searchMenu(v){const job=jobFor(v.id);return '<details class="menu"><summary aria-label="Video options" title="More options">⋮</summary><div class="menu-pop"><button onclick="startDownload(\''+esc(v.id)+'\')">Download</button>'+(job?'<button onclick="showLog(\''+esc(job.job_id)+'\')">View log</button>':'')+(job&&['queued','running'].includes(job.status)?'<button onclick="cancelDownload(\''+esc(job.job_id)+'\')" style="color:#f2aaaa">Cancel download</button>':'')+'<button onclick="blockItem(\'video\',\''+esc(v.id)+'\',decodeURIComponent(\''+encodeURIComponent(v.title||'')+'\'))">Block video</button>'+(v.channel_id?'<button onclick="blockItem(\'channel\',\''+esc(v.channel_id)+'\',decodeURIComponent(\''+encodeURIComponent(v.channel||'')+'\'))">Block channel</button>':'')+'</div></details>'; }
function jobFor(id){return downloadJobs.find(x=>x.video_id===id);}
function searchProxyEnabled(){return proxyEnabled;}
function renderSearchView(app){
 const nav='<div class="nav"><button title="Library" onclick="view=\'library\';render()"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5.5h5v13H4zM10 4h5v14.5h-5zM16 6h4v12.5h-4zM3 20.5h18"/></svg></button><button class="active" title="YouTube search" onclick="view=\'search\';render()"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 4.5 4.5"/></svg></button><button title="Blocked content" onclick="showBlocked()"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m5.6 5.6 12.8 12.8"/></svg></button><button title="Settings" onclick="showSettings()"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3.5"/><path d="M19 13.5a7.5 7.5 0 0 0 0-3l1.4-1.1-1.8-3.1-1.7.6a7.5 7.5 0 0 0-2.6-1.5L14 3.5h-4l-.3 1.9a7.5 7.5 0 0 0-2.6 1.5l-1.7-.6-1.8 3.1L5 10.5a7.5 7.5 0 0 0 0 3l-1.4 1.1 1.8 3.1 1.7-.6a7.5 7.5 0 0 0 2.6 1.5l.3 1.9h4l.3-1.9a7.5 7.5 0 0 0 2.6-1.5l1.7.6 1.8-3.1z"/></svg></button></div>';
 const cards=searchResults.map(v=>{const job=jobFor(v.id);const thumb='<div class="search-thumb-wrap"><img class="search-thumb" src="/ytthumb/'+encodeURIComponent(v.id)+'?proxy='+encodeURIComponent(searchProxyEnabled()?searchProxy:'')+'&url='+encodeURIComponent(v.thumbnail||'')+'" loading="lazy" decoding="async" alt="" onerror="this.style.display=\'none\'"></div>';return '<article class="search-card">'+thumb+'<div class="search-info"><div class="title">'+esc(v.title)+'</div><div class="channel"><a href="#" onclick="event.preventDefault();openChannel(\'https://www.youtube.com/channel/'+esc(v.channel_id)+'\',\''+esc(v.channel)+'\')">'+esc(v.channel)+'</a></div><div class="date">'+(v.duration?esc(duration(v.duration))+' · ':'')+esc(views(v.view_count))+'</div>'+(job?'<div class="status '+esc(job.status)+'">Download: '+esc(job.status)+(job.error?' — '+esc(job.error):'')+'</div>'+(job.status==='running'||job.status==='queued'?'<button onclick="cancelDownload(\''+esc(job.job_id)+'\')" style="margin-top:7px;color:#f2aaaa">Cancel download</button>':'')+(job.status==='running'?'<div class="progress-track"><div class="progress-fill" style="width:'+Math.max(0,Math.min(100,Number(job.progress)||0))+'%"></div></div><div class="progress-label">'+(Number(job.progress)||0).toFixed(1)+'%</div>':''):'')+'<div class="search-actions"><button onclick="startDownload(\''+esc(v.id)+'\')">Download</button><a href="'+esc(v.url)+'" target="_blank" rel="noopener noreferrer"><button>Open YouTube</button></a></div></div>'+searchMenu(v)+'</article>';}).join('');

 app.innerHTML=nav+'<h1>YouTube search</h1><div class="sub">Find videos, download them, or block unwanted videos and channels.</div><div class="toolbar search-toolbar"><input id="search-query" type="search" placeholder="Search YouTube..." value="'+esc(searchTerm)+'" onkeydown="if(event.key===\'Enter\')searchVideos()"><label class="proxy-control"><input id="proxy-enabled" type="checkbox" '+(proxyEnabled?'checked':'')+' onchange="searchProxy=document.getElementById(&quot;search-proxy&quot;).value.trim()||searchProxy;proxyEnabled=this.checked;render()"> Use proxy</label><input id="search-proxy" type="text" placeholder="SOCKS5 proxy" value="'+esc(searchProxy)+'" '+(proxyEnabled?'':'disabled')+' style="max-width:220px"><button onclick="searchVideos()" '+(searchLoading?'disabled':'')+'>'+(searchLoading?'Searching…':'Search')+'</button></div>'+(searchError?'<div class="empty">'+esc(searchError)+'</div>':'')+(searchLoading?'<div class="empty search-live-log" id="search-live-log">'+(searchProgressLines.length?searchProgressLines.map(x=>'<div>'+esc(x)+'</div>').join(''):'Starting search…')+'</div>':'')+'<div class="sub">'+(searchResults.length?searchResults.length+' results':'')+'</div><div class="search-results">'+(cards||(!searchLoading?'<div class="empty">Enter a search term to find videos.</div>':''))+'</div>';
 if(hasMoreResults){const more=document.createElement('button');more.className='more-results';more.textContent=loadingMore?'Loading…':'Load 5 more';more.disabled=loadingMore;more.onclick=loadMoreResults;app.appendChild(more);}
}

let channelUrl='',channelName='',channelTab='videos',channelData=null,channelLoading=false,channelError='',channelSearch='';
let queueExpanded=true;
function openChannel(url,name){channelUrl=String(url||'');channelName=String(name||'Channel');channelTab='videos';channelData=null;channelSearch='';channelError='';view='channel';render();loadChannel('videos');}
function channelTabUrl(tab){let base=channelUrl.replace(/\/(videos|shorts|streams|playlists|about)\/?$/,'').replace(/\/$/,'');return base+'/'+tab;}
async function loadChannel(tab=channelTab){
 channelTab=tab;channelLoading=true;channelError='';render();
 try{const params=new URLSearchParams({url:channelUrl,tab,limit:'100',proxy:proxyEnabled?searchProxy:''});const r=await fetch('/api/channel?'+params);const d=await r.json();if(!r.ok)throw new Error(d.error||'Unable to load channel.');channelData=d;channelName=d.channel?.name||channelName;}
 catch(e){channelError=e.message;channelData=null;}
 channelLoading=false;render();
}
function renderChannelView(app){const channelSearchFocus=document.activeElement?.placeholder==='Search this channel tab…';const channelSearchCursor=channelSearchFocus?document.activeElement.selectionStart:null;
 const nav='<div class="nav"><button title="Library" onclick="view=\'library\';render()"><svg viewBox="0 0 24 24"><path d="M4 5.5h5v13H4zM10 4h5v14.5h-5zM16 6h4v12.5h-4zM3 20.5h18"/></svg></button><button title="Search" onclick="view=\'search\';render()"><svg viewBox="0 0 24 24"><circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 4.5 4.5"/></svg></button><button title="Download queue" onclick="view=\'queue\';refreshDownloads().then(render)"><svg viewBox="0 0 24 24"><path d="M4 5h16M4 10h16M4 15h11M4 20h8"/><path d="m17 16 4 3-4 3"/></svg></button><button title="Blocked content" onclick="showBlocked()"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="m5.6 5.6 12.8 12.8"/></svg></button><button title="Settings" onclick="showSettings()"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3.5"/></svg></button></div>';
 const tabs=['videos','shorts','streams','playlists','about'];
 const ch=channelData?.channel||{};
 const tabButtons=tabs.map(t=>'<button class="'+(channelTab===t?'active-tab':'')+'" onclick="loadChannel(\''+t+'\')">'+({videos:'Videos',shorts:'Shorts',streams:'Live',playlists:'Playlists',about:'About'}[t])+'</button>').join('');
 const entries=channelData?.entries||[];
 const filter=channelSearch.trim().toLowerCase();
 const list=entries.filter(v=>!filter||String(v.title||'').toLowerCase().includes(filter));
 const card=list.map(v=>{
   const thumb=v.thumbnail?'<img class="search-thumb" loading="lazy" src="/ytthumb/'+encodeURIComponent(v.id)+'?proxy='+encodeURIComponent(proxyEnabled?searchProxy:'')+'&url='+encodeURIComponent(v.thumbnail)+'" onerror="this.style.display=\'none\'">':'';
   const isPlaylist=channelTab==='playlists';
   const target=isPlaylist?(v.url||'https://www.youtube.com/playlist?list='+v.id):(v.url||'https://www.youtube.com/watch?v='+v.id);
   return '<article class="search-card"><div class="search-thumb-wrap">'+thumb+'</div><div class="search-info"><div class="title">'+esc(v.title||'Untitled')+'</div><div class="date">'+(v.duration?esc(duration(v.duration))+' · ':'')+esc(views(v.view_count))+(v.playlist_count?' · '+v.playlist_count+' videos':'')+'</div><div class="search-actions">'+(isPlaylist?'<button onclick="openPlaylist(\''+encodeURIComponent(target)+'\',\''+encodeURIComponent(v.title||'Playlist')+'\')">Open playlist</button><button onclick="addBatch(\''+encodeURIComponent(target)+'\',\'playlist\')">Download playlist</button>':'<button onclick="startDownload(\''+esc(v.id)+'\')">Queue video</button>')+'</div></div></article>';
 if(channelSearchFocus){const input=app.querySelector('input[placeholder="Search this channel tab…"]');if(input){input.focus();if(channelSearchCursor!==null)input.setSelectionRange(channelSearchCursor,channelSearchCursor);}}}).join('');
 app.innerHTML=nav+'<button class="back" onclick="view=\'search\';render()">← Back to search</button><div class="channel-header"><h1>'+esc(ch.name||channelName)+'</h1><div class="sub">'+esc(ch.channel_url||ch.uploader_url||ch.url||channelUrl)+'</div><div class="sub">'+(ch.subscriber_count?Number(ch.subscriber_count).toLocaleString()+' subscribers · ':'')+(ch.video_count?Number(ch.video_count).toLocaleString()+' videos':'')+(ch.country?' · '+esc(ch.country):'')+'</div><div class="search-actions"><button onclick="addBatch(encodeURIComponent(channelTabUrl(\'videos\')),\'channel\')">Download channel videos</button><button onclick="addBatch(encodeURIComponent(channelTabUrl(\'shorts\')),\'channel\')">Download Shorts</button><button onclick="addBatch(encodeURIComponent(channelTabUrl(\'streams\')),\'channel\')">Download streams</button></div></div><div class="channel-tabs">'+tabButtons+'</div>'+(channelTab!=='about'?'<div class="toolbar"><input type="search" placeholder="Search this channel tab…" value="'+esc(channelSearch)+'" oninput="channelSearch=this.value;render()" style="background:#202020;color:#eee;border:1px solid #444;padding:9px;border-radius:3px;flex:1"><button onclick="loadChannel(channelTab)">Refresh</button></div>':'')+(channelLoading?'<div class="empty">Loading channel…</div>':'')+(channelError?'<div class="empty">'+esc(channelError)+'</div>':'')+(channelTab==='about'&&ch?'<section class="about-panel"><h2>About</h2><p>'+esc(ch.description||'No channel description was returned.')+'</p><div class="about-grid">'+[['Channel ID',ch.id],['Country',ch.country],['Subscribers',ch.subscriber_count],['Channel views',ch.view_count],['Video count',ch.video_count],['Channel URL',ch.channel_url||ch.uploader_url||ch.url]].filter(x=>x[1]).map(x=>'<div><strong>'+esc(x[0])+'</strong><div>'+esc(x[1])+'</div></div>').join('')+'</div></section>':'')+(channelTab!=='about'&&!channelLoading?'<div class="sub">'+list.length+' loaded item(s)'+(channelData?.has_more?' · More items may exist':'')+'</div><div class="search-results">'+(card||'<div class="empty">No matches in loaded items.</div>')+'</div>':'');
}
function openPlaylist(encodedUrl,encodedTitle){playlistUrl=decodeURIComponent(encodedUrl);playlistName=decodeURIComponent(encodedTitle||'Playlist');playlistData=null;playlistLoading=false;playlistError='';view='playlist';loadPlaylist();render();}
let playlistUrl='',playlistName='',playlistData=null,playlistLoading=false,playlistError='',playlistSearch='';
async function loadPlaylist(){playlistLoading=true;render();try{const p=new URLSearchParams({url:playlistUrl,tab:'playlist',limit:'100',proxy:proxyEnabled?searchProxy:''});const r=await fetch('/api/channel?'+p);const d=await r.json();if(!r.ok)throw new Error(d.error||'Playlist loading failed.');playlistData=d;}catch(e){playlistError=e.message;}playlistLoading=false;render();}
function renderPlaylistView(app){const playlistSearchFocus=document.activeElement?.placeholder==='Search playlist…';const playlistSearchCursor=playlistSearchFocus?document.activeElement.selectionStart:null;
 const nav='<div class="nav"><button title="Library" onclick="view=\'library\';render()">Library</button><button title="Search" onclick="view=\'search\';render()">Search</button><button title="Queue" onclick="view=\'queue\';refreshDownloads().then(render)">Queue</button><button title="Blocked" onclick="showBlocked()">Blocked</button><button title="Settings" onclick="showSettings()">Settings</button></div>';
 const entries=playlistData?.entries||[],q=playlistSearch.trim().toLowerCase(),items=entries.filter(v=>!q||String(v.title||'').toLowerCase().includes(q));
 const cards=items.map(v=>'<article class="search-card"><div class="search-info"><div class="title">'+esc(v.title||'Untitled')+'</div><div class="date">'+(v.duration?esc(duration(v.duration))+' · ':'')+esc(views(v.view_count))+'</div><button onclick="startDownload(\''+esc(v.id)+'\')">Queue video</button></div></article>').join('');
 app.innerHTML=nav+'<button onclick="view=\'channel\';render()">← Back to channel</button><h1>'+esc(playlistName)+'</h1><div class="search-actions"><button onclick="addBatch(encodeURIComponent(playlistUrl),\'playlist\')">Download entire playlist</button></div><div class="toolbar"><input type="search" placeholder="Search playlist…" value="'+esc(playlistSearch)+'" oninput="playlistSearch=this.value;render()" style="flex:1;background:#202020;color:#eee;border:1px solid #444;padding:9px;border-radius:3px"></div>'+(playlistLoading?'<div class="empty">Loading playlist…</div>':'')+(playlistError?'<div class="empty">'+esc(playlistError)+'</div>':'')+'<div class="sub">'+items.length+' loaded video(s)</div><div class="search-results">'+(cards||'<div class="empty">No matching playlist videos.</div>')+'</div>'if(playlistSearchFocus){const input=app.querySelector('input[placeholder="Search playlist…"]');if(input){input.focus();if(playlistSearchCursor!==null)input.setSelectionRange(playlistSearchCursor,playlistSearchCursor);}};
}
async function addBatch(encodedUrl,type){const url=decodeURIComponent(encodedUrl);if(type==='channel'&&!confirm('Add the channel tab to the download queue? This may include many videos.'))return;if(type==='playlist'&&!confirm('Add the entire playlist to the download queue?'))return;try{const r=await fetch('/api/batch-download',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url,source_type:type,proxy:proxyEnabled?searchProxy:''})});const d=await r.json();if(!r.ok)throw new Error(d.error||'Could not queue batch.');downloadJobs.push(d);alert('Added to download queue.');}catch(e){alert(e.message);}}
function renderQueueView(app){
 const nav='<div class="nav"><button title="Library" onclick="view=\'library\';render()">Library</button><button title="Search" onclick="view=\'search\';render()">Search</button><button class="active" title="Queue">Queue</button><button title="Blocked" onclick="showBlocked()">Blocked</button><button title="Settings" onclick="showSettings()">Settings</button></div>';
 const sorted=[...downloadJobs].sort((a,b)=>a.created_at-b.created_at);
 app.innerHTML=nav+'<h1>Download queue</h1><div class="sub">'+sorted.filter(x=>x.status==='queued').length+' queued · '+sorted.filter(x=>x.status==='running').length+' active · '+sorted.filter(x=>x.status==='completed').length+' completed · '+sorted.filter(x=>x.status==='failed').length+' failed</div><div class="search-results">'+(sorted.map(j=>'<article class="search-card"><div class="search-info"><div class="title">'+esc(j.label||j.video_id||j.source_url||'Download')+'</div><div class="status '+esc(j.status)+'">'+esc(j.status)+(j.error?' · '+esc(j.error):'')+'</div>'+(j.status==='running'?'<div class="progress-track"><div class="progress-fill" style="width:'+Math.max(0,Math.min(100,j.progress||0))+'%"></div></div><div class="progress-label">'+(j.progress||0).toFixed(1)+'%</div>':'')+'<div class="search-actions"><button onclick="showLog(\''+esc(j.job_id)+'\')">View log</button>'+(j.status==='queued'||j.status==='running'?'<button onclick="cancelDownload(\''+esc(j.job_id)+'\')">Cancel</button>':'')+'</div></div></article>').join('')||'<div class="empty">Queue is empty.</div>')+'</div><button onclick="refreshDownloads().then(render)">Refresh queue</button>';
}

async function pollSearchProgress(key){try{const r=await fetch('/api/search-progress?key='+encodeURIComponent(key));if(r.ok){const d=await r.json();searchProgressLines=d.lines||[];const box=document.getElementById('search-live-log');if(box){box.innerHTML=searchProgressLines.map(x=>'<div>'+esc(x)+'</div>').join('');box.scrollTop=box.scrollHeight;}}}catch(e){}}
async function searchVideos(){
 const queryInput=document.getElementById('search-query');searchTerm=queryInput?queryInput.value:searchTerm;
 const proxyInput=document.getElementById('search-proxy');if(proxyInput)searchProxy=proxyInput.value.trim();
 const proxyToggle=document.getElementById('proxy-enabled');if(proxyToggle)proxyEnabled=proxyToggle.checked;
 if(!searchTerm.trim()){searchError='Enter a search query.';render();return;}
 searchLoading=true;searchError='';searchResults=[];searchOffset=0;hasMoreResults=false;searchProgressLines=[];searchProgressKey=Math.random().toString(36).slice(2,14);render();const progressKey=searchProgressKey;const progressTimer=setInterval(()=>pollSearchProgress(progressKey),700);
 try{
  const params=new URLSearchParams({q:searchTerm,limit:'10',offset:'0',proxy:proxyEnabled?searchProxy:'',progress:progressKey});
  const response=await fetch('/api/search?'+params.toString());const data=await response.json();
  if(!response.ok)throw new Error(data.error||'Search failed.');
  searchResults=data.results||[];searchOffset=searchResults.length;hasMoreResults=!!data.has_more;
 }catch(error){searchError=error.message;searchResults=[];}
 clearInterval(progressTimer);await pollSearchProgress(progressKey);searchLoading=false;await refreshDownloads();render();
}
async function loadMoreResults(){if(loadingMore||!hasMoreResults)return;loadingMore=true;render();try{const params=new URLSearchParams({q:searchTerm,limit:'5',offset:String(searchOffset),proxy:proxyEnabled?searchProxy:''});const r=await fetch('/api/search?'+params);const data=await r.json();if(!r.ok)throw new Error(data.error||'Could not load more results.');const seen=new Set(searchResults.map(v=>v.id));const next=(data.results||[]).filter(v=>!seen.has(v.id));searchResults.push(...next);searchOffset+=next.length;hasMoreResults=!!data.has_more&&next.length>0;}catch(e){searchError=e.message;}loadingMore=false;render();}
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
 const nav='<div class="nav"><button title="Library" onclick="view=\'library\';render()"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5.5h5v13H4zM10 4h5v14.5h-5zM16 6h4v12.5h-4zM3 20.5h18"/></svg></button><button title="YouTube search" onclick="view=\'search\';render()"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 4.5 4.5"/></svg></button><button class="active" title="Blocked content" onclick="showBlocked()"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m5.6 5.6 12.8 12.8"/></svg></button><button title="Settings" onclick="showSettings()"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3.5"/><path d="M19 13.5a7.5 7.5 0 0 0 0-3l1.4-1.1-1.8-3.1-1.7.6a7.5 7.5 0 0 0-2.6-1.5L14 3.5h-4l-.3 1.9a7.5 7.5 0 0 0-2.6 1.5l-1.7-.6-1.8 3.1L5 10.5a7.5 7.5 0 0 0 0 3l-1.4 1.1 1.8 3.1 1.7-.6a7.5 7.5 0 0 0 2.6 1.5l.3 1.9h4l.3-1.9a7.5 7.5 0 0 0 2.6-1.5l1.7.6 1.8-3.1z"/></svg></button></div>';
 const rows=(items,kind)=>items.length?items.map(x=>'<div class="blocked-row"><div class="blocked-name"><strong>'+esc(x.name||x.id)+'</strong><div class="date">'+esc(x.id)+'</div></div><button onclick="unblockItem(\''+kind+'\',\''+esc(x.id)+'\')">Unblock</button></div>').join(''):'<div class="empty">Nothing blocked.</div>';
 app.innerHTML=nav+'<h1>Blocked content</h1><div class="sub">Blocked items are filtered out of future YouTube searches.</div><h2>Videos</h2>'+rows(blocked.videos||[],'video')+'<h2>Channels</h2>'+rows(blocked.channels||[],'channel');
}
async function unblockItem(kind,id){
 const response=await fetch('/api/unblock',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind,id})});
 const data=await response.json();if(!response.ok){alert(data.error||'Could not unblock item.');return;}
 blocked=data.blocks||blocked;render();
}
async function showLog(jobId){const modal=document.createElement('div');modal.className='log-modal';modal.innerHTML='<div class="log-panel"><div style="display:flex;justify-content:space-between;align-items:center"><strong>Download log</strong><button onclick="closeLog()">✕</button></div><div id="log-status" class="sub"></div><pre id="log-content" class="log-content">Loading log…</pre></div>';document.body.appendChild(modal);window.currentLogJob=jobId;await refreshLog();if(logTimer)clearInterval(logTimer);logTimer=setInterval(refreshLog,1000);}
async function refreshLog(){if(!window.currentLogJob)return;try{const r=await fetch('/api/download-log/'+encodeURIComponent(window.currentLogJob));const d=await r.json();const el=document.getElementById('log-content');if(el){el.textContent=d.log||'(No log output yet.)';el.scrollTop=el.scrollHeight;document.getElementById('log-status').textContent='Status: '+d.status;if(d.status==='completed'||d.status==='failed'){clearInterval(logTimer);logTimer=null;}}}catch(e){}}
function closeLog(){window.currentLogJob=null;if(logTimer)clearInterval(logTimer);logTimer=null;document.querySelector('.log-modal')?.remove();}
async function showSettings(){view='settings';try{const r=await fetch('/api/settings');settings=await r.json();}catch(e){}renderSettings();}
function renderSettings(){const app=document.getElementById('app');const nav='<div class="nav"><button title="Library" onclick="view=\'library\';render()"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5.5h5v13H4zM10 4h5v14.5h-5zM16 6h4v12.5h-4zM3 20.5h18"/></svg></button><button class="active" title="YouTube search" onclick="view=\'search\';render()"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 4.5 4.5"/></svg></button><button title="Blocked content" onclick="showBlocked()"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m5.6 5.6 12.8 12.8"/></svg></button><button title="Settings" onclick="showSettings()"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3.5"/><path d="M19 13.5a7.5 7.5 0 0 0 0-3l1.4-1.1-1.8-3.1-1.7.6a7.5 7.5 0 0 0-2.6-1.5L14 3.5h-4l-.3 1.9a7.5 7.5 0 0 0-2.6 1.5l-1.7-.6-1.8 3.1L5 10.5a7.5 7.5 0 0 0 0 3l-1.4 1.1 1.8 3.1 1.7-.6a7.5 7.5 0 0 0 2.6 1.5l.3 1.9h4l.3-1.9a7.5 7.5 0 0 0 2.6-1.5l1.7.6 1.8-3.1z"/></svg></button></div>';app.innerHTML=nav+'<h1>Settings</h1><div class="sub">Defaults for new searches and downloads.</div><form class="settings-form" onsubmit="saveSettings(event)"><label class="check"><input id="setting-proxy-enabled" type="checkbox" '+(settings.use_proxy!==false?'checked':'')+'> Use proxy by default</label><label>Default proxy<input id="setting-proxy" value="'+esc(settings.proxy||'socks5://127.0.0.1:10808')+'"></label><label>Browser cookies<input id="setting-cookies" value="'+esc(settings.cookies_from_browser||'firefox')+'"></label><label>Default video format selector<input id="setting-format" value="'+esc(settings.format_selector||'398+bestaudio/398')+'"><span class="date">Default: AV1 720p with best audio fallback</span></label><label class="check"><input id="setting-no-shorts" type="checkbox" '+(settings.no_shorts!==false?'checked':'')+'> Exclude live streams</label><button type="submit">Save settings</button><div id="settings-status" class="status"></div></form>';}
async function saveSettings(event){event.preventDefault();const data={use_proxy:document.getElementById('setting-proxy-enabled').checked,proxy:document.getElementById('setting-proxy').value.trim(),cookies_from_browser:document.getElementById('setting-cookies').value.trim(),format_selector:document.getElementById('setting-format').value.trim(),no_shorts:document.getElementById('setting-no-shorts').checked};const r=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const d=await r.json();const el=document.getElementById('settings-status');if(!r.ok){el.textContent=d.error||'Could not save settings.';return;}settings=d;searchProxy=settings.proxy||'';proxyEnabled=settings.use_proxy!==false;el.textContent='Settings saved.';}
async function startDownload(id){
 try{
  const response=await fetch('/api/download',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,proxy:searchProxyEnabled()?searchProxy:''})});
  const data=await response.json();if(!response.ok)throw new Error(data.error||'Could not start download.');
  await refreshDownloads();render();
 }catch(error){alert(error.message);}
}
async function cancelDownload(jobId){
 if(!confirm('Cancel this download?'))return;
 try{
  const response=await fetch('/api/cancel-download',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:jobId})});
  const data=await response.json();if(!response.ok)throw new Error(data.error||'Could not cancel download.');
  await refreshDownloads();render();
 }catch(error){alert(error.message);}
}
async function refreshDownloads(){try{const r=await fetch('/api/downloads');if(r.ok)downloadJobs=await r.json();}catch(e){}return downloadJobs.some(job=>job.status==='queued'||job.status==='running');}
async function loadSettingsDefaults(){try{const r=await fetch('/api/settings');settings=await r.json();searchProxy=settings.proxy||searchProxy;proxyEnabled=settings.use_proxy!==false;}catch(e){}}
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
window.onpopstate=render;loadSettingsDefaults();load();window.setInterval(async()=>{if(!['search','queue'].includes(view)||!downloadJobs.some(job=>job.status==='queued'||job.status==='running'))return;await refreshDownloads();if(document.activeElement?.id!=='search-query'&&document.activeElement?.id!=='search-proxy')render();},4000);
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
        if parsed.path=='/api/settings': self.send_json(public_settings());return
        if parsed.path.startswith('/api/download-log/'): self.send_json(get_download_log(unquote(parsed.path.rsplit('/',1)[-1])));return
        if parsed.path.startswith('/ytthumb/'):
            video_id=unquote(parsed.path[len('/ytthumb/'):]);params=parse_qs(parsed.query);proxy=params.get('proxy',[''])[0];thumbnail_url=params.get('url',[''])[0]
            try:
                image_data,content_type=fetch_thumbnail(video_id,proxy,thumbnail_url)
                self.send_response(200);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(image_data)));self.send_header('Cache-Control','public, max-age=86400');self.end_headers();self.wfile.write(image_data)
            except Exception as exc:
                print(f"Thumbnail fetch failed for {video_id}: {exc}")
                self.send_error(502, "Thumbnail fetch failed")
            return
        if parsed.path=='/api/search-progress':
            params=parse_qs(parsed.query);key=params.get('key',[''])[0];self.send_json(get_search_progress(key));return

        if parsed.path=='/api/channel':
            params=parse_qs(parsed.query);url=params.get('url',[''])[0];tab=params.get('tab',['videos'])[0];limit=params.get('limit',['30'])[0];proxy=params.get('proxy',[''])[0]
            try:self.send_json(extract_youtube_page(url,tab,int(limit),proxy))
            except (ValueError,RuntimeError,TimeoutError) as exc:self.send_json({'error':str(exc)},400)
            return
        if parsed.path=='/api/search':
            params=parse_qs(parsed.query);query=params.get('q',[''])[0];proxy=params.get('proxy',[''])[0]
            try:
                limit=max(1,min(int(params.get('limit',['10'])[0]),50));offset=max(0,int(params.get('offset',['0'])[0]));key=params.get('progress',[''])[0];results=search_videos(query,limit,proxy,offset,key);self.send_json({'results':results,'has_more':len(results)==limit})
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
            if endpoint=='/api/settings':
                current=read_config_file();current.update({k:data[k] for k in ('proxy','use_proxy','cookies_from_browser','no_shorts','format_selector') if k in data})
                if current.get('proxy') and not str(current['proxy']).startswith(('socks5://','socks5h://','http://','https://')): raise ValueError('Proxy must include a valid scheme, e.g. socks5://127.0.0.1:10808')
                write_config_file(current);self.send_json(public_settings());return

            if endpoint=='/api/batch-download':
                job=start_batch_download(str(data.get('url','')),str(data.get('source_type','playlist')),data.get('proxy'))
                self.send_json(job,202);return
            if endpoint=='/api/download':
                job=start_download(str(data.get('id','')),data.get('proxy'))
                self.send_json(job,202);return
            if endpoint=='/api/cancel-download':
                job=cancel_download(str(data.get('job_id','')))
                self.send_json(job);return
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

def read_config_file():
    path=ROOT/'config.json'
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data,dict) else {}
    except (OSError,json.JSONDecodeError): return {}

def write_config_file(data):
    path=ROOT/'config.json';tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=4)+'\n',encoding='utf-8');tmp.replace(path)

def public_settings():
    cfg=load_config();return {'proxy':cfg.get('proxy','socks5://127.0.0.1:10808'),'use_proxy':cfg.get('use_proxy',True),'cookies_from_browser':cfg.get('cookies_from_browser','firefox'),'no_shorts':cfg.get('no_shorts',True),'format_selector':cfg.get('format_selector','398+bestaudio/398')}

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

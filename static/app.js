const categories=["전체","디지털","생활","도서","의류","기타"];let current="전체",claimId=null;
const $=id=>document.getElementById(id);const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const pad=n=>String(n).padStart(2,"0");
function localInputValue(date){return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`}
function dateLabel(date){return new Intl.DateTimeFormat("ko-KR",{month:"long",day:"numeric",hour:"2-digit",minute:"2-digit",second:"2-digit"}).format(date)}
function countdown(ms){
  const total=Math.max(0,Math.ceil(ms/1000)),days=Math.floor(total/86400),hours=Math.floor(total%86400/3600),minutes=Math.floor(total%3600/60),seconds=total%60;
  return `${days?days+"일 ":""}${pad(hours)}:${pad(minutes)}:${pad(seconds)} 후 시작`;
}
function toast(message,error=false){$("toast").textContent=message;$("toast").className="toast show"+(error?" error":"");setTimeout(()=>$("toast").className="toast",2800)}
async function load(){
  const q=encodeURIComponent($("search").value.trim()),cat=encodeURIComponent(current);
  const res=await fetch(`/api/items?q=${q}&category=${cat}`),items=await res.json();
  $("filters").innerHTML=categories.map(c=>`<button class="filter ${c===current?"on":""}" data-category="${c}">${c}</button>`).join("");
  $("filters").querySelectorAll("button").forEach(b=>b.onclick=()=>{current=b.dataset.category;load()});
  $("grid").innerHTML=items.length?items.map(card).join(""):'<div class="empty">조건에 맞는 나눔이 아직 없어요.</div>';
  document.querySelectorAll(".claim").forEach(b=>b.onclick=()=>openClaim(Number(b.dataset.id),b.dataset.title));
  updateCountdowns();
}
function card(i){
  const emo={디지털:"⌨️",생활:"🪴",도서:"📚",의류:"👕",기타:"🎁"}[i.category]||"🎁";
  const start=i.claim_start_at?new Date(i.claim_start_at):null,waiting=i.status==="open"&&start&&start>Date.now();
  const state=i.status!=="open"?"나눔 완료":waiting?"신청 대기":"나눔 중";
  const buttonText=i.status!=="open"?esc(i.claimant||"이웃")+" 신청":waiting?countdown(start-Date.now()):"나눔받기";
  return `<article class="card"><div class="visual ${esc(i.category)}">${i.image_url?`<img src="${esc(i.image_url)}" alt="">`:`<span>${emo}</span>`}<b class="status ${i.status!=="open"?"done":waiting?"waiting":""}">${state}</b></div><div class="cardBody"><div class="meta"><strong>${esc(i.category)}</strong><span>📍 ${esc(i.location)}</span></div><h3>${esc(i.title)}</h3><p>${esc(i.description)}</p>${start?`<div class="schedule">⏰ ${dateLabel(start)} 신청 시작</div>`:""}<div class="foot"><span><b>${esc(i.giver)}</b>님의 나눔</span><button class="claim ${waiting?"waiting":""}" data-id="${i.id}" data-title="${esc(i.title)}" data-start="${start?start.toISOString():""}" data-open="${i.status==="open"}" ${i.status==="open"&&!waiting?"":"disabled"}>${buttonText}</button></div></div></article>`;
}
function updateCountdowns(){
  document.querySelectorAll('.claim[data-open="true"][data-start]').forEach(button=>{
    if(!button.dataset.start)return;
    const left=new Date(button.dataset.start)-Date.now(),status=button.closest(".card").querySelector(".status");
    if(left<=0){button.disabled=false;button.textContent="나눔받기";button.classList.remove("waiting");status.textContent="나눔 중";status.classList.remove("waiting")}
    else{button.disabled=true;button.textContent=countdown(left)}
  });
}
function modal(id,show){$(id).classList.toggle("show",show)}
$("open").onclick=()=>{const start=new Date(Date.now()+60000),input=$("claimStartAt");input.min=localInputValue(new Date());if(!input.value)input.value=localInputValue(start);modal("modal",true)};$("close").onclick=()=>modal("modal",false);$("claimClose").onclick=()=>modal("claimModal",false);
["modal","claimModal"].forEach(id=>$(id).onclick=e=>{if(e.target===$(id))modal(id,false)});
$("search").oninput=()=>load();
function openClaim(id,title){claimId=id;$("claimTitle").textContent=title;modal("claimModal",true)}
$("form").onsubmit=async e=>{
  e.preventDefault();const body=Object.fromEntries(new FormData(e.target));
  body.claimStartAt=new Date(body.claimStartAt).toISOString();
  const res=await fetch("/api/items",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(body)}),data=await res.json();
  if(!res.ok)return toast(data.error||"등록 실패",true);
  e.target.reset();modal("modal",false);toast("나눔 물건이 등록되었어요!");load();
};
$("claimForm").onsubmit=async e=>{
  e.preventDefault();const body=Object.fromEntries(new FormData(e.target));
  const res=await fetch(`/api/items/${claimId}/claim`,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(body)}),data=await res.json();
  if(!res.ok){modal("claimModal",false);toast(data.error||"신청 실패",true);return load()}
  e.target.reset();modal("claimModal",false);toast("선착순 신청이 확정되었어요!");load();
};
load();

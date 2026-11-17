const categories=["전체","디지털","생활","도서","의류","기타"];let current="전체",currentUser=null,claimStartConfirmed=false;
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
  document.querySelectorAll(".deleteItem").forEach(b=>b.onclick=()=>deleteItem(Number(b.dataset.id),b.dataset.title));
  updateCountdowns();
}
function card(i){
  const emo={디지털:"⌨️",생활:"🪴",도서:"📚",의류:"👕",기타:"🎁"}[i.category]||"🎁";
  const start=i.claim_start_at?new Date(i.claim_start_at):null,waiting=i.status==="open"&&start&&start>Date.now();
  const state=i.status!=="open"?"나눔 완료":waiting?"신청 대기":"나눔 중";
  const buttonText=i.status!=="open"?esc(i.claimant||"이웃")+"님 신청 완료":waiting?`남은 시간 ${countdown(start-Date.now())}`:"나눔 신청하기";
  return `<article class="card"><div class="visual ${esc(i.category)}">${i.image_url?`<img src="${esc(i.image_url)}" alt="">`:`<span>${emo}</span>`}<b class="status ${i.status!=="open"?"done":waiting?"waiting":""}">${state}</b></div><div class="cardBody"><div class="meta"><strong>${esc(i.category)}</strong><span>📍 ${esc(i.location)}</span></div><h3>${esc(i.title)}</h3><p>${esc(i.description)}</p>${start?`<div class="schedule">⏰ ${dateLabel(start)} 신청 시작</div>`:""}<button class="claim liveCountdown ${waiting?"":"started"}" data-id="${i.id}" data-title="${esc(i.title)}" ${start?`data-countdown="${start.toISOString()}"`:""} data-open="${i.status==="open"}" ${i.status==="open"&&!waiting?"":"disabled"}>${buttonText}</button><div class="foot"><span><b>${esc(i.giver)}</b>님의 나눔</span>${i.can_delete?`<button class="deleteItem" data-id="${i.id}" data-title="${esc(i.title)}">삭제</button>`:""}</div></div></article>`;
}
function myItemRow(i,type){
  const done=i.status!=="open",start=i.claim_start_at?new Date(i.claim_start_at):null,claimed=i.claimed_at?new Date(i.claimed_at):null;
  const detail=type==="created"
    ?(done?`${esc(i.claimant||"신청자")}님이 신청했어요`:(start?`${dateLabel(start)} 신청 시작`:"신청 대기 중"))
    :(claimed?`${dateLabel(claimed)} 신청 완료`:"신청 시각 기록 없음");
  return `<article class="myItem"><div class="myItemMain"><div class="myItemTop"><span class="myCategory">${esc(i.category)}</span><span class="myStatus ${done?"done":""}">${done?"신청 완료":"나눔 중"}</span></div><h4>${esc(i.title)}</h4><p>📍 ${esc(i.location)} · ${detail}</p></div>${type==="created"&&i.can_delete?`<button class="deleteItem" data-id="${i.id}" data-title="${esc(i.title)}">삭제</button>`:""}</article>`;
}
async function loadMyPage(){
  const res=await fetch("/api/me/items"),data=await res.json();
  if(!res.ok){if(res.status===401){currentUser=null;updateAuth();modal("myPageModal",false);modal("loginModal",true)}return toast(data.error||"마이페이지를 불러오지 못했습니다.",true)}
  $("myProfile").textContent=`${currentUser.display_name}님 · @${currentUser.username}`;
  $("createdCount").textContent=`${data.created.length}개`;
  $("claimedCount").textContent=`${data.claimed.length}개`;
  $("myCreatedList").innerHTML=data.created.length?data.created.map(i=>myItemRow(i,"created")).join(""):'<div class="myEmpty">아직 등록한 나눔이 없어요.</div>';
  $("myClaimedList").innerHTML=data.claimed.length?data.claimed.map(i=>myItemRow(i,"claimed")).join(""):'<div class="myEmpty">아직 신청한 나눔이 없어요.</div>';
  $("myCreatedList").querySelectorAll(".deleteItem").forEach(b=>b.onclick=()=>deleteItem(Number(b.dataset.id),b.dataset.title));
}
function updateCountdowns(){
  document.querySelectorAll('.claim.liveCountdown[data-open="true"][data-countdown]').forEach(button=>{
    const left=new Date(button.dataset.countdown)-Date.now(),status=button.closest(".card").querySelector(".status");
    if(left<=0){button.disabled=false;button.textContent="나눔 신청하기";button.classList.add("started");button.classList.remove("waiting");status.textContent="나눔 중";status.classList.remove("waiting")}
    else{button.disabled=true;button.textContent=`남은 시간 ${countdown(left)}`}
  });
}
function modal(id,show){$(id).classList.toggle("show",show)}
function updateAuth(){
  $("guestActions").classList.toggle("hidden",!!currentUser);$("userActions").classList.toggle("hidden",!currentUser);
  $("userName").textContent=currentUser?(currentUser.role==="admin"?`🛡️ 관리자 ${currentUser.display_name}`:`${currentUser.display_name}님`):"";
}
async function loadAuth(){const res=await fetch("/api/auth/status"),data=await res.json();currentUser=data.user||null;updateAuth()}
$("open").onclick=()=>{if(!currentUser){toast("로그인 후 나눔을 등록할 수 있어요.",true);return modal("loginModal",true)}const start=new Date(Date.now()+60000),input=$("claimStartAt");input.min=localInputValue(new Date());if(!input.value)input.value=localInputValue(start);claimStartConfirmed=false;$("claimStartConfirmed").textContent="시간을 선택한 뒤 확인해 주세요.";$("claimStartConfirmed").classList.remove("confirmed");modal("modal",true)};
$("close").onclick=()=>modal("modal",false);$("registerClose").onclick=()=>modal("registerModal",false);$("loginClose").onclick=()=>modal("loginModal",false);
$("openRegister").onclick=()=>modal("registerModal",true);$("openLogin").onclick=()=>modal("loginModal",true);
$("openMyPage").onclick=()=>{modal("myPageModal",true);loadMyPage()};$("myPageClose").onclick=()=>modal("myPageModal",false);
$("goLogin").onclick=()=>{modal("registerModal",false);modal("loginModal",true)};$("goRegister").onclick=()=>{modal("loginModal",false);modal("registerModal",true)};
$("claimStartAt").oninput=()=>{claimStartConfirmed=false;$("claimStartConfirmed").textContent="변경한 시간을 다시 확인해 주세요.";$("claimStartConfirmed").classList.remove("confirmed")};
$("confirmClaimStart").onclick=()=>{const input=$("claimStartAt"),start=new Date(input.value);if(!input.value||Number.isNaN(start.getTime()))return toast("신청 시작 시간을 선택해 주세요.",true);if(start<=new Date())return toast("현재보다 이후 시간을 선택해 주세요.",true);claimStartConfirmed=true;$("claimStartConfirmed").textContent=`✓ ${dateLabel(start)}로 설정됐어요.`;$("claimStartConfirmed").classList.add("confirmed")};
["modal","registerModal","loginModal","myPageModal"].forEach(id=>$(id).onclick=e=>{if(e.target===$(id))modal(id,false)});
$("search").oninput=()=>load();
async function openClaim(id,title){
  if(!currentUser){toast("로그인 후 신청할 수 있어요.",true);return modal("loginModal",true)}
  const res=await fetch(`/api/items/${id}/claim`,{method:"POST"}),data=await res.json();
  if(!res.ok){if(res.status===401){currentUser=null;updateAuth();modal("loginModal",true)}toast(data.error||"신청 실패",true);return load()}
  toast(`${title} 나눔 신청이 확정되었어요!`);load();
}
async function deleteItem(id,title){
  if(!confirm(`${title} 나눔을 삭제할까요?`))return;
  const res=await fetch(`/api/items/${id}`,{method:"DELETE"}),data=await res.json();
  if(!res.ok){if(res.status===401){currentUser=null;updateAuth();modal("loginModal",true)}return toast(data.error||"삭제 실패",true)}
  toast("나눔을 삭제했어요.");await load();if($("myPageModal").classList.contains("show"))await loadMyPage();
}
$("form").onsubmit=async e=>{
  e.preventDefault();if(!claimStartConfirmed)return toast("신청 시작 시간을 확인해 주세요.",true);const body=Object.fromEntries(new FormData(e.target));
  body.claimStartAt=new Date(body.claimStartAt).toISOString();
  const res=await fetch("/api/items",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(body)}),data=await res.json();
  if(!res.ok)return toast(data.error||"등록 실패",true);
  e.target.reset();claimStartConfirmed=false;modal("modal",false);toast("나눔 물건이 등록되었어요!");load();
};
$("registerForm").onsubmit=async e=>{e.preventDefault();const body=Object.fromEntries(new FormData(e.target));if(body.password!==body.confirmPassword)return toast("비밀번호가 일치하지 않습니다.",true);const res=await fetch("/api/auth/register",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(body)}),data=await res.json();if(!res.ok)return toast(data.error||"회원가입 실패",true);currentUser=data.user;e.target.reset();modal("registerModal",false);updateAuth();toast(`${currentUser.display_name}님, 가입을 환영해요!`)};
$("loginForm").onsubmit=async e=>{e.preventDefault();const body=Object.fromEntries(new FormData(e.target));const res=await fetch("/api/auth/login",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(body)}),data=await res.json();if(!res.ok)return toast(data.error||"로그인 실패",true);currentUser=data.user;e.target.reset();modal("loginModal",false);updateAuth();toast(`${currentUser.display_name}님, 로그인했어요!`)};
$("logout").onclick=async()=>{await fetch("/api/auth/logout",{method:"POST"});currentUser=null;modal("myPageModal",false);updateAuth();toast("로그아웃했어요.")};
setInterval(updateCountdowns,1000);
loadAuth();load();

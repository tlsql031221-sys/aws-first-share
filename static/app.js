const categories=["전체","디지털","생활","도서","의류","기타"];let current="전체",claimId=null;
const $=id=>document.getElementById(id);const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function toast(message,error=false){$("toast").textContent=message;$("toast").className="toast show"+(error?" error":"");setTimeout(()=>$("toast").className="toast",2800)}
async function load(){
  const q=encodeURIComponent($("search").value.trim()),cat=encodeURIComponent(current);
  const res=await fetch(`/api/items?q=${q}&category=${cat}`),items=await res.json();
  $("filters").innerHTML=categories.map(c=>`<button class="filter ${c===current?"on":""}" data-category="${c}">${c}</button>`).join("");
  $("filters").querySelectorAll("button").forEach(b=>b.onclick=()=>{current=b.dataset.category;load()});
  $("grid").innerHTML=items.length?items.map(card).join(""):'<div class="empty">조건에 맞는 나눔이 아직 없어요.</div>';
  document.querySelectorAll(".claim").forEach(b=>b.onclick=()=>openClaim(Number(b.dataset.id),b.dataset.title));
}
function card(i){
  const emo={디지털:"⌨️",생활:"🪴",도서:"📚",의류:"👕",기타:"🎁"}[i.category]||"🎁";
  return `<article class="card"><div class="visual ${esc(i.category)}">${i.image_url?`<img src="${esc(i.image_url)}" alt="">`:`<span>${emo}</span>`}<b class="status ${i.status==="open"?"":"done"}">${i.status==="open"?"나눔 중":"나눔 완료"}</b></div><div class="cardBody"><div class="meta"><strong>${esc(i.category)}</strong><span>📍 ${esc(i.location)}</span></div><h3>${esc(i.title)}</h3><p>${esc(i.description)}</p><div class="foot"><span><b>${esc(i.giver)}</b>님의 나눔</span><button class="claim" data-id="${i.id}" data-title="${esc(i.title)}" ${i.status==="open"?"":"disabled"}>${i.status==="open"?"나눔받기":esc(i.claimant||"이웃")+" 신청"}</button></div></div></article>`;
}
function modal(id,show){$(id).classList.toggle("show",show)}
$("open").onclick=()=>modal("modal",true);$("close").onclick=()=>modal("modal",false);$("claimClose").onclick=()=>modal("claimModal",false);
["modal","claimModal"].forEach(id=>$(id).onclick=e=>{if(e.target===$(id))modal(id,false)});
$("search").oninput=()=>load();
function openClaim(id,title){claimId=id;$("claimTitle").textContent=title;modal("claimModal",true)}
$("form").onsubmit=async e=>{
  e.preventDefault();const body=Object.fromEntries(new FormData(e.target));
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

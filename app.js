const basePath='';

let baseline,state,current,filter='all',search='',issueFilter='',queue=Promise.resolve(),timer,saveError=false;

const $=id=>document.getElementById(id);

const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

const label={pending:'Pending',proposed:'Accept proposed',original:'Keep original',edited:'Accept with changes'};

const fieldOrder=['h1','intro','body_h2','body_h2_second','secondary_h1','title','meta'];

const applicable=p=>Object.keys(p.fields).filter(k=>p.fields[k].applicable);

const reviewKeys=p=>applicable(p).filter(k=>p.fields[k].required!==false||choice(p,k).editedTouched||choice(p,k).status!=='pending');

let previewMode='draft';const contextCache={};

const canvas=document.createElement('canvas'),ctx=canvas.getContext('2d');

function choice(p,key){return state.pages[p.id]?.fields?.[key]??{status:'pending',edited:'',editedTouched:false,explicitPending:false};}

function pageDone(p){return p.reviewable&&reviewKeys(p).every(k=>choice(p,k).status!=='pending');}

function localDecision(p){return state.pages[p.id]??={fields:{},note:''};}

function localField(p,key){const d=localDecision(p);return d.fields[key]??={status:'pending',edited:'',editedTouched:false,explicitPending:false};}

function visible(){return baseline.pages.filter(p=>(filter==='all'||(filter==='complete'?pageDone(p):filter==='skipped'?state.pages[p.id]?.skipped:!pageDone(p)&&!state.pages[p.id]?.skipped))&&(!issueFilter||p.issues.includes(issueFilter))&&(!search||[p.url,p.target,...p.issues].join(' ').toLowerCase().includes(search)));}

function displayText(p,key){const c=choice(p,key),f=p.fields[key];if(!f)return '';if(!f.applicable)return f.original;if(c.status==='original')return f.original;if(c.editedTouched||c.status==='edited')return c.edited;return f.proposed;}

function sidebar(){
 const pages=baseline.pages,completed=pages.filter(pageDone).length,list=visible();
 $('progress').innerHTML=`<strong>${completed} / ${pages.length}</strong> pages decided<small>${pages.length-completed} pending · ${pages.filter(p=>state.pages[p.id]?.skipped).length} skipped for later</small>`;
 $('filteredCount').textContent=`${list.length} in this view · ${pages.length} total pages`;
 $('pages').replaceChildren();
 for(const p of list){const b=document.createElement('button');b.className=p.id===current?.id?'selected':'';b.textContent=p.fields.h1?.proposed||p.fields.title?.proposed||p.url;const small=document.createElement('small');small.textContent=`${p.id} · ${pageDone(p)?'Decided':'Pending'}`;b.append(small);b.onclick=()=>navigate(p.id);$('pages').append(b);}
}

function widthInfo(key,text){if(key!=='title'&&key!=='meta')return `${text.length} characters`;ctx.font=`${key==='title'?20:14}px Arial`;const px=ctx.measureText(text).width,limit=key==='title'?580:920;return `${text.length} characters · ${Math.round(px)} px estimate / ${limit} px target <span class="${px>limit?'warning':''}">${px>limit?'Over '+limit+' px editorial target':'Within editorial width estimate'}</span>`;}

function beforeIssueBadges(scope){const issues=current.issues.filter(issue=>scope==='h1'?(/\bh1\b/i.test(issue)||issue==='Page has identical headings'):scope==='title'?/^Title\b/i.test(issue):/^Description\b/i.test(issue));return issues.length?`<div class="previewIssues" data-issue-scope="${scope}" aria-label="Original ${scope==='meta'?'meta description':scope==='title'?'page title':'heading'} issues">${issues.map(issue=>`<span class="issuePill">${esc(issue)}</span>`).join('')}</div>`:'';}

function previewSingle(original,siteId,searchId){
 const text=k=>original?(current.fields[k]?.original??''):displayText(current,k),brand=baseline.brand;
 const logo=brand.logo?`<img src="/${esc(brand.logo)}" alt="${esc(brand.name)}">`:`<span class="brandText">${esc(brand.name)}</span>`;
 const photo=brand.image?`<img class="mobileReference" src="/${esc(brand.image)}" alt="${esc(brand.imageAlt||'Shared brand reference image')}">`:'';
 const h1=current.fields.h1?`<h2>${esc(text('h1'))}</h2>`:'<p class="missingPreview">No H1 field supplied for this page.</p>';
 const intro=current.fields.intro?`<p class="brandIntro">${esc(text('intro'))}</p>`:'';
 $(siteId).innerHTML=`<div class="brandPage"><div class="brandHeader">${logo}<span class="mockMenu" aria-hidden="true">☰</span></div>${photo}<div class="brandHero"><div class="brandCategory">${esc(brand.category||current.type)}</div>${original?beforeIssueBadges('h1'):''}${h1}${intro}</div></div>`;
 $(searchId).innerHTML=`<div class="googleIdentity"><div><div class="googleSiteName">${esc(brand.name)}</div><div class="googleUrl">${esc(current.url)}</div></div></div>${original?beforeIssueBadges('title'):''}<div class="googleTitle">${esc(current.fields.title?text('title'):'(Page title not supplied)')}</div>${original?beforeIssueBadges('meta'):''}<div class="googleDescription">${esc(current.fields.meta?text('meta'):'(Meta description not supplied)')}</div>`;
}
function previews(){previewSingle(true,'siteBefore','searchBefore');previewSingle(false,'siteViewport','searchPreview');}
function focusPreview(){}
function loadContext(){}

// Same-page decisions preserve the reviewer's position, focus and expanded notes.
function render(){
 const x=window.scrollX,y=window.scrollY,navScroll=$('pages').scrollTop;
 const focused=document.activeElement,fieldKey=focused?.closest('.field')?.dataset.field;
 const buttonText=focused?.tagName==='BUTTON'?focused.textContent:null;const focusedId=focused?.id;
 const openDetails=[...document.querySelectorAll('.field details[open]')].map(e=>e.closest('.field').dataset.field);
 const resized=[...document.querySelectorAll('.field textarea')].filter(e=>e.style.height).map(e=>[e.closest('.field').dataset.field,e.style.height]);
 renderContent();
 for(const key of openDetails){const detail=document.querySelector(`.field[data-field="${key}"] details`);if(detail)detail.open=true;}
 for(const [key,height]of resized){const input=document.querySelector(`.field[data-field="${key}"] textarea`);if(input)input.style.height=height;}
 if(fieldKey&&buttonText){const field=document.querySelector(`.field[data-field="${fieldKey}"]`);const replacement=[...(field?.querySelectorAll('button')??[])].find(b=>b.textContent===buttonText);replacement?.focus({preventScroll:true});}
 if(focusedId)$(focusedId)?.focus({preventScroll:true});
 $('pages').scrollTop=navScroll;
 window.scrollTo({left:x,top:y,behavior:'instant'});
}

function renderContent(){const p=current;$('pageLabel').textContent=`${p.id} · ${p.type}`;$('pageTitle').textContent=p.fields.h1?.proposed||p.fields.title?.proposed||p.url;$('source').textContent=p.url;$('source').href=p.url;

 $('metrics').innerHTML=p.issues.map(x=>`<span class="issuePill">${esc(x)}</span>`).join('');

 $('evidenceBody').textContent=`Source row ${p.sourceRow}. ${p.inspection}. ${p.condition||''}`;

 for(const id of ['fields','pageFields','searchFields'])$(id).replaceChildren(); $('pagePicker').innerHTML=baseline.pages.map(x=>`<option value="${esc(x.id)}">${esc(x.id+' · '+(x.fields.h1?.original||x.url)+' · '+(pageDone(x)?'Decided':state.pages[x.id]?.skipped?'Skipped':'Pending'))}</option>`).join('');$('pagePicker').value=p.id;$('fieldProgress').textContent=p.reviewable?`${reviewKeys(p).filter(k=>choice(p,k).status!=='pending').length} / ${reviewKeys(p).length} review decisions · ${applicable(p).length} editable fields`:'';

 if(!p.reviewable){const e=document.createElement('div');e.className='unavailable';e.textContent=p.aliasOf?`This URL is an alias of ${p.aliasOf}. Review that record to avoid duplicate implementation.`:'This URL returns 404. Resolve the destination before reviewing copy.';if(p.aliasOf){const b=document.createElement('button');b.textContent='Review '+p.aliasOf;b.onclick=()=>navigate(p.aliasOf);e.append(document.createElement('br'),b);}$('fields').append(e);}

 else for(const key of fieldOrder){const f=p.fields[key];if(!f||!f.applicable)continue;const c=choice(p,key),div=document.createElement('div');div.className='field';div.dataset.field=key;div.innerHTML=`<div class="fieldTop"><h3>${esc(f.label)}</h3><span>${esc(label[c.status])}${c.editedTouched&&c.status==='pending'?' · edited draft':''}</span></div><div class="fieldRole">${f.required?'Prepared recommendation from your spreadsheet':'Optional field · unchanged in spreadsheet'}</div><textarea rows="${key==='meta'||key==='intro'?3:2}" aria-label="${esc(f.label)} proposed copy"></textarea><div class="width"></div><div class="actions"></div><div class="originalHint"><b>Original:</b> ${esc(f.original||'(Empty in source spreadsheet)')}</div><details class="fieldDetails"><summary>Rationale and implementation notes</summary><p class="muted">${esc(f.rationale)}</p><p class="fieldCondition">${esc(f.condition)}</p></details>`;

const input=div.querySelector('textarea');input.value=c.editedTouched?c.edited:f.proposed;div.querySelector('.width').innerHTML=widthInfo(key,input.value);input.onfocus=()=>focusPreview(key);

 input.oninput=()=>{hideMessage();localDecision(p).skipped=false;const v=localField(p,key);if(v.status!=='pending'){v.previousDecision=v.status;v.status='pending';v.explicitPending=false;}v.edited=input.value;v.editedTouched=true;v.updatedAt=new Date().toISOString();previewMode='draft';div.querySelector('.width').innerHTML=widthInfo(key,input.value);div.querySelector('.fieldTop span').textContent='Pending · edited draft';previews();schedule();};

 for(const [status,text]of [['proposed','Accept proposed'],['original',f.original?'Keep original':'Keep original empty'],['edited','Accept with changes'],['pending','Undo decision']]){const b=document.createElement('button');b.textContent=text;b.className=c.status===status&&status!=='pending'?'active':'';b.onclick=async()=>{const v=localField(p,key);if(status==='edited'){if(!input.value.trim())return message('Enter edited text, or choose Keep original empty if the original is empty.');v.edited=input.value;v.editedTouched=true;}if(status==='proposed'){v.edited='';v.editedTouched=false;}v.status=status;v.explicitPending=status==='pending';v.updatedAt=new Date().toISOString();render();await save();};div.querySelector('.actions').append(b);}$(key==='title'||key==='meta'?'searchFields':'pageFields').append(div);}

 $('notes').value=state.pages[p.id]?.note??'';$('notes').disabled=!p.reviewable;for(const id of ['saveNext','acceptAll'])$(id).disabled=!p.reviewable;previews();loadContext(p);sidebar();position();}

function nextInView(direction){const allowed=new Set(visible().map(p=>p.id));const index=baseline.pages.findIndex(p=>p.id===current.id);if(index<0)return;for(let i=index+direction;i>=0&&i<baseline.pages.length;i+=direction){if(allowed.has(baseline.pages[i].id))return baseline.pages[i];}}
function position(){const list=visible(),i=list.findIndex(p=>p.id===current.id);$('position').textContent=i<0?(pageDone(current)?'This page is complete':state.pages[current.id]?.skipped?'Skipped for later':'Outside current filter'):`${i+1} of ${list.length} in view`;$('previous').disabled=!nextInView(-1);$('next').disabled=!nextInView(1);}

let messageTimer,messageFadeTimer;
function hideMessage(force=false){const box=$('message');if(!force&&box.dataset.persistent==='true')return;clearTimeout(messageTimer);clearTimeout(messageFadeTimer);box.classList.add('messageFading');messageFadeTimer=setTimeout(()=>{box.hidden=true;box.classList.remove('messageFading');},250);}
function message(text,{persistent=false}={}){const box=$('message');clearTimeout(messageTimer);clearTimeout(messageFadeTimer);box.classList.remove('messageFading');box.dataset.persistent=String(persistent);box.hidden=false;box.replaceChildren();const content=document.createElement('span');content.textContent=text;const close=document.createElement('button');close.type='button';close.className='dismissMessage';close.setAttribute('aria-label','Dismiss notification');close.textContent='×';close.onclick=()=>hideMessage(true);box.append(content,close);if(!persistent)messageTimer=setTimeout(()=>hideMessage(),4500);}



function schedule(){clearTimeout(timer);$('saveStatus').textContent='Unsaved changes';timer=setTimeout(()=>save().catch(()=>{}),600);}

async function api(path,body){const r=await fetch(basePath+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!r.ok){const data=await r.json();throw Error(data.error||'Request failed');}return r;}

function save(){clearTimeout(timer);timer=null;if(!current.reviewable)return queue;const id=current.id,decision=structuredClone(localDecision(current));$('saveStatus').textContent='Saving…';const task=queue.then(async()=>{try{const response=await api('/api/save',{baselineVersion:baseline.version,expectedRevision:state.revision,pageId:id,decision,currentId:id});const saved=await response.json();state.revision=saved.revision;state.updatedAt=saved.updatedAt;saveError=false;if($('message').dataset.persistent==='true')hideMessage(true);$('saveStatus').className='';$('saveStatus').textContent='Saved to disk';}catch(e){saveError=true;$('saveStatus').textContent='Save failed';$('saveStatus').className='error';message(e.message,{persistent:true});throw e;}});queue=task.catch(()=>{});return task;}

let navigating=false,advancing=false;
async function navigate(id){if(navigating||advancing)return;navigating=true;try{if(current?.reviewable)await save();if(saveError)return;hideMessage();current=baseline.pages.find(p=>p.id===id);render();if(current.reviewable)await save();window.scrollTo({top:0,behavior:'smooth'});}catch{}finally{navigating=false;}}

async function step(direction){const target=nextInView(direction);if(target)await navigate(target.id);}

function download(blob,name){const a=document.createElement('a'),u=URL.createObjectURL(blob);a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}

$('search').oninput=()=>{search=$('search').value.trim().toLowerCase();sidebar();position();};$('issueFilter').onchange=()=>{issueFilter=$('issueFilter').value;sidebar();position();};$('filter').onchange=()=>{filter=$('filter').value;sidebar();position();};$('notes').oninput=()=>{localDecision(current).note=$('notes').value;schedule();};$('previous').onclick=()=>step(-1);$('next').onclick=()=>step(1);$('saveNext').onclick=()=>saveNext(false);$('acceptAll').onclick=()=>bulkCopy('current',true);$('approvePage').onclick=()=>bulkCopy('current',false);$('keepAll').onclick=()=>bulkCopy('original',true);$('skip').onclick=()=>skipPage();$('pagePicker').onchange=()=>navigate($('pagePicker').value);

$('backup').onclick=async()=>{try{await save();if(saveError)return;download(await(await fetch(basePath+'/api/backup')).blob(),'seo-copy-review-backup.json');}catch{}};

$('restore').onclick=()=>$('restoreFile').click();$('restoreFile').onchange=async e=>{try{const file=e.target.files[0];if(!file)return;await save();const backup=JSON.parse(await file.text());const r=await api('/api/restore',{expectedRevision:state.revision,backup});state=await r.json();current=baseline.pages.find(p=>p.id===state.currentId);render();$('saveStatus').textContent='Backup restored';$('message').hidden=true;}catch(e){message(e.message,{persistent:true});}finally{$('restoreFile').value='';}};

$('export').onclick=async()=>{try{await save();if(saveError)return;const response=await fetch('/api/export.csv');if(!response.ok)throw Error('Export failed');download(await response.blob(),'seo-copy-reviewed.csv');}catch(e){message(e.message,{persistent:true});}};

window.addEventListener('beforeunload',e=>{if(timer||saveError){e.preventDefault();e.returnValue='';}});

(async()=>{try{const data=await(await fetch(basePath+'/api/data')).json();baseline=data.baseline;state=data.state;
 const brand=baseline.brand,style=document.documentElement.style;
 style.setProperty('--brand-bg',brand.headerBackground);style.setProperty('--brand-text',brand.headerText);style.setProperty('--brand-font',brand.font||'Arial');style.setProperty('--accent',brand.accent);
 document.querySelector('.wordmark').textContent=brand.name;document.title=brand.name+' · SEO Copy Review';document.querySelector('.mobileNote').textContent=brand.caption||'Shared brand imagery. Illustrative copy layout, not a live page rendering.';
 $('filter').value='all';
for(const [name,count]of Object.entries(baseline.issueCounts)){const option=document.createElement('option');option.value=name;option.textContent=name+' ('+count+')';$('issueFilter').append(option);}current=baseline.pages.find(p=>p.id===state.currentId)??baseline.pages[0];$('loading').hidden=true;$('review').hidden=false;render();}catch(e){$('loading').textContent='Could not load the review.';message(e.message,{persistent:true});}})();



function pixelWidth(key,text){if(!['title','meta'].includes(key))return 0;ctx.font=`${key==='title'?20:14}px Arial`;return ctx.measureText(text).width;}

function withinLimit(){return true;} // Width estimates are editing guidance, not hard limits.

async function saveNext(){if(advancing||navigating)return;const p=current;for(const key of applicable(p)){const c=choice(p,key);if(c.status==='pending'&&c.editedTouched&&!c.explicitPending&&(!c.edited.trim()||!withinLimit(key,c.edited)))return message('Enter copy for the edited field, or explicitly keep the original before continuing.');}for(const key of applicable(p)){const c=localField(p,key);if(c.status==='pending'&&c.editedTouched&&!c.explicitPending)c.status='edited';}localDecision(p).skipped=false;await moveAfterSave(true);}

async function moveAfterSave(next){if(advancing)return;advancing=true;const target=next?nextInView(1):null;try{await save();if(next&&target){hideMessage();current=target;render();await save();window.scrollTo({top:0,behavior:'smooth'});}else{render();if(next)message('Saved. End of this filtered queue — no pages remain after this one. Use the page selector or change filters to revisit earlier pages.');}}catch{}finally{advancing=false;}}

async function bulkCopy(mode,next){if(advancing||navigating)return;const p=current,keys=applicable(p).filter(k=>k!=='structure');if(mode==='current')for(const key of keys){const text=displayText(p,key),c=choice(p,key);if(!text.trim())return message('Decide empty fields individually.');if((c.editedTouched||p.fields[key].required)&&c.status!=='original'&&!withinLimit(key,text))return message('Shorten '+p.fields[key].label+' before approving all.');}for(const key of keys){const c=localField(p,key);if(mode==='original')c.status='original';else if(c.status==='original')continue;else c.status=c.editedTouched?'edited':'proposed';c.explicitPending=false;c.updatedAt=new Date().toISOString();}localDecision(p).skipped=false;await moveAfterSave(next);}

async function skipPage(){if(advancing||navigating)return;localDecision(current).skipped=true;await moveAfterSave(true);message('Skipped for later. Drafts and existing decisions are saved; no new approvals were made.');}



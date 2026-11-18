import fs from 'node:fs/promises';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source=await fs.readFile(new URL('app.js',import.meta.url),'utf8');
const start=source.indexOf('let messageTimer,messageFadeTimer;'),end=source.indexOf('\nfunction schedule',start);assert(start>=0&&end>start);
let sequence=0;const timers=new Map(),classes=new Set();
const box={hidden:true,dataset:{},classList:{add:x=>classes.add(x),remove:x=>classes.delete(x)},replaceChildren(){this.children=[];},append(...nodes){this.children.push(...nodes);}};
const context={document:{createElement:()=>({setAttribute(){}})},$:()=>box,setTimeout:(fn,ms)=>{const id=++sequence;timers.set(id,{fn,ms});return id;},clearTimeout:id=>timers.delete(id)};vm.createContext(context);vm.runInContext(source.slice(start,end),context);
function runDelay(ms){for(const [id,t]of [...timers])if(t.ms===ms){timers.delete(id);t.fn();}}
vm.runInContext("message('Width limit reached')",context);assert.equal(box.hidden,false);assert.equal(timers.size,1);runDelay(4500);assert(classes.has('messageFading'));runDelay(250);assert.equal(box.hidden,true);
vm.runInContext("message('First');message('Second')",context);assert.equal(timers.size,1);assert.equal(box.children[0].textContent,'Second');
vm.runInContext('hideMessage()',context);runDelay(250);assert(box.hidden);
vm.runInContext("message('Save failed',{persistent:true});hideMessage()",context);assert.equal(timers.size,0);assert.equal(box.hidden,false);assert(!classes.has('messageFading'));
box.children[1].onclick();runDelay(250);assert(box.hidden);
console.log('PASS: portable regression checks');

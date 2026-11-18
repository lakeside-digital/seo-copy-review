import fs from 'node:fs/promises';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const root=new URL('.',import.meta.url),source=await fs.readFile(new URL('app.js',root),'utf8');
const fn=source.match(/^function nextInView\(direction\).*$/m)[0];
const order=['A','B','C','D','E'].map(id=>({id}));
function next(id,eligible,direction=1){const context={baseline:{pages:order},current:{id},visible:()=>order.filter(p=>eligible.includes(p.id)),Set};return vm.runInNewContext(fn+';nextInView('+direction+')?.id',context);}
assert.equal(next('C',['A','D','E']),'D','Completed current page removed from pending must advance, not restart at A');
assert.equal(next('B',['A','E']),'E','Skip consecutive completed/skipped pages');
assert.equal(next('E',['A','B']),undefined,'End of queue must not wrap');
assert.equal(next('C',['A','D'],-1),'A','Previous works even when current is filtered out');
assert.equal(next('A',['C']), 'C','Search/issue-filtered next respects stable order');
assert.equal(next('C',[]),undefined,'Empty view has no fallback');
assert.equal(next('A',['A','B','C']), 'B','All-pages view advances normally');
assert.equal(next('missing',['A','B']),undefined,'Unknown IDs never wrap');
console.log('PASS: portable regression checks');

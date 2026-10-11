const test=require('node:test');
const assert=require('node:assert/strict');
const {ranges}=require('../public/klipe-background');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
test('long videos are split into bounded contiguous jobs',()=>{
  assert.deepEqual(ranges(0,101.8,101.8),[[0,30],[30,60],[60,90],[90,101.8]]);
});
test('range boundaries stay inside requested media and align to frames',()=>{
  const r=ranges(.011,31.999,32);
  assert.equal(r[0][0],1/30);assert.equal(r.at(-1)[1],959/30);
  assert.equal(r[0][1],r[1][0]);
});
test('invalid and oversized intervals are rejected before starting jobs',()=>{
  for(const args of [[-1,2,10],[3,3,10],[0,11,10],[0,601,700],[0,1,10,0],[NaN,1,10],[0,.001,10]])
    assert.throws(()=>ranges(...args));
});
test('background removal lives in Properties without placeholder or AI tabs',()=>{
  const html=fs.readFileSync(path.join(__dirname,'../editor.html'),'utf8');
  const script=fs.readFileSync(path.join(__dirname,'../public/klipe-background.js'),'utf8');
  assert.match(html,/data-background-removal-host/);
  assert.match(html,/backgroundRemoval\?\.mount/);
  assert.doesNotMatch(html,/onclick="NLE\.ia\.abrir\(\)"|data-cctab="ai"|data-ccpanel="ai"|data-ccsub="retouch"|data-ccsubpanel="retouch"/);
  assert.doesNotMatch(script,/createElement\('dialog'\)|btn-remove-background|showModal/);
  for(const match of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)) {
    if(match[1].trim())assert.doesNotThrow(()=>new vm.Script(match[1]));
  }
});
test('Properties remount preserves controls and resets range only for another clip',()=>{
  const script=fs.readFileSync(path.join(__dirname,'../public/klipe-background.js'),'utf8');
  const fields=new Map();
  const field=id=>{
    if(!fields.has(id))fields.set(id,{value:'',addEventListener(){}});
    return fields.get(id);
  };
  const panel={setAttribute(){},querySelector:field,querySelectorAll(){return []}};
  const state={selection:['a'],videoDuration:20,tracks:[{type:'video',clips:[
    {id:'a',startSec:0,endSec:10},{id:'b',startSec:10,endSec:20}
  ]}]};
  const NLE={sm:{getState:()=>state}};
  const document={createElement:()=>panel,querySelector:()=>null};
  vm.runInNewContext(script,{document,NLE,window:{KlipeAssist:{}}});
  const mounted=[];
  const host={append:p=>mounted.push(p)};
  NLE.backgroundRemoval.mount(host);
  assert.equal(field('#bg-start').value,'0.000');
  assert.equal(field('#bg-end').value,'10.000');
  field('#bg-end').value='2.5';
  NLE.backgroundRemoval.mount(null);
  NLE.backgroundRemoval.mount(host);
  assert.equal(field('#bg-end').value,'2.5');
  assert.ok(mounted.every(p=>p===panel));
  state.selection=['b'];
  NLE.backgroundRemoval.mount(host);
  assert.equal(field('#bg-start').value,'10.000');
  assert.equal(field('#bg-end').value,'20.000');
});

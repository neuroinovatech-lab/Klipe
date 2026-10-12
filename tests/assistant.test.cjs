const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const A=require('../public/klipe-assist-core');
const {resolveMedia}=require('../assistant-api');
const {requireSourceTimeline}=require('../assistant-api');
test('visual jobs reject timelines requiring source-time remapping',()=>{
  assert.doesNotThrow(()=>requireSourceTimeline({videoDuration:8,videoClips:[{startSec:0,endSec:8}]}));
  assert.throws(()=>requireSourceTimeline({videoDuration:8,keepRanges:[[3,11]]}),/sincronismo/);
  assert.throws(()=>requireSourceTimeline({videoDuration:8,videoClips:[{startSec:0,endSec:8,srcStart:3}]}),/sincronismo/);
});
const config=()=>({projectName:'demo',width:1080,height:1920,fps:30,videoDuration:20,
  videoSrc:'projects/demo/video.mp4',videoClips:[],titles:[],captions:[],zooms:[],sfx:[]});
const transcript=[{start:1,end:4,text:'Primeiro, confira o resultado.'},{start:11,end:14,text:'Agora veja o desconto.'}];

test('analysis is read-only and uses corrected timeline captions',()=>{
  const cfg=config();cfg.captions=[{startSec:3,endSec:5,text:'Primeiro, texto corrigido.'}];
  const before=JSON.stringify(cfg),result=A.plan(cfg,transcript);
  assert.equal(JSON.stringify(cfg),before);
  assert.equal(result.speechCount,1);
  assert.equal(result.suggestions.find(s=>s.type==='title').clip.text,cfg.captions[0].text);
});
test('cut transcript drops removed words and maps kept words',()=>{
  const cfg=config();cfg.keepRanges=[[3,6],[10,14]];
  const data=[{start:2,end:5,text:'REMOVIDO palavra mantida',words:[
    {start:2,end:2.5,text:'REMOVIDO'},{start:3.2,end:3.8,text:'palavra'},{start:4,end:5,text:'mantida'}]},
    {start:11,end:12,text:'agora'}];
  const got=A.cues(cfg,data);
  assert.equal(got[0].text,'palavra mantida');assert.equal(got[0].words[0].start,.2);
  assert.equal(got[1].startSec,4);
});
test('partial source sentences without word timings are not invented',()=>{
  const cfg=config();cfg.keepRanges=[[3,5]];
  assert.deepEqual(A.cues(cfg,[{start:2,end:4,text:'inclui trecho removido'}]),[]);
});
test('suggestions preserve existing effects and never propose deleting speech',()=>{
  const cfg=config();cfg.titles=[{id:'user',startSec:0,endSec:6,text:'MEU TITULO'}];
  const plan=A.plan(cfg,transcript);
  assert(!plan.suggestions.some(s=>s.type==='title' && s.clip.startSec===1));
  assert(plan.suggestions.some(s=>s.type==='review'));
  assert(!plan.suggestions.some(s=>s.type==='delete' || s.type==='cut'));
});
test('applying the same suggestions twice does not duplicate effects',()=>{
  const cfg=config(),first=A.plan(cfg,transcript);
  for(const s of first.suggestions)if(A.tracks[s.type])cfg[A.tracks[s.type]].push(s.clip);
  assert(!A.plan(cfg,transcript).suggestions.some(s=>s.type!=='review'));
});
test('native titles animate position and bind editable text',()=>{
  const title=A.title(config(),{startSec:0,endSec:3,text:'O texto muda'},[]);
  assert.equal(title.cena.camadas[0].texto,'@titulo');
  assert(title.cena.camadas[0].y[0][1] < title.cena.camadas[0].y[1][1]);
  assert.equal(title.text,'O texto muda');
});
test('placement avoids detected face and refuses when all bands are blocked',()=>{
  const face={startSec:0,endSec:5,x:0,y:.6,w:1,h:.4};
  assert(A.freeY(config(),0,3,[face])>0);
  assert.equal(A.freeY(config(),0,3,[{...face,y:0,h:1}]),null);
});
test('only measured local sounds enter a proposal',()=>{
  const cfg=config();
  assert(!A.plan(cfg,transcript,{'sfx/pop.wav':{}}).suggestions.some(s=>s.type==='sfx'));
  const assets={'sfx/pop.wav':{duration:.37},'sfx/cash.wav':{duration:.62}};
  const sfx=A.plan(cfg,transcript,assets).suggestions.filter(s=>s.type==='sfx');
  assert.equal(sfx.length,2);assert.equal(sfx[0].clip.endSec,1.37);
});
test('inspector catches missing media, empty text, invalid intervals and overflow',()=>{
  const cfg=config();cfg.titles=[{id:'x',startSec:5,endSec:3,text:''},{id:'x',startSec:19,endSec:25,text:'teste'}];
  const codes=new Set(A.inspect(cfg,{[cfg.videoSrc]:{error:'ausente'}}).map(i=>i.code));
  for(const code of ['source','empty-text','duplicate','interval','overflow'])assert(codes.has(code));
});
test('snapshot includes unsaved edits and ignores playhead movement',()=>{
  const cfg=config(),state={...cfg,tracks:[{type:'title',clips:[{id:'x',text:'editado'}],locked:true}]};
  const first=A.snapshot(state,cfg);state.playhead=17;
  assert.equal(A.hash(first),A.hash(A.snapshot(state,cfg)));assert.equal(first.titles[0].text,'editado');
  assert.equal(first.titles[0]._locked,true);
});
test('media resolver isolates projects and denies traversal',()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'klipe-assist-'));
  try{
    fs.mkdirSync(path.join(root,'projects','a'),{recursive:true});
    fs.mkdirSync(path.join(root,'projects','b'),{recursive:true});
    fs.writeFileSync(path.join(root,'projects','a','v.mp4'),'a');
    fs.writeFileSync(path.join(root,'projects','b','v.mp4'),'b');
    assert(resolveMedia(root,'a','projects/a/v.mp4').endsWith('v.mp4'));
    for(const src of ['projects/b/v.mp4','../secret','projects/a/../../secret','C:/secret','https://example.org/a'])
      assert.throws(()=>resolveMedia(root,'a',src));
  }finally{fs.rmSync(root,{recursive:true,force:true});}
});
test('source analysis rejects active transforms but accepts disabled or anchor-only changes',()=>{
  const {hasVideoTransform}=require('../public/klipe-background');
  for(const change of [{scale:1.2},{scaleX:1.2},{scaleY:.8},{rotation:20},{posY:5},{pitch:4},{yaw:7},{flipX:true},{flipY:true}]){
    assert.equal(hasVideoTransform(change),true);
    assert.equal(hasVideoTransform({...change,transformEnabled:false}),false);
  }
  assert.equal(hasVideoTransform({}),false);
  assert.equal(hasVideoTransform({anchorX:150,anchorY:-20,scaleX:1,scaleY:1}),false);
  assert.equal(hasVideoTransform({scale:2,scaleX:1,scaleY:1}),false);
});

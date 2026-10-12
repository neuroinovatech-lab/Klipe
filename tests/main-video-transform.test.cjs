const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const scope={window:{}};
vm.runInNewContext(fs.readFileSync(require.resolve('../public/klipe_player.js'),'utf8'),scope);
const transform=(cfg,t)=>JSON.parse(JSON.stringify(scope.window.KlipePlayer.prototype._videoTransform.call({cfg},t)));
const basic=(cfg,t)=>{const {matrizVideo,...values}=transform(cfg,t);return values;};
test('main transform is selected per clip and resets outside the interval',()=>{
  const cfg={videoClips:[{startSec:1,endSec:2,posX:100,posY:-50,scale:.5}]};
  assert.deepEqual(basic(cfg,1.5),{posX:100,posY:-50,escala:.5});
  assert.deepEqual(basic(cfg,2),{posX:0,posY:0,escala:1});
});
test('independent scales, anchor, rotation and disabled state produce valid matrices',()=>{
  const tools=scope.window.KlipeVideoTransform;
  const m=tools.matrix({scaleX:.5,scaleY:.25,anchorX:16,anchorY:-8},64,64);
  assert.equal(m[0],.5);assert.equal(m[4],.25);
  assert.equal(m[6],.25);assert.equal(m[7],.1875);
  assert.deepEqual(Array.from(tools.matrix({rotation:30,pitch:50,transformEnabled:false},64,64)),[1,0,0,0,1,0,0,0,1]);
  const rotated=tools.matrix({rotation:90},320,180);
  assert.ok(Math.abs(rotated[1]+320/180)<1e-8);
  assert.ok(Math.abs(rotated[3]-180/320)<1e-8);
});
test('perspective remains finite at limits and saved fields retain false values',()=>{
  const tools=scope.window.KlipeVideoTransform;
  const m=tools.matrix({scaleX:3,scaleY:.1,pitch:60,yaw:-60,anchorX:1920,anchorY:-1080},1920,1080);
  assert.ok(m.every(Number.isFinite));
  for(const x of [-1,1])for(const y of [-1,1])assert.ok(m[2]*x+m[5]*y+m[8]>0);
  const saved=JSON.parse(JSON.stringify(tools.savedFields({scaleX:1,flipX:false,transformEnabled:false,scaleLinked:false,unknown:'ignored'})));
  assert.deepEqual(saved,{scaleX:1,flipX:false,transformEnabled:false,scaleLinked:false});
});
test('neutral clip overrides legacy globals and clamps invalid values',()=>{
  assert.equal(transform({videoBaseScale:2},0).escala,2);
  assert.equal(transform({videoBaseScale:2,videoClips:[{startSec:0,endSec:1}]},0).escala,1);
  assert.equal(transform({videoBaseScale:-1},0).escala,.1);
  assert.equal(transform({videoBaseScale:NaN},0).escala,1);
});

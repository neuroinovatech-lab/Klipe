const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const scope={window:{}};
vm.runInNewContext(fs.readFileSync(require.resolve('../public/klipe_player.js'),'utf8'),scope);
const transform=(cfg,t)=>JSON.parse(JSON.stringify(scope.window.KlipePlayer.prototype._videoTransform.call({cfg},t)));
test('main transform is selected per clip and resets outside the interval',()=>{
  const cfg={videoClips:[{startSec:1,endSec:2,posX:100,posY:-50,scale:.5}]};
  assert.deepEqual(transform(cfg,1.5),{posX:100,posY:-50,escala:.5});
  assert.deepEqual(transform(cfg,2),{posX:0,posY:0,escala:1});
});
test('neutral clip overrides legacy globals and clamps invalid values',()=>{
  assert.equal(transform({videoBaseScale:2},0).escala,2);
  assert.equal(transform({videoBaseScale:2,videoClips:[{startSec:0,endSec:1}]},0).escala,1);
  assert.equal(transform({videoBaseScale:-1},0).escala,.1);
  assert.equal(transform({videoBaseScale:NaN},0).escala,1);
});

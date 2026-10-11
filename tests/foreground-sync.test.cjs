const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const scope = {window:{},setTimeout(){}};
vm.runInNewContext(fs.readFileSync(require.resolve('../public/klipe_player.js'),'utf8'),scope);
const sync = scope.window.KlipePlayer.prototype._sincronizarRecorte;
function fixture(overrides={}) {
  const video={currentTime:1,readyState:4,seeking:false,paused:true,
    addEventListener(){},requestVideoFrameCallback(){},
    play(){this.paused=false;return Promise.resolve();},pause(){this.paused=true;},...overrides};
  const player={cfg:{fps:30},tocando:false,_redesenhar(){}};
  return {video,player,run:(time,rate=1)=>sync.call(player,video,time,rate)};
}
test('foreground corrects drift smaller than the old 250ms tolerance',()=>{
  const f=fixture(); assert.equal(f.run(1.1),false);assert.equal(f.video.currentTime,1.1);
});
test('foreground never paints while seeking, loading or warming',()=>{
  for(const state of [{seeking:true},{readyState:1},{_klipeWarming:true}]) {
    const f=fixture(state);assert.equal(f.run(2),false);assert.equal(f.video.currentTime,1);
  }
});
test('aligned foreground follows transport and global playback speed',()=>{
  const f=fixture();f.player.tocando=true;
  assert.equal(f.run(1,2),true);assert.equal(f.video.playbackRate,2);assert.equal(f.video.paused,false);
  f.player.tocando=false;assert.equal(f.run(1),true);assert.equal(f.video.paused,true);
});
test('playing layer starts its clock even when a seek is needed',()=>{
  const f=fixture();f.player.tocando=true;
  assert.equal(f.run(2),false);assert.equal(f.video.paused,false);
});
test('small playback drift converges with speed correction without seeking',()=>{
  const f=fixture();f.player.tocando=true;
  assert.equal(f.run(1.04),true);assert.equal(f.video.currentTime,1);
  assert.ok(f.video.playbackRate>1);
  assert.equal(f.run(.96),true);assert.ok(f.video.playbackRate<1);
});
test('outside foreground window cannot block drawing',()=>{
  const player={cfg:{brolls:[{alpha:true,foreground:true,startSec:0,endSec:1}]},t:1,
    _tocarAudios(){},gl:{clearColor(){throw new Error('drawing reached');}}};
  assert.throws(()=>scope.window.KlipePlayer.prototype.desenhar.call(player),/drawing reached/);
});
test('seek uses exact source time with foreground and preserves legacy offset otherwise',()=>{
  for(const foreground of [true,false]) {
    const p={cfg:{fps:30,brolls:[{alpha:true,foreground,startSec:0,endSec:10}]},duracao:10,tocando:true,
      video:{currentTime:0},desenhar(){},_redesenhar(){}};
    scope.window.KlipePlayer.prototype.seek.call(p,3);
    assert.equal(p.video.currentTime,foreground?3:3+1/30);
  }
});

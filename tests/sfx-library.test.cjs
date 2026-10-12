const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const vm=require('node:vm');
const root=path.resolve(__dirname,'..'),publicDir=path.join(root,'public');
const manifest=JSON.parse(fs.readFileSync(path.join(publicDir,'sfx/woven-library.json'),'utf8'));
test('bundled sound collection has verified intact WAV assets and license metadata',()=>{
 assert.equal(manifest.sounds.length,35);
 assert.equal(new Set(manifest.sounds.map(s=>s.src)).size,35);
 assert.ok(fs.existsSync(path.join(publicDir,'sfx/WOVEN-LICENSE.txt')));
 for(const s of manifest.sounds){
  assert.match(s.src,/^sfx\/[a-z_]+\/woven-[a-z0-9-]+\.wav$/);
  assert.equal(s.license,'CC0-1.0');assert.ok(s.durationSec>0);
  const data=fs.readFileSync(path.join(publicDir,s.src));
  assert.equal(data.toString('ascii',0,4),'RIFF');assert.equal(data.toString('ascii',8,12),'WAVE');
  assert.equal(crypto.createHash('sha256').update(data).digest('hex'),s.sha256);
 }
});
test('existing library scanner exposes every bundled sound in its category',()=>{
 const server=fs.readFileSync(path.join(root,'editor-server.js'),'utf8');
 const start=server.indexOf('function listSfx()'),end=server.indexOf('// List ambient/other audio files',start);
 const list=vm.runInNewContext(server.slice(start,end)+';listSfx()', {fs,path,PUBLIC_DIR:publicDir});
 for(const s of manifest.sounds)assert.ok(list.some(entry=>entry.src===s.src&&entry.category===s.category),s.src);
 assert.ok(!list.some(entry=>typeof entry==='object'&&/license|\.json/i.test(entry.src)));
});

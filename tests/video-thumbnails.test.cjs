const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync(require.resolve('../editor.html'), 'utf8');
const start = html.indexOf('  _ensureVideoThumbs(src, baseDurationSec) {');
const end = html.indexOf('\n  secToX(sec)', start);
assert.ok(start >= 0 && end > start, 'thumbnail method must be found');
const method = html.slice(start, end);

function fixture({drawFails = false, redrawFails = false} = {}) {
  const queue = new Map();
  let timerId = 0, created = 0, redraws = 0, captures = 0;
  const later = fn => { queue.set(++timerId, fn); return timerId; };
  const videos = [];
  const document = {createElement(type) {
    if (type === 'canvas') return {getContext: () => ({drawImage() {
      captures++; if (drawFails) throw new Error('bad frame');
    }})};
    assert.equal(type, 'video'); created++;
    const listeners = new Map();
    const v = {
      seeks: [], releases: 0, pauses: 0,
      addEventListener(event, fn) {if (!listeners.has(event)) listeners.set(event, new Set()); listeners.get(event).add(fn);},
      removeEventListener(event, fn) {listeners.get(event)?.delete(fn);},
      emit(event) {for (const fn of [...(listeners.get(event) || [])]) fn();},
      callbacks(event) {return [...(listeners.get(event) || [])];},
      set src(value) {this._src = value; if (value === '') {this.releases++; later(() => this.emit('error'));}},
      get src() {return this._src;},
      set currentTime(value) {this.time = value; this.seeks.push(value); later(() => this.emit('seeked'));},
      get currentTime() {return this.time || 0;},
      removeAttribute(name) {assert.equal(name, 'src'); delete this._src;},
      pause() {this.pauses++;},
      load() {this.releases++; later(() => this.emit('error'));},
    };
    videos.push(v); return v;
  }};
  const ensure = vm.runInNewContext('({' + method + '})._ensureVideoThumbs', {
    document, setTimeout: later, clearTimeout: id => queue.delete(id),
  });
  const renderer = {_videoThumbCache: new Map(), _videoThumbPending: new Set(), renderAll() {
    redraws++; if (redrawFails) throw new Error('renderer already gone');
  }};
  const run = (src='video.mp4', duration=10) => ensure.call(renderer, src, duration);
  const step = () => {const [id, fn] = queue.entries().next().value; queue.delete(id); fn();};
  const drain = () => {let budget=100; while (queue.size && budget--) step(); assert.equal(queue.size,0,'cleanup must not create an endless event loop');};
  return {run, step, drain, renderer, videos, queue, get redraws(){return redraws;}, get captures(){return captures;}, get created(){return created;}};
}

test('successful extraction releases the video and redraws only once', () => {
  const f=fixture(); f.run(); f.videos[0].emit('loadedmetadata'); f.drain();
  assert.equal(f.renderer._videoThumbCache.get('video.mp4').length,20);
  assert.equal(f.renderer._videoThumbPending.size,0);
  assert.equal(f.redraws,1); assert.equal(f.videos[0].releases,1);
  assert.equal(f.videos[0].callbacks('error').length,0);
  assert.equal(f.videos[0].src,undefined);
});

test('failed media and cleanup errors finish once without infinite redraw', () => {
  const f=fixture(); f.run(); f.videos[0].emit('error'); f.drain();
  assert.equal(f.renderer._videoThumbCache.get('video.mp4').length,0);
  assert.equal(f.renderer._videoThumbPending.size,0);
  assert.equal(f.redraws,1); assert.equal(f.videos[0].releases,1);
});

test('late seek, metadata and error callbacks cannot restart completed work', () => {
  const f=fixture(); f.run(); const v=f.videos[0];
  const late=[...v.callbacks('loadedmetadata'),...v.callbacks('seeked'),...v.callbacks('error')];
  v.emit('loadedmetadata'); f.step(); // capture first frame, with next seek queued
  v.emit('error');
  const count=f.captures, seeks=v.seeks.length;
  for (const fn of late) fn();
  f.drain();
  assert.equal(f.captures,count); assert.equal(v.seeks.length,seeks);
  assert.equal(f.redraws,1); assert.equal(v.releases,1);
});

test('pending and cached media do not start a second extraction', () => {
  const f=fixture(); f.run(); f.run(); assert.equal(f.created,1);
  f.videos[0].emit('loadedmetadata'); f.drain(); f.run();
  assert.equal(f.created,1); assert.equal(f.redraws,1);
});

test('different sources complete independently; bad frames and redraw failure still release resources', () => {
  const f=fixture({drawFails:true,redrawFails:true}); f.run('a.mp4'); f.run('b.mp4');
  for(const v of f.videos) v.emit('loadedmetadata'); f.drain();
  assert.equal(f.redraws,2); assert.equal(f.renderer._videoThumbPending.size,0);
  for(const v of f.videos) assert.equal(v.releases,1);
});

test('empty or too short source does not allocate video', () => {
  const f=fixture(); f.run('',10); f.run('short.mp4',.1); f.run('empty.mp4',0);
  assert.equal(f.created,0);
});

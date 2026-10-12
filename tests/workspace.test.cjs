const test = require('node:test');
const assert = require('node:assert/strict');
const {normalize, geometry} = require('../public/klipe-workspace.js');

test('invalid saved workspace values fall back to safe defaults', () => {
  assert.deepEqual(normalize(null), normalize({}));
  assert.deepEqual(normalize({left: NaN, right: '900', ratio: Infinity, mode: 'bad', library: null}), normalize({}));
});
test('saved widths and monitor ratio are bounded', () => {
  assert.equal(normalize({left: -1}).left, 220);
  assert.equal(normalize({right: 5000}).right, 480);
  assert.equal(normalize({ratio: 9}).ratio, .8);
});
test('desktop minimum size leaves room for the monitor and timeline', () => {
  const g = geometry({left: 440, right: 480, ratio: .8}, 960, 640);
  assert.ok(g.library && g.properties);
  assert.ok(960 - g.left - g.right >= 352);
  assert.ok(g.height <= 370);
});
test('review temporarily hides panels without changing preferences', () => {
  const prefs = {mode: 'review', library: true, properties: true, left: 330};
  const g = geometry(prefs, 1440, 1000);
  assert.equal(g.library, false); assert.equal(g.properties, false);
  assert.equal(prefs.library, true); assert.equal(g.left, 330);
  assert.equal(geometry({...prefs, mode: 'edit'}, 1440, 1000).library, true);
});
test('narrow screens do not squeeze the monitor between panels', () => {
  const g = geometry({}, 390, 844);
  assert.equal(g.library, false); assert.equal(g.properties, false);
});

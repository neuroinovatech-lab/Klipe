const test = require('node:test');
const assert = require('node:assert/strict');
const {normalize, reviewHeight} = require('../public/klipe-workspace.js');

test('invalid saved preferences use classic editing mode', () => {
  for (const value of [null, undefined, {}, {mode: 'bad'}, 'desktop']) {
    assert.deepEqual(normalize(value), {mode: 'edit', enabled: false});
  }
});
test('old desktop preferences cannot enable the removed layout', () => {
  const saved = {enabled: true, left: 330, ratio: 0.7, mode: 'review'};
  assert.deepEqual(normalize(saved), {mode: 'review', enabled: false});
  assert.equal(saved.enabled, true);
});
test('review keeps room for the timeline on desktop and small windows', () => {
  for (const height of [640, 900, 1080, 1600]) {
    assert.ok(reviewHeight(height) >= 180);
    assert.ok(reviewHeight(height) <= height - 270);
  }
  assert.equal(reviewHeight(300), 180);
});

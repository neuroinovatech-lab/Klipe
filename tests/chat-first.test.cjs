const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

test('editor does not load the internal assistant panel', () => {
  const html = fs.readFileSync(path.join(__dirname, '..', 'editor.html'), 'utf8');
  assert.doesNotMatch(html, /(?:src|href)=["'][^"']*klipe-assistant\.(?:js|css)/);
  assert.doesNotMatch(html, /id=["']assistant-panel["']/);
});

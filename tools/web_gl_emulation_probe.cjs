// Read-only probe of the VAO wrappers in an existing Emscripten-generated JS.
// This tests wrapper state with a mocked GL context, not browser rendering.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const input = process.argv[2];
if (!input) throw new Error('Usage: node tools/web_gl_emulation_probe.cjs <RangeRuntime.js>');
const source = fs.readFileSync(input, 'utf8').replace(/\r\n/g, '\n');
function between(start, end) {
  const a = source.indexOf(start);
  const b = source.indexOf(end, a + start.length);
  assert(a >= 0 && b > a, `Generated wrapper not found: ${start}`);
  return source.slice(a, b);
}
const bindWrapper = between('    var orig_glBindBuffer = _glBindBuffer;', '    var orig_glGetFloatv');
const pointerWrapper = between('    var orig_glVertexAttribPointer = _glVertexAttribPointer;', '\n  },\n  getAttributeFromCapability');
const vaoWrapper = between('var emulGlBindVertexArray =', 'var _glBindVertexArray =');
function run(unbindBeforeVao) {
  const context = {assert, errors: [], bindings: {}, GLEmulation: {
    currentVao: null, enabledVertexAttribArrays: {}, vaos: {1: {
      arrayBuffer: 0, elementArrayBuffer: 0, enabledVertexAttribArrays: {},
      vertexAttribPointers: {}, enabledClientStates: {}
    }}
  }, GLImmediate: {lastRenderer: null}};
  context.GLctx = {ARRAY_BUFFER: 34962, ELEMENT_ARRAY_BUFFER: 34963,
    disableVertexAttribArray() {},
    getParameter() { return context.bindings[34963] ? {name: context.bindings[34963]} : null; }
  };
  context._glBindBuffer = (target, buffer) => { context.bindings[target] = buffer; };
  context._glVertexAttribPointer = (index, size, type, normalized, stride, offset) => {
    if (!context.bindings[34962] && offset !== 0) context.errors.push('vertexAttribPointer: no ARRAY_BUFFER');
  };
  context._glEnableVertexAttribArray = () => {};
  context._glEnableClientState = () => {};
  vm.createContext(context);
  vm.runInContext(bindWrapper + pointerWrapper + vaoWrapper, context);
  // Same bind / pointer / unbind sequence as RAS_StorageVao's constructor.
  context._emscripten_glBindVertexArray(1);
  context._glBindBuffer(34962, 7);
  context._glBindBuffer(34963, 8);
  context._glVertexAttribPointer(1, 3, 5126, false, 0, 12);
  if (unbindBeforeVao) context._glBindBuffer(34962, 0);
  const recordedVbo = context.GLEmulation.vaos[1].arrayBuffer;
  context._emscripten_glBindVertexArray(0);
  if (!unbindBeforeVao) context._glBindBuffer(34962, 0);
  context._emscripten_glBindVertexArray(1);
  return {recordedVbo, errors: context.errors};
}
const existing = run(true);
const control = run(false);
assert.equal(existing.recordedVbo, 0);
assert.deepEqual(existing.errors, ['vertexAttribPointer: no ARRAY_BUFFER']);
assert.equal(control.recordedVbo, 7);
assert.deepEqual(control.errors, []);
console.log(JSON.stringify({existing, control, result: 'PASS: wrapper-state issue reproduced; browser validation still required'}, null, 2));

#!/usr/bin/env node
/**
 * G3 contract validator (JavaScript side). Zero dependencies (recorded choice in
 * the G3 ledger): a hand-rolled subset validator implementing EXACTLY the same
 * rule semantics as tests/contracts/validate_contracts.py's fallback (type,
 * enum, const, pattern, minLength, minimum, minItems, required,
 * additionalProperties:false, nested properties). The `jsonschema` library is
 * intentionally NOT added — G3 forbids new JS deps; full ajv adoption is a
 * documented future option if schema features grow beyond the subset.
 *
 * Enforces the same structural criteria as the Python side (C3.4/C3.5/C3.7).
 * Exit 0 = all fixtures + structural checks pass.
 */
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const SCHEMAS = path.join(ROOT, 'contracts', 'schemas');
const FIX = path.join(ROOT, 'tests', 'contracts', 'fixtures');
const TYPE_TEST = {
  object: v => v !== null && typeof v === 'object' && !Array.isArray(v),
  array: v => Array.isArray(v),
  string: v => typeof v === 'string',
  integer: v => typeof v === 'number' && Number.isInteger(v),
  boolean: v => typeof v === 'boolean',
  null: v => v === null,
};

function check(node, schema, path_, errors) {
  if (schema.type) {
    const types = Array.isArray(schema.type) ? schema.type : [schema.type];
    if (!types.some(t => TYPE_TEST[t](node))) {
      errors.push(`${path_}: type ${schema.type} vs ${node === null ? 'null' : typeof node}`);
      return;
    }
  }
  if ('const' in schema) {
    if (JSON.stringify(node) !== JSON.stringify(schema.const)) {
      errors.push(`${path_}: const ${JSON.stringify(schema.const)} vs ${JSON.stringify(node)}`);
      return;
    }
  }
  if (schema.enum && !schema.enum.includes(node)) {
    errors.push(`${path_}: ${JSON.stringify(node)} not in enum`);
    return;
  }
  if (typeof node === 'string') {
    if (schema.pattern && !new RegExp(schema.pattern).test(node)) {
      errors.push(`${path_}: pattern ${schema.pattern} vs '${node}'`);
      return;
    }
    if (schema.minLength !== undefined && node.length < schema.minLength) {
      errors.push(`${path_}: minLength ${schema.minLength}`);
      return;
    }
  }
  if (typeof node === 'number' && schema.minimum !== undefined && node < schema.minimum) {
    errors.push(`${path_}: minimum ${schema.minimum}`);
    return;
  }
  if (Array.isArray(node)) {
    if (schema.minItems !== undefined && node.length < schema.minItems) {
      errors.push(`${path_}: minItems ${schema.minItems}`);
      return;
    }
    if (schema.items) node.forEach((item, i) => check(item, schema.items, `${path_}[${i}]`, errors));
  }
  if (TYPE_TEST.object(node)) {
    const props = schema.properties || {};
    for (const r of schema.required || []) {
      if (!(r in node)) errors.push(`${path_}: missing required ${r}`);
    }
    if (schema.additionalProperties === false) {
      for (const k of Object.keys(node)) {
        if (!(k in props)) errors.push(`${path_}: additional property ${k}`);
      }
    }
    for (const [k, v] of Object.entries(node)) {
      if (props[k]) check(v, props[k], `${path_}.${k}`, errors);
    }
  }
}

const SECRET_KEY_RX = /secret|password|api[_-]?key|private[_-]?key|token[_-]?value|bearer|credential[_-]?value|client[_-]?secret/i;

function main() {
  const failures = [];
  let passed = 0;
  const expectations = [];
  for (const f of fs.readdirSync(path.join(FIX, 'valid')).sort()) {
    const n = f.replace(/\.valid\.json$/, '');
    expectations.push([path.join(FIX, 'valid', f), path.join(SCHEMAS, `${n}.schema.json`), true]);
  }
  for (const f of fs.readdirSync(path.join(FIX, 'invalid')).sort()) {
    if (!f.endsWith('.invalid.json')) continue;
    const schemaName = f.split('.')[0];
    expectations.push([path.join(FIX, 'invalid', f), path.join(SCHEMAS, `${schemaName}.schema.json`), false]);
  }

  for (const [fpath, spath, shouldPass] of expectations) {
    const fx = JSON.parse(fs.readFileSync(fpath, 'utf8'));
    const sc = JSON.parse(fs.readFileSync(spath, 'utf8'));
    const errors = [];
    check(fx, sc, '$', errors);
    if (shouldPass && errors.length) failures.push(`FAIL accept ${path.basename(fpath)}: ${errors.join('; ')}`);
    else if (!shouldPass && !errors.length) failures.push(`FAIL reject ${path.basename(fpath)}: accepted, expected rejection`);
    else passed += 1;
  }

  // C3.4 + C3.5 structural criteria (mirror of the Python checks)
  const ai = JSON.parse(fs.readFileSync(path.join(SCHEMAS, 'AgentIdentity.schema.json'), 'utf8'));
  const sep = ['employee_id', 'sprite_id', 'native_harness_id', 'harness_instance_id',
               'session_id', 'current_task_id', 'operational_scope', 'authorization_context'];
  if (new Set(sep).size !== 8 || !sep.every(f => ai.required.includes(f))) {
    failures.push('FAIL C3.4 AgentIdentity separation fields');
  } else passed += 1;
  const vbProps = (ai.properties.verified_binding && ai.properties.verified_binding.properties) || {};
  if (ai.required.includes('asserted_id') && ai.required.includes('verified_binding') && !('asserted_id' in vbProps)) {
    passed += 1;
  } else failures.push('FAIL C3.5 asserted_id/verified_binding distinction');

  // C3.7 value-bearing key scan
  const offenders = [];
  for (const base of [SCHEMAS, path.join(FIX, 'valid')]) {
    for (const f of fs.readdirSync(base).sort()) {
      const text = fs.readFileSync(path.join(base, f), 'utf8');
      const m = text.match(SECRET_KEY_RX);
      if (m) offenders.push(`${f}:${m[0]}`);
    }
  }
  if (offenders.length) failures.push(`FAIL C3.7 value-bearing keys: ${offenders.slice(0, 8).join(', ')}`);
  else passed += 1;

  console.log('JS_VALIDATOR=subset');
  console.log(`node: ${passed} checks passed, ${failures.length} failed`);
  for (const f of failures) console.log('  ' + f);
  process.exit(failures.length ? 1 : 0);
}

main();

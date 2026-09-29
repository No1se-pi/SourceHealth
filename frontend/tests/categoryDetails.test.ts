import assert from 'node:assert/strict';
import test from 'node:test';
import { hasDetectedCiConfiguration, localSastStatus, type PresentationCheck } from '../src/components/common/categoryDetailsModel.ts';

const check = (overrides: Partial<PresentationCheck> = {}): PresentationCheck => ({
  category: 'cicd', source: 'sourcecraft', availability: 'source_unavailable',
  metrics: {}, findings: [], ...overrides,
});

test('CI source unavailable with confirmed config shows detected state without inventing a score', () => {
  const score = null;
  assert.equal(hasDetectedCiConfiguration({ cicd: check({ metrics: { configured: true } }) }, score), true);
  assert.equal(score, null);
});

test('CI config is not claimed without canonical confirmation', () => {
  assert.equal(hasDetectedCiConfiguration({ cicd: check({ metrics: { configured: false } }) }, null), false);
  assert.equal(hasDetectedCiConfiguration({ cicd: check() }, null), false);
});

test('available local SAST exposes three findings', () => {
  const status = localSastStatus({ sast: check({ category: 'code_health', source: 'sourcehealth_local',
    availability: 'available', findings: [{}, {}, {}] }) });
  assert.equal(status?.label, 'Local SAST · выполнен · 3 находки');
});

test('partial local SAST labels confirmed findings explicitly', () => {
  const status = localSastStatus({ sast: check({ category: 'code_health', source: 'sourcehealth_local',
    availability: 'partial', findings: Array.from({ length: 15 }, () => ({})) }) });
  assert.equal(status?.label, 'Local SAST · частично · 15 подтверждённых находок');
});

test('absent or no-data local SAST produces no completed status', () => {
  assert.equal(localSastStatus(undefined), null);
  assert.equal(localSastStatus({ sast: check({ category: 'code_health', source: 'sourcehealth_local',
    availability: 'no_data' }) }), null);
});

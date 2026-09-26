import React from 'react';
import type { components } from '../api/generated';
import { CompareGrid } from '../components/compare/CompareGrid';

type CompareResponse = components['schemas']['CompareResponse'];

export const ComparePage: React.FC<{ comparison: CompareResponse }> = ({ comparison }) => (
  <main>
    <h1>Сравнение репозиториев</h1>
    <p>Health, покрытие и шесть категорий из уже сохранённых результатов.</p>
    <CompareGrid comparison={comparison} />
  </main>
);

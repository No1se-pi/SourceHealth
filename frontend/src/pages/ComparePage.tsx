import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { components } from '../api/generated';
import { api } from '../api/client';
import { CompareGrid } from '../components/compare/CompareGrid';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';
import { usePageTitle } from '../utils/usePageTitle';

type CompareResponse = components['schemas']['CompareResponse'];

interface ComparePageProps {
  comparison?: CompareResponse;
}

export const ComparePage: React.FC<ComparePageProps> = ({ comparison: propComparison }) => {
  usePageTitle('Сравнение проектов');
  const [searchParams] = useSearchParams();
  const [data, setData] = useState<CompareResponse | undefined>(propComparison);
  const [loading, setLoading] = useState<boolean>(!propComparison);
  const [error, setError] = useState<unknown>();

  useEffect(() => {
    if (propComparison) {
      setData(propComparison);
      setLoading(false);
      return;
    }

    const ids = searchParams.getAll('repository_id');
    const reposParam = searchParams.get('repos');
    const allIds = ids.length > 0 ? ids : (reposParam ? reposParam.split(',').map((s) => s.trim()).filter(Boolean) : []);

    if (allIds.length < 2) {
      setError(new Error('Выберите от 2 до 4 проектов для сравнения'));
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(undefined);
    api
      .compare(allIds.slice(0, 4))
      .then((res) => {
        setData(res);
        setLoading(false);
      })
      .catch((err) => {
        setError(err);
        setLoading(false);
      });
  }, [propComparison, searchParams]);

  return (
    <main className="container compare-page">
      <div className="compare-page__heading"><span>СРАВНЕНИЕ</span><h1>Репозитории рядом</h1></div>
      <p className="compare-page__lead">
        Health, покрытие и шесть категорий из уже сохранённых результатов.
      </p>

      {loading && <LoadingState message="Загрузка данных сравнения..." />}
      {Boolean(error) && (
        <ErrorState
          error={error}
          onRetry={() => {
            const ids = searchParams.getAll('repository_id');
            if (ids.length >= 2) {
              setLoading(true);
              api.compare(ids).then(setData).catch(setError).finally(() => setLoading(false));
            }
          }}
        />
      )}
      {!loading && !error && data && <CompareGrid comparison={data} />}
    </main>
  );
};

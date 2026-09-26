import { useEffect } from 'react';

/**
 * Sets document.title formatted with the SourceHealth brand prefix.
 */
export function usePageTitle(title?: string): void {
  useEffect(() => {
    if (title) {
      document.title = `${title} · SourceHealth`;
    } else {
      document.title = 'SourceHealth · Анализ здоровья репозиториев';
    }
  }, [title]);
}

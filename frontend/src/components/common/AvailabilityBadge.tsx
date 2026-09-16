import React from 'react';
import type { DataAvailability } from '../../api/client';
import { Badge, type BadgeVariant } from './Badge';

interface AvailabilityConfig {
  label: string;
  variant: BadgeVariant;
  description: string;
}

const AVAILABILITY_CONFIG: Record<DataAvailability, AvailabilityConfig> = {
  available: {
    label: 'Данные есть',
    variant: 'success',
    description: 'Факты успешно собраны и подтверждены',
  },
  partial: {
    label: 'Частично',
    variant: 'warning',
    description: 'Часть источников фактов недоступна или неполна',
  },
  no_data: {
    label: 'Нет данных',
    variant: 'neutral',
    description: 'Данные по этой категории отсутствуют в репозитории',
  },
  source_unavailable: {
    label: 'Источник недоступен',
    variant: 'warning',
    description: 'Внешний сервис или API платформы временно недоступны',
  },
  not_configured: {
    label: 'Не настроено',
    variant: 'neutral',
    description: 'Инструмент (например CI/CD или AppSec) не подключён к репозиторию',
  },
  not_applicable: {
    label: 'Не применимо',
    variant: 'neutral',
    description: 'Проверка не актуальна для данного типа проекта',
  },
  error: {
    label: 'Ошибка сбора',
    variant: 'danger',
    description: 'При получении фактов произошёл сбой анализатора',
  },
};

interface AvailabilityBadgeProps {
  availability: DataAvailability;
  className?: string;
  showTooltip?: boolean;
}

export const AvailabilityBadge: React.FC<AvailabilityBadgeProps> = ({
  availability,
  className = '',
  showTooltip = true,
}) => {
  const config = AVAILABILITY_CONFIG[availability] ?? {
    label: availability,
    variant: 'neutral' as BadgeVariant,
    description: '',
  };

  return (
    <Badge
      variant={config.variant}
      className={className}
      style={{ cursor: showTooltip ? 'help' : 'default' }}
    >
      <span title={showTooltip ? config.description : undefined}>
        {config.label}
      </span>
    </Badge>
  );
};

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
    label: 'Источник доступен',
    variant: 'success',
    description: 'Источник успешно собран',
  },
  partial: {
    label: 'Частично',
    variant: 'warning',
    description: 'Получена только часть необходимых данных',
  },
  no_data: {
    label: 'Недостаточно данных',
    variant: 'neutral',
    description: 'Недостаточно доступных данных от источника для этой проверки',
  },
  source_unavailable: {
    label: 'Источник недоступен',
    variant: 'warning',
    description: 'Источник временно недоступен',
  },
  not_configured: {
    label: 'Не настроено',
    variant: 'neutral',
    description: 'Источник или инструмент не настроен',
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

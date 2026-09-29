type ReportExportMenuProps = { analysisId: string };

const formats = [
  { extension: 'md', label: 'Markdown (.md)' },
  { extension: 'pdf', label: 'PDF (.pdf)' },
  { extension: 'docx', label: 'Word (.docx)' },
] as const;

export const ReportExportMenu = ({ analysisId }: ReportExportMenuProps) => (
  <details className="report-export">
    <summary className="report-export__trigger">↓ Скачать отчёт</summary>
    <div className="report-export__menu" role="menu" aria-label="Формат отчёта">
      {formats.map((format) => (
        <a
          key={format.extension}
          href={`/api/v1/analyses/${encodeURIComponent(analysisId)}/report.${format.extension}`}
          download
          role="menuitem"
          className="report-export__option"
        >
          {format.label}
        </a>
      ))}
    </div>
  </details>
);

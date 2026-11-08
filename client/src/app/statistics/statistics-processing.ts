import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import {
  chunkConfigurationDescription,
  chunkConfigurationLabel,
  chunkStatusLabel,
} from './chunk-statistics.presenter';
import {
  ChunkConfigurationDescriptor,
  DatasetChunkStatistics,
  PageChunkStatistics,
  PageStatistics,
  StatisticsResponse,
} from './statistics.models';
import { StatisticsStore } from './statistics.store';

type ChunkStatusFilter = 'all' | 'issues' | 'stale' | PageChunkStatistics['status'];

interface ProcessingIssueRow {
  page: string;
  chunkConfigId: string;
  code: string;
  severity: 'warning' | 'error';
  message: string;
  lineNumber: number | null;
  affectedRecordCount: number;
}

@Component({
  selector: 'app-statistics-processing',
  imports: [DatePipe, DecimalPipe, FormsModule],
  templateUrl: './statistics-processing.html',
})
export class StatisticsProcessing implements OnInit {
  readonly store = inject(StatisticsStore);
  readonly statistics = this.store.statistics;
  readonly loading = this.store.loading;
  readonly error = this.store.error;

  readonly selectedConfigId = signal<string | null>(null);
  readonly statusFilter = signal<ChunkStatusFilter>('all');

  readonly filteredPages = computed(() => {
    const data = this.statistics();
    const status = this.statusFilter();
    const configId = this.selectedConfigId();
    if (!data || status === 'all') {
      return data?.pages ?? [];
    }
    return data.pages.filter((page) => {
      const statistics = configId
        ? [this.pageChunkStatistics(page, configId)]
        : page.chunk_statistics;
      if (status === 'issues') {
        return statistics.some((item) => item?.validation_issues.length);
      }
      if (status === 'stale') {
        return statistics.some((item) => item?.freshness_status === 'stale');
      }
      return statistics.some((item) => item?.status === status);
    });
  });
  readonly issueRows = computed<ProcessingIssueRow[]>(() => {
    const data = this.statistics();
    const selectedConfigId = this.selectedConfigId();
    if (!data) {
      return [];
    }
    return data.pages.flatMap((page) =>
      page.chunk_statistics
        .filter(
          (statistics) => !selectedConfigId || statistics.chunk_config_id === selectedConfigId,
        )
        .flatMap((statistics) =>
          statistics.validation_issues.map((issue) => ({
            page: page.page,
            chunkConfigId: statistics.chunk_config_id,
            code: issue.code,
            severity: issue.severity,
            message: issue.message,
            lineNumber: issue.line_number,
            affectedRecordCount: issue.affected_record_count,
          })),
        ),
    );
  });

  ngOnInit(): void {
    void this.store.ensureLoaded().then(() => this.ensureSelection());
  }

  async load(): Promise<void> {
    await this.store.refresh();
    this.ensureSelection();
  }

  selectConfiguration(configId: string): void {
    this.selectedConfigId.set(configId);
  }

  showAllConfigurations(): void {
    this.selectedConfigId.set(null);
  }

  configurationLabel(configuration: ChunkConfigurationDescriptor): string {
    return chunkConfigurationLabel(configuration);
  }

  configurationDescription(configuration: ChunkConfigurationDescriptor): string {
    return chunkConfigurationDescription(configuration);
  }

  statusLabel(status: PageChunkStatistics['status']): string {
    return chunkStatusLabel(status);
  }

  summaryFor(data: StatisticsResponse, configId: string): DatasetChunkStatistics | undefined {
    return data.summary.chunk_statistics.find(
      (statistics) => statistics.chunk_config_id === configId,
    );
  }

  pageChunkStatistics(page: PageStatistics, configId: string): PageChunkStatistics | undefined {
    return page.chunk_statistics.find((statistics) => statistics.chunk_config_id === configId);
  }

  downloadStatusLabel(page: PageStatistics): string {
    return {
      available: 'Letöltve',
      missing: 'Hiányzik',
      invalid: 'Hibás',
    }[page.download_status];
  }

  processingStatusLabel(page: PageStatistics): string {
    return {
      processed: 'Feldolgozva',
      processed_empty: 'Üres',
      not_processed: 'Nincs feldolgozva',
      invalid: 'Hibás',
    }[page.processing_status];
  }

  coverage(summary: DatasetChunkStatistics): number {
    const expected = summary.document_count + summary.missing_document_count;
    return expected === 0 ? 0 : (summary.document_count / expected) * 100;
  }

  issueSummary(statistics: PageChunkStatistics): string | null {
    const issue = statistics.validation_issues[0];
    if (!issue) {
      return null;
    }
    const additionalCount = statistics.validation_issues.length - 1;
    return additionalCount > 0 ? `${issue.message} +${additionalCount} további` : issue.message;
  }

  issueTypeLabel(code: string): string {
    return (
      {
        missing_file: 'Hiányzó chunkfájl',
        unreadable_file: 'Nem olvasható fájl',
        invalid_record: 'Érvénytelen rekord',
        configuration_mismatch: 'Eltérő konfiguráció',
        source_page_mismatch: 'Eltérő forrásoldal',
        duplicate_chunk_id: 'Duplikált chunkazonosító',
        orphan_document: 'Árva dokumentumhivatkozás',
        strategy_mismatch: 'Eltérő stratégia',
        non_contiguous_chunk_index: 'Nem folytonos chunkindex',
        invalid_token_span_sequence: 'Hibás tokentartomány',
        token_limit_exceeded: 'Tokenlimit-túllépés',
        stale_chunk_file: 'Elavult chunkfájl',
      }[code] ?? code
    );
  }

  issueSeverityLabel(severity: ProcessingIssueRow['severity']): string {
    return severity === 'error' ? 'Hiba' : 'Figyelmeztetés';
  }

  private ensureSelection(): void {
    const configurations = this.statistics()?.chunk_configurations ?? [];
    if (
      !this.selectedConfigId() ||
      !configurations.some(
        (configuration) => configuration.chunk_config_id === this.selectedConfigId(),
      )
    ) {
      this.selectedConfigId.set(configurations[0]?.chunk_config_id ?? null);
    }
  }
}

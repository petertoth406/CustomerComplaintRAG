import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, HostListener, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import {
  chunkConfigurationLabel,
  chunkStatusLabel,
} from './chunk-statistics.presenter';
import { LengthDistributionTable } from './length-distribution-table';
import {
  ChunkConfigurationDescriptor,
  DatasetSummary,
  PageChunkStatistics,
  PageStatistics,
} from './statistics.models';
import { StatisticsStore } from './statistics.store';

@Component({
  selector: 'app-statistics-pages',
  imports: [DatePipe, DecimalPipe, FormsModule, LengthDistributionTable],
  templateUrl: './statistics-pages.html',
})
export class StatisticsPages implements OnInit {
  readonly store = inject(StatisticsStore);

  readonly statistics = this.store.statistics;
  readonly selectedPage = signal<PageStatistics | null>(null);
  readonly loading = this.store.loading;
  readonly error = this.store.error;
  readonly includeTokens = this.store.includeTokens;

  ngOnInit(): void {
    void this.store.ensureLoaded();
  }

  async load(): Promise<void> {
    this.selectedPage.set(null);
    await this.store.refresh();
  }

  openPage(page: PageStatistics): void {
    this.selectedPage.set(page);
  }

  closeModal(): void {
    this.selectedPage.set(null);
  }

  @HostListener('document:keydown.escape')
  closeModalOnEscape(): void {
    this.closeModal();
  }

  answerRate(page: PageStatistics): number {
    return this.calculateAnswerRate(page.content);
  }

  summaryAnswerRate(summary: DatasetSummary): number {
    return this.calculateAnswerRate(summary.content);
  }

  private calculateAnswerRate(content: PageStatistics['content']): number {
    const complaints = content.complaint_document_count ?? 0;
    const answered = content.answered_document_count ?? 0;
    return complaints === 0 ? 0 : (answered / complaints) * 100;
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

  chunkConfiguration(
    configId: string,
  ): ChunkConfigurationDescriptor | undefined {
    return this.statistics()?.chunk_configurations.find(
      (configuration) => configuration.chunk_config_id === configId,
    );
  }

  chunkConfigurationLabel(configuration: ChunkConfigurationDescriptor): string {
    return chunkConfigurationLabel(configuration);
  }

  chunkStatusLabel(status: PageChunkStatistics['status']): string {
    return chunkStatusLabel(status);
  }

}

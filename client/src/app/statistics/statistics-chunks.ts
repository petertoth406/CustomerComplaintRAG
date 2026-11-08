import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import {
  chunkConfigurationDescription,
  chunkConfigurationLabel,
} from './chunk-statistics.presenter';
import {
  ChunkConfigurationDescriptor,
  DatasetChunkStatistics,
  PageChunkStatistics,
  StatisticsResponse,
} from './statistics.models';
import { HistogramChart } from './histogram-chart';
import { StatisticsStore } from './statistics.store';

type DistributionScope = 'dataset' | 'page';

@Component({
  selector: 'app-statistics-chunks',
  imports: [DatePipe, DecimalPipe, FormsModule, HistogramChart],
  templateUrl: './statistics-chunks.html',
})
export class StatisticsChunks implements OnInit {
  readonly store = inject(StatisticsStore);
  readonly statistics = this.store.statistics;
  readonly loading = this.store.loading;
  readonly error = this.store.error;

  readonly selectedConfigId = signal<string | null>(null);
  readonly distributionScope = signal<DistributionScope>('dataset');
  readonly selectedPageName = signal<string | null>(null);
  readonly selectedSummary = computed(() => {
    const data = this.statistics();
    const configId = this.selectedConfigId();
    if (!data || !configId) {
      return undefined;
    }
    return this.summaryFor(data, configId);
  });
  readonly selectedConfiguration = computed(() => {
    const data = this.statistics();
    const configId = this.selectedConfigId();
    return data?.chunk_configurations.find(
      (configuration) => configuration.chunk_config_id === configId,
    );
  });
  readonly availablePages = computed(() => {
    const data = this.statistics();
    const configId = this.selectedConfigId();
    if (!data || !configId) {
      return [];
    }
    return data.pages.filter(
      (page) => (this.pageChunkStatistics(page, configId)?.chunk_count ?? 0) > 0,
    );
  });
  readonly selectedPage = computed(() =>
    this.availablePages().find((page) => page.page === this.selectedPageName()),
  );
  readonly selectedDistribution = computed<
    DatasetChunkStatistics | PageChunkStatistics | undefined
  >(() => {
    if (this.distributionScope() === 'dataset') {
      return this.selectedSummary();
    }
    const page = this.selectedPage();
    const configId = this.selectedConfigId();
    return page && configId ? this.pageChunkStatistics(page, configId) : undefined;
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
    this.ensurePageSelection();
  }

  selectScope(scope: DistributionScope): void {
    this.distributionScope.set(scope);
    this.ensurePageSelection();
  }

  selectPage(pageName: string): void {
    this.selectedPageName.set(pageName);
  }

  configurationLabel(configuration: ChunkConfigurationDescriptor): string {
    return chunkConfigurationLabel(configuration);
  }

  configurationDescription(configuration: ChunkConfigurationDescriptor): string {
    return chunkConfigurationDescription(configuration);
  }

  summaryFor(data: StatisticsResponse, configId: string): DatasetChunkStatistics | undefined {
    return data.summary.chunk_statistics.find(
      (statistics) => statistics.chunk_config_id === configId,
    );
  }

  pageChunkStatistics(
    page: StatisticsResponse['pages'][number],
    configId: string,
  ): PageChunkStatistics | undefined {
    return page.chunk_statistics.find((statistics) => statistics.chunk_config_id === configId);
  }

  distributionTitle(): string {
    return this.distributionScope() === 'dataset'
      ? 'Teljes állomány'
      : (this.selectedPage()?.page ?? 'Nincs kiválasztott oldal');
  }

  singleChunkRate(summary: DatasetChunkStatistics): number {
    return this.documentRatio(summary.single_chunk_document_count, summary);
  }

  multiChunkRate(summary: DatasetChunkStatistics): number {
    return this.documentRatio(summary.multi_chunk_document_count, summary);
  }

  private documentRatio(documentCount: number, summary: DatasetChunkStatistics): number {
    const coveredCount = summary.single_chunk_document_count + summary.multi_chunk_document_count;
    return coveredCount === 0 ? 0 : (documentCount / coveredCount) * 100;
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
    this.ensurePageSelection();
  }

  private ensurePageSelection(): void {
    const pages = this.availablePages();
    if (!pages.some((page) => page.page === this.selectedPageName())) {
      this.selectedPageName.set(pages[0]?.page ?? null);
    }
  }
}

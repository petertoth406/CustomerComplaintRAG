import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, HostListener, computed, inject, OnInit, signal } from '@angular/core';
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

type ChunkStatusFilter = 'all' | PageChunkStatistics['status'];

@Component({
  selector: 'app-statistics-chunks',
  imports: [DatePipe, DecimalPipe, FormsModule],
  templateUrl: './statistics-chunks.html',
})
export class StatisticsChunks implements OnInit {
  readonly store = inject(StatisticsStore);
  readonly statistics = this.store.statistics;
  readonly loading = this.store.loading;
  readonly error = this.store.error;
  readonly includeTokens = this.store.includeTokens;

  readonly selectedConfigId = signal<string | null>(null);
  readonly statusFilter = signal<ChunkStatusFilter>('all');
  readonly selectedPage = signal<PageStatistics | null>(null);
  readonly modalConfigId = signal<string | null>(null);

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
        : (page.chunk_statistics ?? []);
      return statistics.some((item) => item?.status === status);
    });
  });

  ngOnInit(): void {
    void this.store.ensureLoaded().then(() => this.ensureSelection());
  }

  async load(): Promise<void> {
    this.closeModal();
    await this.store.refresh();
    this.ensureSelection();
  }

  selectConfiguration(configId: string): void {
    this.selectedConfigId.set(configId);
  }

  showAllConfigurations(): void {
    this.selectedConfigId.set(null);
  }

  openPage(page: PageStatistics, configId?: string): void {
    const fallback = this.selectedConfigId()
      ?? this.statistics()?.chunk_configurations[0]?.chunk_config_id
      ?? null;
    this.modalConfigId.set(configId ?? fallback);
    this.selectedPage.set(page);
  }

  closeModal(): void {
    this.selectedPage.set(null);
  }

  @HostListener('document:keydown.escape')
  closeModalOnEscape(): void {
    this.closeModal();
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

  summaryFor(
    data: StatisticsResponse,
    configId: string,
  ): DatasetChunkStatistics | undefined {
    return data.summary.chunk_statistics?.find(
      (statistics) => statistics.chunk_config_id === configId,
    );
  }

  pageChunkStatistics(
    page: PageStatistics,
    configId: string,
  ): PageChunkStatistics | undefined {
    return page.chunk_statistics?.find(
      (statistics) => statistics.chunk_config_id === configId,
    );
  }

  modalConfiguration(
    data: StatisticsResponse,
  ): ChunkConfigurationDescriptor | undefined {
    return data.chunk_configurations.find(
      (configuration) => configuration.chunk_config_id === this.modalConfigId(),
    );
  }

  hasChunkStatistics(data: StatisticsResponse): boolean {
    return Array.isArray(data.chunk_configurations)
      && data.chunk_configurations.length > 0;
  }

  private ensureSelection(): void {
    const configurations = this.statistics()?.chunk_configurations ?? [];
    if (
      this.selectedConfigId()
      && !configurations.some(
        (configuration) => configuration.chunk_config_id === this.selectedConfigId(),
      )
    ) {
      this.selectedConfigId.set(null);
    }
  }
}

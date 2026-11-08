import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, inject, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { LengthDistributionTable } from './length-distribution-table';
import { StatisticsResponse } from './statistics.models';
import { StatisticsStore } from './statistics.store';

@Component({
  selector: 'app-statistics-overview',
  imports: [DatePipe, DecimalPipe, FormsModule, LengthDistributionTable],
  templateUrl: './statistics-overview.html',
})
export class StatisticsOverview implements OnInit {
  readonly store = inject(StatisticsStore);

  readonly statistics = this.store.statistics;
  readonly loading = this.store.loading;
  readonly error = this.store.error;
  readonly includeTokens = this.store.includeTokens;

  ngOnInit(): void {
    void this.store.ensureLoaded();
  }

  async load(): Promise<void> {
    await this.store.refresh();
  }

  answerRate(statistics: StatisticsResponse): number {
    const complaints = statistics.summary.content.complaint_document_count ?? 0;
    const answered = statistics.summary.content.answered_document_count ?? 0;
    return complaints === 0 ? 0 : (answered / complaints) * 100;
  }

}

import { DecimalPipe } from '@angular/common';
import { Component, input } from '@angular/core';

import {
  LengthDistribution,
  TextLengthStatistics,
} from './statistics.models';

interface DistributionRow {
  label: string;
  distribution: LengthDistribution;
}

@Component({
  selector: 'app-length-distribution-table',
  imports: [DecimalPipe],
  templateUrl: './length-distribution-table.html',
})
export class LengthDistributionTable {
  readonly title = input.required<string>();
  readonly description = input.required<string>();
  readonly statistics = input.required<TextLengthStatistics>();
  readonly includeTokens = input(false);

  rows(): DistributionRow[] {
    const statistics = this.statistics();
    const rows: DistributionRow[] = [
      { label: 'Karakter', distribution: statistics.characters },
      { label: 'Szó', distribution: statistics.words },
    ];

    if (this.includeTokens() && statistics.tokens) {
      rows.push({ label: 'Token', distribution: statistics.tokens });
    }
    return rows;
  }
}

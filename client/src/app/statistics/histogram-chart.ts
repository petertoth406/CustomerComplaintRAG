import { DecimalPipe } from '@angular/common';
import { Component, computed, input } from '@angular/core';

import { HistogramBucket } from './statistics.models';

@Component({
  selector: 'app-histogram-chart',
  imports: [DecimalPipe],
  templateUrl: './histogram-chart.html',
})
export class HistogramChart {
  readonly title = input.required<string>();
  readonly description = input.required<string>();
  readonly buckets = input.required<HistogramBucket[]>();
  readonly unit = input.required<string>();

  readonly maximumCount = computed(() =>
    Math.max(0, ...this.buckets().map((bucket) => bucket.count)),
  );

  barWidth(count: number): number {
    const maximum = this.maximumCount();
    return maximum === 0 ? 0 : (count / maximum) * 100;
  }
}

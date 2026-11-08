import { HttpErrorResponse } from '@angular/common/http';
import { inject, Injectable, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { StatisticsApiService } from './statistics-api.service';
import { StatisticsResponse } from './statistics.models';

@Injectable({ providedIn: 'root' })
export class StatisticsStore {
  private readonly api = inject(StatisticsApiService);
  private pendingRequest?: Promise<void>;

  readonly statistics = signal<StatisticsResponse | null>(null);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly includeTokens = signal(false);

  ensureLoaded(): Promise<void> {
    if (this.pendingRequest) {
      return this.pendingRequest;
    }
    return this.statistics() ? Promise.resolve() : this.refresh();
  }

  refresh(): Promise<void> {
    this.pendingRequest ??= this.fetch().finally(() => {
      this.pendingRequest = undefined;
      this.loading.set(false);
    });
    return this.pendingRequest;
  }

  private async fetch(): Promise<void> {
    this.loading.set(true);
    this.error.set(null);
    try {
      this.statistics.set(
        await firstValueFrom(this.api.load(this.includeTokens())),
      );
    } catch (error: unknown) {
      this.error.set(this.errorMessage(error));
    }
  }

  private errorMessage(error: unknown): string {
    if (error instanceof HttpErrorResponse) {
      return error.error?.detail ?? `A statisztika nem tölthető be (HTTP ${error.status}).`;
    }
    return 'A statisztika betöltése váratlan hibával leállt.';
  }
}

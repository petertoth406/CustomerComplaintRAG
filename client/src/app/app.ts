import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';

type RequestKey =
  | 'status'
  | 'statistics'
  | 'download'
  | 'process'
  | 'run'
  | 'embeddings'
  | 'search';

interface ApiResponse {
  status: number;
  ok: boolean;
  body: string;
}

interface PageSelection {
  pageId: number | null;
  startPage: number | null;
  endPage: number | null;
}

@Component({
  selector: 'app-root',
  imports: [FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  private readonly http = inject(HttpClient);

  readonly responses = signal<Partial<Record<RequestKey, ApiResponse>>>({});
  readonly loading = signal<Partial<Record<RequestKey, boolean>>>({});

  pageSelection: PageSelection = {
    pageId: null,
    startPage: null,
    endPage: null,
  };
  timestamp = false;
  saveBlocks = false;
  query = '';

  getStatus(): void {
    void this.send('status', 'GET', '/api/v1/status');
  }

  getStatistics(): void {
    void this.send('statistics', 'GET', '/api/v1/statistics');
  }

  download(): void {
    void this.send('download', 'POST', '/api/v1/preprocessing/download', {
      ...this.selectionPayload(),
      timestamp: this.timestamp,
    });
  }

  process(): void {
    void this.send('process', 'POST', '/api/v1/preprocessing/process', {
      ...this.selectionPayload(),
      save_blocks: this.saveBlocks,
    });
  }

  runPipeline(): void {
    void this.send('run', 'POST', '/api/v1/preprocessing/run', {
      ...this.selectionPayload(),
      timestamp: this.timestamp,
      save_blocks: this.saveBlocks,
    });
  }

  createEmbeddings(): void {
    void this.send(
      'embeddings',
      'POST',
      '/api/v1/preprocessing/embeddings',
      this.selectionPayload(),
    );
  }

  search(): void {
    const query = this.query.trim();
    if (!query) {
      return;
    }
    void this.send('search', 'POST', '/api/v1/search', { query });
  }

  responseFor(key: RequestKey): ApiResponse | undefined {
    return this.responses()[key];
  }

  isLoading(key: RequestKey): boolean {
    return this.loading()[key] ?? false;
  }

  private selectionPayload(): Record<string, number> {
    const payload: Record<string, number> = {};
    if (this.pageSelection.pageId !== null) {
      payload['page_id'] = this.pageSelection.pageId;
    }
    if (this.pageSelection.startPage !== null) {
      payload['start_page'] = this.pageSelection.startPage;
    }
    if (this.pageSelection.endPage !== null) {
      payload['end_page'] = this.pageSelection.endPage;
    }
    return payload;
  }

  private async send(
    key: RequestKey,
    method: 'GET' | 'POST',
    url: string,
    body?: unknown,
  ): Promise<void> {
    this.loading.update((state) => ({ ...state, [key]: true }));
    this.responses.update((state) => {
      const next = { ...state };
      delete next[key];
      return next;
    });

    try {
      const response = await firstValueFrom(
        this.http.request(method, url, { body, observe: 'response' }),
      );
      this.responses.update((state) => ({
        ...state,
        [key]: {
          status: response.status,
          ok: response.ok,
          body: this.formatBody(response.body),
        },
      }));
    } catch (error: unknown) {
      const httpError = error instanceof HttpErrorResponse ? error : null;
      this.responses.update((state) => ({
        ...state,
        [key]: {
          status: httpError?.status ?? 0,
          ok: false,
          body: this.formatBody(httpError?.error ?? error),
        },
      }));
    } finally {
      this.loading.update((state) => ({ ...state, [key]: false }));
    }
  }

  private formatBody(body: unknown): string {
    if (typeof body === 'string') {
      return body;
    }
    if (body === undefined || body === null) {
      return String(body);
    }
    try {
      return JSON.stringify(body, null, 2);
    } catch {
      return String(body);
    }
  }
}

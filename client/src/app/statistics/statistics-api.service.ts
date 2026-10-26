import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { StatisticsResponse } from './statistics.models';

@Injectable({ providedIn: 'root' })
export class StatisticsApiService {
  private readonly http = inject(HttpClient);

  load(includeTokens: boolean): Observable<StatisticsResponse> {
    return this.http.get<StatisticsResponse>('/api/v1/statistics', {
      params: { include_tokens: includeTokens },
    });
  }
}

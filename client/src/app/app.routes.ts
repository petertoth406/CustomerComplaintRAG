import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./api-console/api-console').then((module) => module.ApiConsole),
  },
  {
    path: 'statistics',
    loadComponent: () =>
      import('./statistics/statistics-shell').then(
        (module) => module.StatisticsShell,
      ),
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'overview' },
      {
        path: 'overview',
        loadComponent: () =>
          import('./statistics/statistics-overview').then(
            (module) => module.StatisticsOverview,
          ),
      },
      {
        path: 'pages',
        loadComponent: () =>
          import('./statistics/statistics-pages').then(
            (module) => module.StatisticsPages,
          ),
      },
      {
        path: 'chunks',
        loadComponent: () =>
          import('./statistics/statistics-chunks').then(
            (module) => module.StatisticsChunks,
          ),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];

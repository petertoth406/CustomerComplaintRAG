import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-statistics-shell',
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './statistics-shell.html',
})
export class StatisticsShell {}

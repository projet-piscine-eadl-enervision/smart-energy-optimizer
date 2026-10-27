import { Component, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AlertsService } from '../../core/alerts.service';
import { AuthService } from '../../core/auth.service';
import { User } from '../../core/models';

/** Page commune des connectés : en-tête (navigation, compte, déconnexion) et contenu de la route. */
@Component({
  selector: 'app-shell',
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './shell.html',
})
export class Shell implements OnInit, OnDestroy {
  protected readonly auth = inject(AuthService);
  protected readonly alerts = inject(AlertsService);
  protected readonly user = signal<User | null>(null);

  ngOnInit(): void {
    // Un échec n'empêche pas d'utiliser l'application : l'en-tête n'affiche simplement pas le compte
    this.auth.me().subscribe({ next: (u) => this.user.set(u), error: () => this.user.set(null) });
    this.alerts.start();
  }

  ngOnDestroy(): void {
    this.alerts.stop();
  }
}

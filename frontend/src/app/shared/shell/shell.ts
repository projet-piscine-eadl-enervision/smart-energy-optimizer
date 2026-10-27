import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from '../../core/auth.service';
import { User } from '../../core/models';

/** Page commune des connectés : en-tête (navigation, compte, déconnexion) et contenu de la route. */
@Component({
  selector: 'app-shell',
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './shell.html',
})
export class Shell implements OnInit {
  protected readonly auth = inject(AuthService);
  protected readonly user = signal<User | null>(null);

  ngOnInit(): void {
    // Un échec n'empêche pas d'utiliser l'application : l'en-tête n'affiche simplement pas le compte
    this.auth.me().subscribe({ next: (u) => this.user.set(u), error: () => this.user.set(null) });
  }
}

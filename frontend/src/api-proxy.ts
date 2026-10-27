import type { Request, Response } from 'express';
import { Readable } from 'node:stream';
import type { ReadableStream as NodeReadableStream } from 'node:stream/web';
import { buildUpstreamUrl, parseApiUpstream } from './api-upstream';

/**
 * Le front appelle l'API par un chemin relatif (/api/...) : ce serveur transmet la requête à
 * l'adresse donnée par API_UPSTREAM, lue au lancement. Aucune adresse d'environnement n'est dans
 * le code, ce qui permet de promouvoir la même image du staging à la production.
 *
 * Lue au premier besoin et non au chargement du module : le build (pré-rendu) charge aussi ce code,
 * sans API_UPSTREAM. Au lancement du serveur, server.ts appelle getApiUpstream() pour échouer tout
 * de suite, avec un message clair, si la variable manque.
 */
let apiUpstream: URL | undefined;

export function getApiUpstream(): URL {
  apiUpstream ??= parseApiUpstream(process.env['API_UPSTREAM']);
  return apiUpstream;
}

// En-têtes propres à une connexion, jamais transmis. content-length et content-encoding sont aussi
// retirés : fetch a déjà décompressé le corps, qui est renvoyé en flux.
const HOP_BY_HOP = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
  'host',
  'content-length',
  'content-encoding',
]);

/** IP de la connexion, sans le préfixe IPv6 des adresses IPv4 (::ffff:203.0.113.7 devient 203.0.113.7). */
export function clientAddress(req: Request): string | undefined {
  const address = req.socket?.remoteAddress;
  return address?.startsWith('::ffff:') ? address.slice('::ffff:'.length) : address;
}

export async function apiProxy(req: Request, res: Response): Promise<void> {
  let upstreamUrl: URL | null;
  try {
    // Monté sous /api, Express a déjà retiré ce préfixe de req.url.
    upstreamUrl = buildUpstreamUrl(req.url, getApiUpstream());
  } catch (error) {
    console.error('Proxy API mal configuré :', error);
    res.status(500).json({ detail: 'Proxy API mal configuré' });
    return;
  }
  // Chemin qui ferait sortir la requête de l'hôte de l'API : refusé sans appeler l'amont.
  if (!upstreamUrl) {
    res.status(400).json({ detail: 'Chemin invalide' });
    return;
  }

  const headers = new Headers();
  for (const [name, value] of Object.entries(req.headers)) {
    if (value === undefined || HOP_BY_HOP.has(name)) continue;
    headers.set(name, Array.isArray(value) ? value.join(', ') : value);
  }
  // Adresse réelle du client, ajoutée à droite de l'en-tête reçu : l'API ne retient que la partie ajoutée
  // par ce proxy de confiance (TRUSTED_PROXY_IPS), une valeur forgée par le navigateur reste à gauche.
  const clientIp = clientAddress(req);
  if (clientIp) {
    const received = headers.get('x-forwarded-for');
    headers.set('x-forwarded-for', received ? `${received}, ${clientIp}` : clientIp);
  }
  headers.set('x-forwarded-host', req.headers.host ?? '');
  headers.set('x-forwarded-proto', req.protocol);

  const hasBody = req.method !== 'GET' && req.method !== 'HEAD';
  const init: RequestInit & { duplex?: 'half' } = {
    method: req.method,
    headers,
    redirect: 'manual',
  };
  if (hasBody) {
    init.body = Readable.toWeb(req) as unknown as BodyInit;
    init.duplex = 'half';
  }

  try {
    const upstream = await fetch(upstreamUrl, init);

    res.status(upstream.status);
    upstream.headers.forEach((value, name) => {
      if (!HOP_BY_HOP.has(name) && name !== 'set-cookie') res.setHeader(name, value);
    });
    const cookies = upstream.headers.getSetCookie();
    if (cookies.length > 0) res.setHeader('set-cookie', cookies);

    if (upstream.body) {
      Readable.fromWeb(upstream.body as unknown as NodeReadableStream)
        .on('error', () => res.destroy())
        .pipe(res);
    } else {
      res.end();
    }
  } catch (error) {
    console.error(`API injoignable (${upstreamUrl.origin}) :`, error);
    if (!res.headersSent) res.status(502).json({ detail: 'API injoignable' });
  }
}

/**
 * Adresse de l'API et construction des URL appelées par le proxy (voir api-proxy.ts).
 * Fonctions pures, sans dépendance à Node ni à Express, pour être testées seules.
 */

/**
 * Valide la valeur de API_UPSTREAM. Aucune valeur par défaut : l'adresse vient toujours de
 * l'environnement (Dockerfile, docker-compose), jamais du code.
 */
export function parseApiUpstream(value: string | undefined): URL {
  if (!value?.trim()) {
    throw new Error(
      "API_UPSTREAM n'est pas définie : indiquer l'adresse de l'API, par exemple http://api:8000",
    );
  }
  let upstream: URL;
  try {
    upstream = new URL(value.trim());
  } catch {
    throw new Error(`API_UPSTREAM n'est pas une URL valide : ${value}`);
  }
  if (upstream.protocol !== 'http:' && upstream.protocol !== 'https:') {
    throw new Error(`API_UPSTREAM doit commencer par http:// ou https:// : ${value}`);
  }
  return upstream;
}

/**
 * Construit l'URL de l'API pour le chemin demandé par le client (req.url, sans le préfixe /api).
 * Renvoie null si le chemin ferait sortir la requête de l'hôte de l'API (protection SSRF) :
 * chemin non relatif, « // » ou « \ » en tête (URL sans schéma vers un autre hôte), origine différente.
 */
export function buildUpstreamUrl(path: string, upstream: URL): URL | null {
  if (!path.startsWith('/') || path.startsWith('//') || path.includes('\\')) return null;

  // Le chemin éventuel de API_UPSTREAM (ex. http://api:8000/v1) est conservé, comme avant.
  let end = upstream.pathname.length;
  while (end > 0 && upstream.pathname[end - 1] === '/') {
    end--;
  }
  const basePath = upstream.pathname.slice(0, end);
  let target: URL;
  try {
    target = new URL(`${basePath}${path}`, upstream.origin);
  } catch {
    return null;
  }
  return target.origin === upstream.origin ? target : null;
}

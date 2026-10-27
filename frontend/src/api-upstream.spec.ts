import { buildUpstreamUrl, parseApiUpstream } from './api-upstream';

describe('parseApiUpstream', () => {
  it('accepte une URL http ou https', () => {
    expect(parseApiUpstream('http://api:8000').origin).toBe('http://api:8000');
    expect(parseApiUpstream('https://api.example.org').origin).toBe('https://api.example.org');
  });

  it('refuse une valeur absente ou vide (aucune adresse par défaut)', () => {
    expect(() => parseApiUpstream(undefined)).toThrow(/API_UPSTREAM/);
    expect(() => parseApiUpstream('  ')).toThrow(/API_UPSTREAM/);
  });

  it('refuse une URL invalide ou un autre protocole', () => {
    expect(() => parseApiUpstream('api:8000/x y')).toThrow(/API_UPSTREAM/);
    expect(() => parseApiUpstream('file:///etc/passwd')).toThrow(/http/);
  });
});

describe('buildUpstreamUrl', () => {
  const upstream = new URL('http://api:8000');

  it("construit l'URL des appels normaux /api/...", () => {
    expect(buildUpstreamUrl('/sites', upstream)?.href).toBe('http://api:8000/sites');
    expect(buildUpstreamUrl('/energy/SITE001?from=2024-01-01&to=2024-01-31', upstream)?.href).toBe(
      'http://api:8000/energy/SITE001?from=2024-01-01&to=2024-01-31',
    );
  });

  it("conserve le chemin éventuel de l'adresse de l'API", () => {
    const withPath = new URL('http://api:8000/v1/');
    expect(buildUpstreamUrl('/sites', withPath)?.href).toBe('http://api:8000/v1/sites');
  });

  it("refuse un chemin qui ferait sortir la requête de l'hôte de l'API", () => {
    for (const path of [
      '//evil.example.com/x',
      '/\\evil.example.com/x',
      '\\\\evil.example.com/x',
      'http://evil.example.com/x',
      'evil.example.com/x',
      '',
    ]) {
      expect(buildUpstreamUrl(path, upstream), path).toBeNull();
    }
  });

  it("ne change pas d'hôte avec un @ ou des ..", () => {
    expect(buildUpstreamUrl('/@evil.example.com/x', upstream)?.origin).toBe('http://api:8000');
    expect(buildUpstreamUrl('/../../evil', upstream)?.origin).toBe('http://api:8000');
  });
});

import type { Request, Response } from 'express';
import { Readable, Writable } from 'node:stream';

/** Réponse Express factice : garde le statut, les en-têtes et le corps reçus. */
class FakeResponse extends Writable {
  statusCode = 200;
  headers: Record<string, string | string[]> = {};
  body = '';
  headersSent = false;
  readonly done = new Promise<void>((resolve) => this.on('finish', resolve).on('close', resolve));

  override _write(chunk: Buffer, _encoding: BufferEncoding, callback: () => void): void {
    this.headersSent = true;
    this.body += chunk.toString();
    callback();
  }

  status(code: number): this {
    this.statusCode = code;
    return this;
  }

  setHeader(name: string, value: string | string[]): this {
    this.headers[name] = value;
    return this;
  }

  json(payload: unknown): this {
    this.setHeader('content-type', 'application/json');
    this.end(JSON.stringify(payload));
    return this;
  }
}

/** Requête Express factice : un flux lisible (le corps) avec les champs lus par le proxy. */
function fakeRequest(
  url: string,
  {
    method = 'GET',
    headers = {},
    body = '',
  }: { method?: string; headers?: Record<string, string | string[]>; body?: string } = {},
): Request {
  const req = Readable.from(body ? [Buffer.from(body)] : []);
  return Object.assign(req, {
    url,
    method,
    protocol: 'https',
    headers: { host: 'enervision.example.org', ...headers },
  }) as unknown as Request;
}

/** Recharge le module pour repartir d'une adresse de l'API non encore lue (elle est mise en cache). */
async function loadProxy(upstream: string | undefined): Promise<typeof import('./api-proxy')> {
  if (upstream === undefined) delete process.env['API_UPSTREAM'];
  else process.env['API_UPSTREAM'] = upstream;
  vi.resetModules();
  return import('./api-proxy');
}

async function callProxy(
  apiProxy: (req: Request, res: Response) => Promise<void>,
  req: Request,
): Promise<FakeResponse> {
  const res = new FakeResponse();
  await apiProxy(req, res as unknown as Response);
  await res.done;
  return res;
}

describe('apiProxy', () => {
  const savedUpstream = process.env['API_UPSTREAM'];
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    if (savedUpstream === undefined) delete process.env['API_UPSTREAM'];
    else process.env['API_UPSTREAM'] = savedUpstream;
  });

  it("transmet la requête à l'API et renvoie sa réponse, sans les en-têtes de connexion", async () => {
    const { apiProxy } = await loadProxy('http://api:8000');
    const upstreamHeaders = new Headers({
      'content-type': 'application/json',
      connection: 'keep-alive',
      'x-total': '2',
    });
    upstreamHeaders.append('set-cookie', 'a=1');
    upstreamHeaders.append('set-cookie', 'b=2');
    fetchMock.mockResolvedValue(
      new Response('[{"id":"SITE001"}]', { status: 200, headers: upstreamHeaders }),
    );

    const res = await callProxy(
      apiProxy,
      fakeRequest('/sites?limit=2', {
        headers: { accept: 'application/json', connection: 'close', 'x-multi': ['a', 'b'] },
      }),
    );

    const [url, init] = fetchMock.mock.calls[0] as [URL, RequestInit];
    expect(url.href).toBe('http://api:8000/sites?limit=2');
    expect(init.method).toBe('GET');
    expect(init.redirect).toBe('manual');
    expect(init.body).toBeUndefined();
    const sent = init.headers as Headers;
    expect(sent.get('accept')).toBe('application/json');
    expect(sent.get('x-multi')).toBe('a, b');
    expect(sent.has('connection')).toBe(false);
    expect(sent.has('host')).toBe(false);
    expect(sent.get('x-forwarded-host')).toBe('enervision.example.org');
    expect(sent.get('x-forwarded-proto')).toBe('https');

    expect(res.statusCode).toBe(200);
    expect(res.body).toBe('[{"id":"SITE001"}]');
    expect(res.headers['x-total']).toBe('2');
    expect(res.headers['connection']).toBeUndefined();
    expect(res.headers['set-cookie']).toEqual(['a=1', 'b=2']);
  });

  it('transmet le corps des requêtes autres que GET et HEAD', async () => {
    const { apiProxy } = await loadProxy('http://api:8000');
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    const res = await callProxy(
      apiProxy,
      fakeRequest('/predictions', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: '{"site":"SITE001"}',
      }),
    );

    const [, init] = fetchMock.mock.calls[0] as [URL, RequestInit & { duplex?: string }];
    expect(init.method).toBe('POST');
    expect(init.duplex).toBe('half');
    expect(await new Response(init.body).text()).toBe('{"site":"SITE001"}');
    expect(res.statusCode).toBe(204);
    expect(res.body).toBe('');
  });

  it("refuse un chemin qui ferait sortir la requête de l'hôte de l'API, sans l'appeler (SSRF)", async () => {
    const { apiProxy } = await loadProxy('http://api:8000');

    for (const path of [
      '//evil.example.com/x',
      '/\\evil.example.com/x',
      'http://evil.example.com/x',
    ]) {
      const res = await callProxy(apiProxy, fakeRequest(path));
      expect(res.statusCode, path).toBe(400);
      expect(JSON.parse(res.body)).toEqual({ detail: 'Chemin invalide' });
    }
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("répond 502 quand l'API est injoignable", async () => {
    const { apiProxy } = await loadProxy('http://api:8000');
    fetchMock.mockRejectedValue(new TypeError('fetch failed'));

    const res = await callProxy(apiProxy, fakeRequest('/sites'));

    expect(res.statusCode).toBe(502);
    expect(JSON.parse(res.body)).toEqual({ detail: 'API injoignable' });
  });

  it('répond 500 sans appeler personne quand API_UPSTREAM manque', async () => {
    const { apiProxy } = await loadProxy(undefined);

    const res = await callProxy(apiProxy, fakeRequest('/sites'));

    expect(res.statusCode).toBe(500);
    expect(JSON.parse(res.body)).toEqual({ detail: 'Proxy API mal configuré' });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('getApiUpstream lit API_UPSTREAM une seule fois', async () => {
    const { getApiUpstream } = await loadProxy('http://api:8000');
    expect(getApiUpstream().origin).toBe('http://api:8000');
    process.env['API_UPSTREAM'] = 'http://autre:9000';
    expect(getApiUpstream().origin).toBe('http://api:8000');
  });
});

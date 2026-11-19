"""Read-only checks for the live demo. No indexing, writes to ES or model calls."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup
from wikinews_search.config import DEFAULT_ES_URL, DEFAULT_INDEX
from wikinews_search.indexer import make_client
from wikinews_search.searcher import FIELDS, build_body, search


def inspect_response(case, data, expected=None):
    """Validate actual API/direct results, including filters and order."""
    assert data['total'] > 0 and data['hits'], 'Nessuna corrispondenza'
    params = case['params']
    if expected is not None:
        assert data['total'] == expected['total'], f"Totale {data['total']} != {expected['total']}"
        top = [{'id': h['id'], 'title': h['title']} for h in data['hits'][:3]]
        assert top == expected['top3'], 'Primi tre ID/titoli diversi dalla verifica documentata'
    if params.get('category'):
        assert all(params['category'] in h['categories'] for h in data['hits']), 'Categoria errata'
    if params.get('year'):
        assert all(h['date'] and h['date'][:4] == params['year'] for h in data['hits']), 'Anno errato'
    if params.get('sort') == 'date':
        dates = [h['date'] for h in data['hits'] if h['date']]
        assert dates == sorted(dates, reverse=True), 'Date non decrescenti'
    return f"{data['total']} risultati; primi tre ID: " + ', '.join(h['id'] for h in data['hits'][:3])


def run_checks(es, index, base_url, cases, expected_count=12209, timeout=5):
    checks = []
    observed = {}

    def check(name, fn, ready=True):
        if not ready:
            checks.append(dict(name=name, status='SKIP', detail='Prerequisito non disponibile'))
            return False
        try:
            detail = fn()
            checks.append(dict(name=name, status='PASS', detail=detail or 'OK'))
            return True
        except Exception as exc:
            checks.append(dict(name=name, status='FAIL', detail=f'{type(exc).__name__}: {exc}'))
            return False

    def require(condition, detail):
        if not condition:
            raise AssertionError(detail)
        return detail

    def fetch(path, as_json=False):
        with urlopen(base_url.rstrip('/') + path, timeout=timeout) as response:
            raw = response.read().decode('utf-8')
        return json.loads(raw) if as_json else raw

    es_ready = check('Elasticsearch', lambda: 'Versione ' + es.info()['version']['number'])
    uuid = None
    def index_metadata():
        nonlocal uuid
        require(es.indices.exists(index=index), index)
        uuid = es.indices.get_settings(index=index)[index]['settings']['index']['uuid']
        return index + ' / ' + uuid
    index_ready = check('Indice esistente', index_metadata, es_ready)
    check('Conteggio corpus', lambda: require(es.count(index=index)['count'] == expected_count,
          f'Attesi {expected_count} documenti; trovati {es.count(index=index)["count"]}'), index_ready)

    def configuration():
        mapping = es.indices.get_mapping(index=index)[index]['mappings']['properties']
        settings = es.indices.get_settings(index=index)[index]['settings']['index']
        assert FIELDS == ['title', 'body'], 'Pesi applicativi diversi dalla configurazione B'
        for field in ('title', 'body'):
            assert mapping[field]['analyzer'] == 'italiano', 'Analyzer non italiano'
            similarity = mapping[field].get('similarity', 'default')
            configured = settings.get('similarity', {}).get(similarity, {})
            assert configured.get('type', 'BM25') == 'BM25', 'Similarity non BM25'
        return 'B: analyzer italiano, BM25, title/body uniformi'
    check('Configurazione ricerca', configuration, index_ready)

    def direct(case):
        params = case['params'].copy()
        q = params.pop('q')
        result = search(es, q, index=index, **params)
        data = dict(total=result.total, hits=[dict(id=h.id, title=h.title, categories=h.categories,
                    date=h.date.isoformat() if h.date else None, snippet_html=h.snippet) for h in result.hits])
        observed[case['id']] = data
        return inspect_response(case, data, case.get('expected'))
    for case in cases:
        check('ES / ' + case['id'], lambda c=case: direct(c), index_ready)

    def equivalent(left, right):
        a, b = observed[left], observed[right]
        assert (a['total'], [h['id'] for h in a['hits']]) == (b['total'], [h['id'] for h in b['hits']])
        queries = [next(c['params']['q'] for c in cases if c['id'] == name) for name in (left, right)]
        tokens = [[t['token'] for t in es.indices.analyze(index=index, analyzer='italiano', text=q)['tokens']] for q in queries]
        assert tokens[0] == tokens[1], 'Token diversi'
        return 'Token, conteggi e prima pagina identici: ' + repr(tokens[0])
    for left, right in [('stemming', 'stemming_plural'), ('accents', 'accents_unicode')]:
        check('Equivalenza / ' + left, lambda l=left, r=right: equivalent(l, r),
              index_ready and left in observed and right in observed)

    def operators():
        def count(q):
            return es.count(index=index, query=build_body(q, 1, 1)['query'])['count']
        roma, milano = count('Roma'), count('Milano')
        both, either = count('Roma + Milano'), count('Roma | Milano')
        assert either == roma + milano - both, 'AND/OR non coerenti con intersezione/unione'
        assert count('elezioni -Roma') == count('elezioni') - count('elezioni + Roma'), 'Esclusione incoerente'
        return f'AND={both}, OR={either}; verificata esclusione globale di Roma'
    check('Semantica AND / OR / NOT', operators, index_ready)

    web_ready = check('Homepage Flask', lambda: require('Cerca nell' in fetch('/'), 'Homepage disponibile'))
    check('Health', lambda: require(fetch('/health', True) == dict(status='ok', documents=expected_count),
          '/health: stato e conteggio corretti'), web_ready)
    check('CSS', lambda: require(':root' in fetch('/static/style.css'), 'Foglio di stile disponibile'), web_ready)

    for case in cases:
        def api(c=case):
            data = fetch('/api/search?' + urlencode(c['params']), True)
            detail = inspect_response(c, data, c.get('expected'))
            if c['id'] in observed:
                original = observed[c['id']]
                assert (data['total'], [h['id'] for h in data['hits']]) == (original['total'], [h['id'] for h in original['hits']]), 'API e indice selezionato non coincidono'
            assert data['facets']['category'] and data['facets']['year'], 'Faccette assenti'
            return detail
        check('API / ' + case['id'], api, web_ready)

    def navigation():
        first = fetch('/api/search?q=terremoto', True)
        second = fetch('/api/search?q=terremoto&page=2', True)
        assert first['page'] == 1 and second['page'] == 2
        assert not {h['id'] for h in first['hits']} & {h['id'] for h in second['hits']}
        html = BeautifulSoup(fetch('/?q=terremoto'), 'html.parser')
        assert html.select_one('a[rel="next"]'), 'Link alla pagina successiva assente'
        assert html.select_one('mark'), 'Snippet non evidenziati'
        article_link = html.select_one('.hits h3 a')['href']
        article = BeautifulSoup(fetch(article_link), 'html.parser')
        assert article.select_one('.article-body mark'), 'Articolo non evidenziato'
        assert article.select_one('.source a')['href'].startswith('https://it.wikinews.org/')
        back = article.select_one('.back a')['href']
        assert back.startswith('/?') and 'terremoto' in back and fetch(back)
        return 'Pagine distinte, snippet, apertura articolo, evidenziazione, fonte e ritorno ai risultati'
    check('Navigazione e articolo', navigation, web_ready)
    check('Risultati vuoti', lambda: require(fetch('/api/search?q=xyzqwerty', True)['total'] == 0,
          'Query senza corrispondenze gestita'), web_ready)
    counts = {status: sum(c['status'] == status for c in checks) for status in ('PASS', 'FAIL', 'SKIP')}
    return dict(checked_at_utc=datetime.now(timezone.utc).isoformat(), index=index, index_uuid=uuid,
                base_url=base_url, expected_documents=expected_count, checks=checks, summary=counts,
                read_only=True, benchmark=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--es-url', default=DEFAULT_ES_URL)
    parser.add_argument('--index-name', default=DEFAULT_INDEX)
    parser.add_argument('--base-url', default='http://127.0.0.1:5000')
    parser.add_argument('--cases', type=Path, default=Path(__file__).with_name('demo_queries.json'))
    parser.add_argument('--expected-documents', type=int, default=12209)
    parser.add_argument('--timeout', type=float, default=5)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    cases = json.loads(args.cases.read_text(encoding='utf-8'))['cases']
    es = make_client(args.es_url).options(request_timeout=args.timeout, max_retries=0)
    report = run_checks(es, args.index_name, args.base_url, cases, args.expected_documents, args.timeout)
    for c in report['checks']:
        print(f"[{c['status']}] {c['name']}: {c['detail']}")
    print(json.dumps(report['summary']))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 1 if report['summary']['FAIL'] else 2 if report['summary']['SKIP'] else 0


if __name__ == '__main__':
    raise SystemExit(main())

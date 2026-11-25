"""Known source URLs are discovery seeds, never substitutes for current evidence."""
import json
from pathlib import Path
from discovery import routes

CATALOG = Path(__file__).with_name('source-catalog.json')


def plan(category, month, catalog=None, approved_reports=None):
    catalog = catalog or json.loads(CATALOG.read_text(encoding='utf-8'))
    group = catalog['categories'][category]
    selected = {}
    profiles = {}
    for mid, profile in group['metrics'].items():
        exact_ids = group.get('monthlySourceIds', {}).get(month, {}).get(mid, [])
        candidates = [catalog['sources'][sid] for sid in (exact_ids or profile['sourceIds'])
                      if not catalog['sources'][sid]['recordedMonths'] or
                      any(m <= month for m in catalog['sources'][sid]['recordedMonths'])]
        candidates.sort(key=lambda s: (s.get('publishedAt') or '', month in s['recordedMonths'],
                                      max(s['recordedMonths'] or [''])), reverse=True)
        # Prefer the exact-month publication; older URLs only identify the provider.
        chosen = candidates[:1]  # Keep a current provider seed; search discovers replacements.
        profiles[mid] = {k:v for k,v in profile.items() if k != 'sourceIds'}
        profiles[mid]['sourceUrls'] = [s['url'] for s in chosen]
        for source in chosen:
            entry = selected.setdefault(source['url'], dict(source, targetMetricIds=[]))
            entry['targetMetricIds'].append(mid)
    # Only reports already on main are approved discovery references. Transfer
    # links and definitions, never their historical values into new extraction.
    learned = set()
    for report_month, report in sorted((approved_reports or {}).items(), reverse=True):
        if report_month > month:
            continue
        for fact in report.get('categories',{}).get(category,{}).get('facts',[]):
            mid = fact.get('id')
            if mid not in profiles or mid in learned or not fact.get('url','').startswith('https://'):
                continue
            learned.add(mid)
            if fact.get('unit') != profiles[mid]['unit'] or fact.get('basis') != profiles[mid]['basis']:
                continue
            url = fact['url']
            existing_dates = [s.get('publishedAt') or '' for s in selected.values() if mid in s['targetMetricIds']]
            if (fact.get('publishedAt') or '') <= max(existing_dates or ['']):
                continue
            if url not in profiles[mid]['sourceUrls']:
                profiles[mid]['sourceUrls'].insert(0,url)
            entry = selected.setdefault(url, {'url':url,'title':fact.get('title','已审核来源'),
                'publishedAt':fact.get('publishedAt'),'recordedMonths':[report_month],
                'method':fact.get('basis'),'reviewStatus':'approved_report_on_main','targetMetricIds':[]})
            if mid not in entry['targetMetricIds']:
                entry['targetMetricIds'].append(mid)
    seeds = sorted(selected.values(), key=lambda s: (
        month in s['recordedMonths'], len(s['targetMetricIds']),
        s.get('publishedAt') or '', max(s['recordedMonths'] or [''])), reverse=True)
    return {'rules':catalog['rules'], 'metrics':profiles, 'seeds':seeds,
            'discoveryRoutes':routes(category,month,[[mid,p['section'],p['label'],p['unit'],p['basis']]
                                                    for mid,p in profiles.items()]),
            'note':'recordedMonths仅表示旧台账记录，必须从原文重新核验目标统计期；旧数字不传给模型。'}

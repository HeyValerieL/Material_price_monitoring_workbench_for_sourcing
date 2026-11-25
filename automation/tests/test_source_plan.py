import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from source_plan import plan


class SourcePlanTests(unittest.TestCase):
    def test_approved_new_source_is_reused_without_transferring_old_values(self):
        reports={'2026-10':{'categories':{'copper':{'facts':[{'id':'output','value':108.67,
            'unit':'万吨/月','basis':'monthly','url':'https://news.smm.cn/new-actual',
            'title':'SMM新月报','publishedAt':'2026-10-31'}]}}}}
        result=plan('copper','2026-11',approved_reports=reports)
        self.assertEqual(result['metrics']['output']['sourceUrls'][0],'https://news.smm.cn/new-actual')
        seed=next(s for s in result['seeds'] if s['url']=='https://news.smm.cn/new-actual')
        self.assertNotIn('value',seed)
        self.assertEqual(seed['reviewStatus'],'approved_report_on_main')
        self.assertFalse(any(s['url']=='https://news.smm.cn/new-actual' for s in plan('copper','2026-09',approved_reports=reports)['seeds']))

    def test_exact_month_first_no_historical_values(self):
        def source(month):
            return {'url':'https://www.stats.gov.cn/'+month,'recordedMonths':[month],
                    'title':month,'metricIds':['output']}
        catalog = {'rules':[], 'sources':{'old':source('2026-09'),
                   'current':source('2026-10'),'future':source('2026-11')},
                   'categories':{'aluminum':{'metrics':{'output':{
                       'sourceIds':['old','future','current'],'unit':'万吨/月','label':'产量','section':'supply','basis':'monthly'}}}}}
        result = plan('aluminum','2026-10',catalog)
        self.assertEqual(result['seeds'][0]['url'],'https://www.stats.gov.cn/2026-10')
        self.assertEqual(len(result['seeds']),1)
        self.assertNotIn('historicalReferences',result)

    def test_real_catalog_covers_all_categories(self):
        for cat in ('aluminum','copper','iron'):
            result = plan(cat,'2026-10')
            self.assertTrue(result['seeds'])
            self.assertIn('calculation',result['metrics']['building'])
            self.assertIn('newOrders',result['metrics'])

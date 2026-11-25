import copy
import contextlib
import io
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('monthly', Path(__file__).parents[1] / 'monthly.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
URL = 'https://www.stats.gov.cn/sj/zxfb/202611/example.html'
PAGE = '发布日期2026-11-16。2026年10月份工业生产。原铝产量385万吨，同比增长1.8%。汽车产量304.5万辆，同比下降7.7%。制造业PMI49.3%。'


def observation(**changes):
    value = {'id': 'output', 'value': 385, 'unit': '万吨/月', 'period': '2026-10',
             'basis': 'monthly', 'definition': '国家统计局原铝产量', 'url': URL,
             'title': '10月工业生产', 'publishedAt': '2026-11-16',
             'quote': '原铝产量385万吨，同比增长1.8%', 'periodEvidence': '2026年10月份工业生产',
             'yoy': 1.8, 'yoyQuote': '原铝产量385万吨，同比增长1.8%',
             'mom': None, 'momQuote': '', 'comparisonDefinition': '官方可比口径'}
    value.update(changes)
    return value


def analysis(**changes):
    value = {'trend': '待观察', 'summary': '供给增长，等待价格验证', 'shortTerm': '观察库存',
             'mediumTerm': '观察订单', 'supportingEvidenceIds': ['output'],
             'conflictingEvidenceIds': [], 'actions': [{'title': '分批确认交付',
             'action': '在订单确定时分批确认交期', 'evidenceIds': ['output'],
             'adjustWhen': '供应转紧时提前锁量'}], 'riskNote': '结合实际订单安排。'}
    value.update(changes)
    return value


class ValidationTests(unittest.TestCase):
    def test_old_article_forecast_is_not_current_month_actual_output(self):
        url='https://news.smm.cn/news/example'
        item=observation(value=108.47,url=url,publishedAt='2026-09-30',
            quote='SMM预计2026年10月电解铜产量108.47万吨',periodEvidence='SMM预计2026年10月电解铜产量')
        page='2026-09-30。'+item['quote']
        result=m.validate_research('copper','2026-10',{'observations':[item]},{url},fetch=lambda _:page)
        self.assertFalse(result['facts'])
        self.assertIn('预测',result['rejected'][0]['reason'])

    def test_verified_trade_tonnes_are_converted_by_program(self):
        item = observation(id='refinedImport',value=311551.74,unit='吨/月',yoy=None,yoyQuote='',
            quote='2026年10月精炼铜进口311551.74吨',periodEvidence='2026年10月精炼铜进口',definition='海关精炼铜分项')
        page='2026-11-16。'+item['quote']
        result=m.validate_research('copper','2026-10',{'observations':[item]}, {URL},fetch=lambda _:page)
        fact=result['facts'][0]
        self.assertAlmostEqual(fact['value'],31.155174)
        self.assertEqual(fact['reportedValue'],311551.74)
        self.assertEqual(fact['unit'],'万吨/月')
        item.update(quote='2026年10月精炼铜进口311551.74万吨')
        result=m.validate_research('copper','2026-10',{'observations':[item]}, {URL},fetch=lambda _:'2026-11-16。'+item['quote'])
        self.assertFalse(result['facts'])

    def test_copper_production_cannot_silently_switch_to_nbs(self):
        result=m.validate_research('copper','2026-10',{'observations':[observation()]},{URL},fetch=lambda _:PAGE)
        self.assertFalse(result['facts'])
        self.assertIn('SMM',result['rejected'][0]['reason'])

    def test_stock_uses_actual_last_working_day(self):
        item=observation(id='stock',value=12.3,unit='万吨',basis='month_end',period='2026-10-30',
            quote='截至2026年10月30日铜社会库存12.3万吨',periodEvidence='截至2026年10月30日',yoy=None,yoyQuote='')
        page='2026-11-16。'+item['quote']
        result=m.validate_research('copper','2026-10',{'observations':[item]},{URL},fetch=lambda _:page)
        self.assertEqual(result['facts'][0]['period'],'2026-10-30')
        item['period']='2026-10-31'
        result=m.validate_research('copper','2026-10',{'observations':[item]},{URL},fetch=lambda _:page)
        self.assertFalse(result['facts'])

    def test_followup_merges_only_missing_ids_and_preserves_other_categories(self):
        class FakeClient:
            provider='deepseek'
            calls=0
            usage=[]
            extraction_rejections=[]
            raw_research={}
            payloads=[]
            def request(self,instructions,payload,schema,search=False):
                self.calls+=1
                self.payloads.append(payload)
                if search:return {'observations':[],'policies':[],'missing':[]},set()
                return analysis(),set()
        initial={'facts':[dict(observation(),label='产量'),dict(observation(id='auto'),label='汽车'),dict(observation(id='pmi'),label='PMI')],
                 'policies':[],'missing':['stock'],'rejected':[],'sourceHashes':{URL:'first'}}
        extra={'facts':[dict(observation(id='stock'),label='库存'),dict(observation(id='output',value=999),label='产量')],
               'policies':[],'missing':[],'rejected':[],'sourceHashes':{URL:'second'}}
        client=FakeClient()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'automation/output').mkdir(parents=True)
            kept={'facts':[],'analysis':analysis(),'policies':[],'missing':[],'rejected':[]}
            (root/'automation/output/previous-draft.json').write_text(json.dumps({'month':'2026-10','categories':{'iron':kept}}),encoding='utf-8')
            with patch.object(m,'Client',return_value=client),patch.object(m,'validate_research',side_effect=[copy.deepcopy(initial),copy.deepcopy(extra)]):
                report=m.run('2026-10',root,only_category='aluminum')
            facts=report['categories']['aluminum']['facts']
            self.assertEqual(next(f['value'] for f in facts if f['id']=='output'),385)
            self.assertIn('stock',{f['id'] for f in facts})
            self.assertEqual(client.payloads[1]['searchPhase'],'followup')
            self.assertIn('iron',report['categories'])
            self.assertEqual(client.calls,3)

    def test_gzip_source_is_decoded_before_extracting_text(self):
        import gzip
        from email.message import Message
        response = io.BytesIO(gzip.compress('<p>2026年9月电解铜产量112.06万吨</p>'.encode()))
        response.headers = Message()
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        response.headers['Content-Encoding'] = 'gzip'
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value = response
            self.assertIn('112.06万吨',m.fetch_page(URL))

    def test_gzip_expanded_content_is_bounded(self):
        import gzip
        from email.message import Message
        response = io.BytesIO(gzip.compress(b'x' * 2_000_001))
        response.headers = Message()
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value = response
            with self.assertRaisesRegex(ValueError,'解压后'):
                m.fetch_page(URL)

    def test_building_cumulative_cannot_masquerade_as_monthly(self):
        item = observation(id='building',value=25544,unit='万平方米/月',
            definition='1—10月房屋竣工面积累计值',quote='1—10月房屋竣工面积25544万平方米',
            periodEvidence='2026年10月份房地产开发投资情况')
        page = '2026-11-16。' + item['periodEvidence'] + item['quote']
        result = m.validate_research('aluminum','2026-10',{'observations':[item]}, {URL}, fetch=lambda _:page)
        self.assertFalse(result['facts'])
        self.assertIn('累计',result['rejected'][0]['reason'])

    def test_padded_chinese_publication_date_and_period_in_numeric_quote(self):
        item = observation(publishedAt='2026-11-06',
            quote='2026年10月份原铝产量385万吨，同比增长1.8%', periodEvidence='10月份原铝产量')
        page = '2026年11月06日。' + item['quote']
        result = m.validate_research('aluminum','2026-10',{'observations':[item]}, {URL}, fetch=lambda _:page)
        self.assertEqual(result['facts'][0]['periodEvidence'],item['quote'])
        self.assertEqual(result['facts'][0]['originalPeriodEvidence'],item['periodEvidence'])

    def test_one_invalid_model_row_does_not_drop_valid_observations(self):
        raw = {'observations':[observation(),observation(id='alumina',value=None)],
               'policies':[],'missing':['stock']}
        checked, rejected = m.check_research_rows(raw)
        self.assertEqual(len(checked['observations']),1)
        self.assertEqual(rejected[0]['id'],'alumina')
        self.assertIn('.value', rejected[0]['reason'])
        self.assertIsNone(raw['observations'][1]['value'])

    def test_no_monthly_comparison_cannot_be_called_sideways(self):
        with self.assertRaises(ValueError):
            m.validate_analysis(analysis(trend='震荡'), [dict(observation(id='price'),mom=None)], [])

    def test_fetch_compresses_blank_space_before_prompt_limit(self):
        from email.message import Message
        response = io.BytesIO((' ' * 20000 + '<table><td>385</td><td>1.8</td></table>').encode())
        response.headers = Message()
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value = response
            self.assertEqual(m.fetch_page(URL), '385 1.8')

    def test_energy_fetch_reads_public_api_not_empty_shell(self):
        from email.message import Message
        url = 'https://energydc.cn/policy/shandong/2026-10/fef4ddf4-bb12-11f1-959b-ce30ac533824'
        response = io.BytesIO(json.dumps({'code':200,'data':{'title':'2026年10月电价',
            'publish':'','content':'当月平均购电价格 0.3405 元/千瓦时'}}).encode())
        response.headers = Message()
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value = response
            text = m.fetch_page(url)
            self.assertIn('0.3405', text)
            self.assertIn('/edc/api/v1/eprice/policy/', opener.return_value.open.call_args.args[0].full_url)

    def test_unknown_publication_allowed_only_for_energy_execution_period(self):
        url = 'https://energydc.cn/policy/shandong/2026-10/fef4ddf4-bb12-11f1-959b-ce30ac533824'
        item = observation(id='powerShandong', value=.3405, unit='元/千瓦时',
            url=url,publishedAt='',quote='当月平均购电价格0.3405元/千瓦时',
            periodEvidence='执行时间2026年10月1日至31日',yoy=None,yoyQuote='')
        page = item['quote'] + item['periodEvidence']
        result = m.validate_research('aluminum','2026-10',{'observations':[item]}, {url}, fetch=lambda _:page)
        self.assertEqual(result['facts'][0]['publicationStatus'],'not_stated')
        item.update(url=URL)
        result = m.validate_research('aluminum','2026-10',{'observations':[item]}, {URL}, fetch=lambda _:page)
        self.assertFalse(result['facts'])

    def test_deepseek_selection_never_uses_openai_key(self):
        env = {'DEEPSEEK_API_KEY':'deepseek-test', 'DEEPSEEK_MODEL':'deepseek-v4-pro',
               'OPENAI_API_KEY':'openai-test', 'OPENAI_MODEL':'gpt-6.1-terra'}
        with patch.dict(os.environ, env, clear=True):
            client = m.Client()
            self.assertEqual(client.provider, 'deepseek')
            self.assertEqual(client.key, 'deepseek-test')
            self.assertEqual(client.api, 'https://api.deepseek.com/responses')

    def test_legacy_model_variable_can_hold_deepseek_name(self):
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY':'test', 'OPENAI_MODEL':'deepseek-v4-pro'}, clear=True):
            self.assertEqual(m.configuration()[2], 'deepseek-v4-pro')
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY':'test', 'OPENAI_MODEL':'gpt-6.1-terra'}, clear=True):
            with self.assertRaises(ValueError): m.configuration()

    def test_deepseek_omits_incompatible_openai_parameters(self):
        result = {'status':'completed', 'output':[{'type':'message','content':[{'type':'output_text','text':'{"value":1}'}]}]}
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY':'test','DEEPSEEK_MODEL':'deepseek-v4-pro'}, clear=True):
            client = m.Client()
            with patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(result).encode())) as network:
                output, urls = client.request('instructions', {}, m.obj({'value':{'type':'number'}}))
                request = network.call_args.args[0]
                body = json.loads(request.data)
                self.assertEqual(request.full_url, 'https://api.deepseek.com/responses')
                self.assertEqual(output, {'value':1})
                for field in ('store','include','max_tool_calls','tools'): self.assertNotIn(field, body)

    def test_deepseek_sources_come_only_from_search_results(self):
        result = {'status':'completed', 'output':[{'type':'message','content':[{'type':'output_text','text':'{"value":1}'}]}]}
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY':'test','DEEPSEEK_MODEL':'deepseek-v4-pro'}, clear=True):
            client = m.Client()
            with patch.object(client, 'search_sources', return_value=[{'url':URL,'content':PAGE}]), patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(result).encode())):
                _, urls = client.request('instructions', {}, m.obj({'value':{'type':'number'}}), search=True)
                self.assertEqual(urls, {URL})

    def test_schema_validation_rejects_invalid_shape(self):
        schema = m.obj({'value':{'type':'number'}})
        for output in ({'value':True}, {'value':None}, {}, {'value':1,'extra':2}, {'value':float('nan')}):
            with self.assertRaises(ValueError): m.validate_schema(output,schema)

    def check(self, item, page=PAGE):
        return m.validate_research('aluminum', '2026-10', {'observations': [item]}, {URL}, fetch=lambda _: page)

    def test_real_quote_and_statistical_month(self):
        result = self.check(observation())
        self.assertEqual(len(result['facts']), 1)
        self.assertEqual(result['facts'][0]['yoy'], 1.8)

    def test_table_cell_separators_preserve_numbers(self):
        self.assertTrue(m.number_in(385, '原铝（万吨）\n385\n1.8\n3885\n3.5'))
        self.assertTrue(m.number_in(1.8, '原铝（万吨）\n385\n1.8\n3885\n3.5'))
        self.assertFalse(m.number_in(3.1, '增长13.1%'))

    def test_same_source_host_alias_still_requires_original_quote(self):
        alias = URL.replace('/sj/zxfb/', '/sj/zxfbhjd/')
        valid = m.validate_research('aluminum','2026-10',{'observations':[observation(url=alias)]},{URL},fetch=lambda _:PAGE)
        self.assertEqual(len(valid['facts']),1)
        invalid = m.validate_research('aluminum','2026-10',{'observations':[observation(url=alias)]},{URL},fetch=lambda _:'unrelated page')
        self.assertFalse(invalid['facts'])

    def test_rejects_invalid_source_numbers_units_and_periods(self):
        for changes in [{'value': 999}, {'period': '2026-09'}, {'unit': '吨/月'},
                        {'url': 'https://attacker.example/'}, {'publishedAt': '2099-01-01'},
                        {'quote': '原铝产量999万吨，同比增长1.8%'}, {'id': 'unknown'},
                        {'periodEvidence': '2025年10月份工业生产'}, {'value': float('nan')}]:
            with self.subTest(changes=changes):
                self.assertFalse(self.check(observation(**changes))['facts'])

    def test_rejects_page_without_publication_date(self):
        self.assertFalse(self.check(observation(), PAGE.replace('2026-11-16', ''))['facts'])

    def test_missing_year_in_period_is_not_verified(self):
        self.assertFalse(self.check(observation(periodEvidence='10月份工业生产'))['facts'])

    def test_unconfirmed_change_is_removed(self):
        self.assertIsNone(self.check(observation(yoy=8.8))['facts'][0]['yoy'])

    def test_no_search_citation_no_acceptance(self):
        result = m.validate_research('aluminum', '2026-10', {'observations':[observation()]}, set(), fetch=lambda _: PAGE)
        self.assertFalse(result['facts'])

    def test_duplicate_metric_not_duplicated(self):
        result = m.validate_research('aluminum', '2026-10', {'observations':[observation(), observation()]}, {URL}, fetch=lambda _: PAGE)
        self.assertEqual(len(result['facts']), 1)

    def test_hostname_boundary(self):
        for url in ['http://stats.gov.cn/', 'https://stats.gov.cn.evil.example/',
                    'https://stats.gov.cn@evil.example/', 'https://stats.gov.cn:8888/']:
            self.assertFalse(m.allowed(url))
        self.assertTrue(m.allowed(URL))

    def test_price_requires_final_ten_days(self):
        fact = observation(id='price', unit='元/吨', basis='month_end_proxy', period='2026-10-31')
        self.assertFalse(self.check(fact)['facts'])

    def test_previous_ten_days_not_treated_as_monthly_change(self):
        fact = observation(id='price', unit='元/吨', basis='month_end_proxy', period='2026-10-31',
                           periodEvidence='2026年10月21—31日', mom=1.8, momQuote='原铝产量385万吨，同比增长1.8%')
        result = self.check(fact, PAGE + '2026年10月21—31日')['facts'][0]
        self.assertIsNone(result['mom'])
        self.assertIsNone(result['yoy'])

    def test_comparison_only_for_same_definition(self):
        current = observation(yoy=None)
        base = observation(value=350, period='2026-09')
        result = m.compare([current], [base])[0]
        self.assertAlmostEqual(result['mom'], 10)
        different = observation(yoy=None)
        m.compare([different], [dict(base, definition='不同统计样本')])
        self.assertIsNone(different['mom'])

    def test_annual_is_not_compared_to_monthly(self):
        fact = observation(id='outputPriorYear', basis='annual', period='2025', yoy=None)
        self.assertIsNone(m.compare([fact], [observation()])[0]['mom'])

    def test_index_change_uses_percentage_points(self):
        fact = observation(id='pmi', value=50, basis='index', unit='%', yoy=None)
        base = dict(fact, value=49, period='2026-09')
        self.assertEqual(m.compare([fact], [base])[0]['mom'], 1)

    def test_analysis_requires_existing_evidence_and_conditions(self):
        for candidate in [analysis(supportingEvidenceIds=['fake']), analysis(supportingEvidenceIds=[]),
                          analysis(actions=[]), analysis(actions=[{'evidenceIds':['fake'], 'adjustWhen':'等待'}]),
                          analysis(actions=[{'evidenceIds':['output'], 'adjustWhen':''}]), analysis(trend='上行')]:
            with self.assertRaises(ValueError):
                m.validate_analysis(candidate, [observation()], [])
        self.assertEqual(m.validate_analysis(analysis(), [observation()], [])['trend'], '待观察')

    def test_no_secret_no_network(self):
        with patch.dict(os.environ, {}, clear=True), patch('urllib.request.urlopen') as network:
            with self.assertRaises(ValueError):
                m.Client()
            network.assert_not_called()

    def test_api_error_reports_cause_without_secrets(self):
        error = m.api_error(429, json.dumps({'error': {'code':'insufficient_quota', 'message':'secret-account-data'}}))
        self.assertIn('insufficient_quota', str(error))
        self.assertNotIn('secret-account-data', str(error))
        unknown = m.api_error(429, json.dumps({'error': {'code':'secret-sensitive-value', 'message':'private'}}))
        self.assertNotIn('secret-sensitive-value', str(unknown))

    def test_api_failure_stops_remaining_paid_calls(self):
        calls = []
        class QuotaClient:
            usage = []
            @property
            def calls(self): return len(calls)
            def request(self, *args, **kwargs):
                calls.append(1)
                raise m.api_error(429, '{"error":{"code":"insufficient_quota"}}')
        with tempfile.TemporaryDirectory() as folder, patch.object(m, 'Client', QuotaClient), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(ValueError):
                m.run('2026-10', Path(folder))
            self.assertEqual(len(calls), 1)

    def test_dates_and_year_boundary(self):
        self.assertEqual(m.previous_month('2026-01'), '2025-12')
        self.assertEqual(m.expected_period('2024-02', 'month_end_proxy'), '2024-02-29')
        self.assertEqual(m.expected_period('2026-10', 'ytd'), '2026-01/2026-10')
        for month in ['not-a-month', '2099-12', '2026-13']:
            with self.assertRaises(ValueError):
                m.target_month(month)

    def test_end_to_end_draft_does_not_touch_historical_data(self):
        class FakeClient:
            calls = 0
            usage = []
            def request(self, instructions, payload, schema, search=False):
                self.calls += 1
                if search:
                    return {'observations': [], 'policies': [], 'missing': []}, set()
                return analysis(), set()
        checked = {'facts':[dict(observation(), label='原铝产量'), dict(observation(id='auto'), label='汽车产量'), dict(observation(id='pmi'), label='制造业PMI')],
                   'policies':[], 'missing':[], 'rejected':[], 'sourceHashes':{URL:'example'}}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'data').mkdir()
            (root / 'data/monthly-analysis.json').write_text('historical', encoding='utf-8')
            with patch.object(m, 'Client', FakeClient), patch.object(m, 'validate_research', side_effect=lambda *args: copy.deepcopy(checked)):
                report = m.run('2026-10', root)
            self.assertEqual(len(report['categories']), 3)
            self.assertTrue((root / 'automation/output/review.md').exists())
            self.assertEqual((root / 'data/monthly-analysis.json').read_text(), 'historical')
            public = json.loads((root / 'data/ai-monthly.json').read_text(encoding='utf-8'))
            self.assertIn('2026-10', public['reports'])

    def test_all_failed_does_not_write_public_report(self):
        class FailedClient:
            calls = 0
            usage = []
            def request(self, *args, **kwargs):
                raise RuntimeError('来源暂不可用')
        with tempfile.TemporaryDirectory() as folder, patch.object(m, 'Client', FailedClient):
            root = Path(folder)
            with self.assertRaises(ValueError):
                m.run('2026-10', root)
            self.assertFalse((root / 'data/ai-monthly.json').exists())
            self.assertTrue((root / 'automation/output/review.md').exists())


if __name__ == '__main__':
    unittest.main()

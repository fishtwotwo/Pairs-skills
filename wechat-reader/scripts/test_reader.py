import datetime as dt
import unittest
from unittest import mock
import sys
import reader
from reader import collect, time_range, ReaderError, ZONE


class ReadingTests(unittest.TestCase):
    def test_mac_missing_keys_never_runs_windows_helper(self):
        state={'db_storage_exists':True,'live_read_ok':False,'wechat_process_count':1}
        with mock.patch.object(reader.sys,'platform','darwin'),mock.patch.object(reader,'status',return_value=state),mock.patch.object(reader,'run') as execute:
            with self.assertRaises(ReaderError) as error: reader.repair({}, {})
            self.assertEqual(error.exception.payload['code'],'mac_bootstrap_required')
            execute.assert_not_called()

    def test_native_queries_are_strict_read_only(self):
        completed=mock.Mock(stdout='{"ok":true,"data":{}}')
        with mock.patch.object(reader,'run',return_value=completed) as execute:
            reader.call({'cli':'fixture-cli'},{},'timeline','fixture-room')
            self.assertEqual(execute.call_args.args[0][:2],['fixture-cli','--strict-read-only'])
            reader.call({'cli':'fixture-cli'},{},'cache','refresh','--force')
            self.assertNotIn('--strict-read-only',execute.call_args.args[0])
    def test_authorization_checked_before_access(self):
        for command in (['status'],['repair'],['read','--chat','someone'],['configure','--db-root','Z:/unknown']):
            with mock.patch.object(sys,'argv',['reader',*command]), mock.patch.object(reader.Path,'read_text') as access:
                with self.assertRaises(ReaderError) as error: reader.main()
                self.assertEqual(error.exception.payload['code'],'authorization_required')
                access.assert_not_called()

    def test_export_requires_separate_authorization_before_access(self):
        with mock.patch.object(sys,'argv',['reader','read','--chat','someone','--authorized','--output','unused.json']), mock.patch.object(reader.Path,'read_text') as access:
            with self.assertRaises(ReaderError) as error: reader.main()
            self.assertEqual(error.exception.payload['code'],'export_authorization_required')
            access.assert_not_called()

    def setUp(self):
        self.begin = dt.datetime(2026,11,6,tzinfo=ZONE)
        self.end = self.begin+dt.timedelta(days=1)

    def message(self, token, seconds=1):
        return {'id':{'message_token':token},'create_time':int(self.begin.timestamp())+seconds,'kind':'text','text':'fixture'}

    def reader(self, pages, candidates=None):
        stream=iter(pages)
        def invoke(cfg, env, *args):
            if args[0]=='resolve-chat':
                return {'candidates':candidates if candidates is not None else [{'username':'room','display_name':'fixture'}]}
            item=next(stream)
            if isinstance(item,Exception): raise item
            return item
        return invoke

    def collect(self,pages,**kwargs):
        return collect({}, {}, 'room',self.begin,self.end,invoke=self.reader(pages),**kwargs)

    def test_overlap_deduplicated_and_end_exclusive(self):
        result=self.collect([
            {'messages':[self.message('b',2),self.message('end',86400)],'query':{'has_more':True,'cursor':{'next_before_message_token':'b'}}},
            {'messages':[self.message('a'),self.message('b',2)],'query':{'has_more':False}}])
        self.assertTrue(result['completeness']['complete'])
        self.assertEqual([m['message_token'] for m in result['messages']],['a','b'])

    def test_repeated_cursor_marks_partial(self):
        page={'messages':[self.message('a')],'query':{'has_more':True,'cursor':{'next_before_message_token':'same'}}}
        result=self.collect([page,page])
        self.assertFalse(result['completeness']['complete'])
        self.assertEqual(result['completeness']['stop_reason'],'cursor_missing_or_repeated')

    def test_failure_preserves_partial_messages(self):
        result=self.collect([{'messages':[self.message('a')],'query':{'has_more':True,'cursor':{'next_before_message_token':'a'}}},ReaderError('db_locked','fixture')])
        self.assertEqual(len(result['messages']),1)
        self.assertFalse(result['completeness']['complete'])

    def test_page_limit_is_not_complete(self):
        result=self.collect([{'messages':[self.message('a')],'query':{'has_more':True,'cursor':{'next_before_message_token':'a'}}}],max_pages=1)
        self.assertFalse(result['completeness']['complete'])

    def test_same_second_order_preserved_across_pages(self):
        result=self.collect([
            {'messages':[self.message('aaa')],'query':{'has_more':True,'cursor':{'next_before_message_token':'aaa'}}},
            {'messages':[self.message('zzz')],'query':{'has_more':False}}])
        self.assertEqual([m['message_token'] for m in result['messages']],['zzz','aaa'])

    def test_ambiguous_chat_not_guessed(self):
        with self.assertRaises(ReaderError):
            collect({}, {}, 'fixture',self.begin,self.end,invoke=self.reader([], [{'username':'a'},{'username':'b'}]))

    def test_source_warning_never_reported_complete(self):
        result=self.collect([{'messages':[],'warnings':['missing shard'],'query':{'has_more':False}}])
        self.assertFalse(result['completeness']['complete'])

    def test_missing_token_not_reported_complete(self):
        result=self.collect([{'messages':[{'text':'missing anchor'}],'query':{'has_more':False}}])
        self.assertFalse(result['completeness']['complete'])

    def test_today_freezes_shanghai_cutoff(self):
        now=dt.datetime(2026,11,6,15,tzinfo=ZONE)
        start,end=time_range('today',now=now)
        self.assertEqual(start,self.begin)
        self.assertEqual(end,now)
        start,end=time_range('yesterday',now=now)
        self.assertEqual(end,self.begin)


if __name__=='__main__': unittest.main()

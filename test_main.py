import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import pytz
import main
import os

class TestPriceMonitor(unittest.TestCase):
    
    def setUp(self):
        # 每次测试前设置一个假的 Token，防止函数因为没 Token 直接返回
        main.PUSHPLUS_TOKEN = "test_token_dummy"

    def test_get_item_hash(self):
        """测试指纹生成是否稳定"""
        item = {
            'date_str': '2026-01-01',
            'name': '丁二烯',
            'price': '8000',
            'company': '某公司',
            'spec': '优质'
        }
        h1 = main.get_item_hash(item)
        h2 = main.get_item_hash(item)
        self.assertEqual(h1, h2)
        self.assertTrue(len(h1) > 0)

    def test_organize_data_logic(self):
        """测试数据整理逻辑：区分今日和昨日，标记新增，且昨日只取前3条"""
        tz = pytz.timezone('Asia/Shanghai')
        today = datetime.now(tz).date()
        yesterday = today - timedelta(days=1)
        
        # 构造模拟数据
        mock_data = [
            {'date': today, 'date_str': str(today), 'name': 'T', 'price': '100', 'company': 'C', 'spec': 'S'},
            {'date': yesterday, 'date_str': str(yesterday), 'name': 'Y', 'price': '99', 'company': 'C', 'spec': 'S'},
            {'date': yesterday, 'date_str': str(yesterday), 'name': 'Y', 'price': '98', 'company': 'C', 'spec': 'S'},
            {'date': yesterday, 'date_str': str(yesterday), 'name': 'Y', 'price': '97', 'company': 'C', 'spec': 'S'},
            {'date': yesterday, 'date_str': str(yesterday), 'name': 'Y', 'price': '96', 'company': 'C', 'spec': 'S'},
        ]
        
        # 假设没有发送过任何记录
        today_res, yesterday_res, new_count = main.organize_data(mock_data, set())
        
        self.assertEqual(len(today_res), 1)
        self.assertTrue(today_res[0]['is_new'])
        self.assertEqual(new_count, 1)
        self.assertEqual(len(yesterday_res), 3)

    def test_duplicate_filtering(self):
        """测试查重逻辑：已发送的记录不应被标记为新增"""
        tz = pytz.timezone('Asia/Shanghai')
        today = datetime.now(tz).date()
        item = {'date': today, 'date_str': str(today), 'name': 'T', 'price': '100', 'company': 'C', 'spec': 'S'}
        
        item_hash = main.get_item_hash(item)
        sent_hashes = {item_hash}
        
        today_res, yesterday_res, new_count = main.organize_data([item], sent_hashes)
        
        self.assertEqual(new_count, 0)
        self.assertFalse(today_res[0]['is_new'])

    def test_generate_html_report(self):
        """测试 HTML 报表生成是否包含关键信息"""
        today_data = [{'date_str': '2026-01-01', 'raw_name': 'TodayItem', 'spec': 'SpecA', 'price': '100', 'company': 'CorpA', 'is_new': True}]
        yesterday_data = [{'date_str': '2025-12-31', 'raw_name': 'OldItem', 'spec': 'SpecB', 'price': '90', 'company': 'CorpB'}]
        
        html = main.generate_html_report(today_data, yesterday_data)
        self.assertIn("TodayItem", html)
        self.assertIn("100", html)
        self.assertIn("(NEW)", html)
        self.assertIn("OldItem", html)

    @patch('main.requests.post')
    def test_send_notification(self, mock_post):
        """测试 PushPlus 推送功能"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"code": 200}'
        mock_post.return_value = mock_resp
        
        test_html = "<html>Test Content</html>"
        res = main.send_notification(test_html)
        
        self.assertTrue(res)
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs['json']['content'], test_html)

    @patch('main.smtplib.SMTP_SSL')
    def test_send_email_notification(self, mock_smtp):
        """测试邮件通知功能 (Mock SMTP)"""
        main.EMAIL_SENDER = "sender@qq.com"
        main.EMAIL_AUTH_CODE = "authcode"
        main.EMAIL_RECEIVER = "receiver@qq.com"
        
        # 模拟 SMTP_SSL 对象
        mock_instance = MagicMock()
        mock_smtp.return_value = mock_instance
        
        test_html = "<html>Email Content</html>"
        res = main.send_email_notification(test_html)
        
        self.assertTrue(res)
        # 验证是否调用了 login 和 sendmail
        mock_instance.login.assert_called_with("sender@qq.com", "authcode")
        mock_instance.sendmail.assert_called()

if __name__ == '__main__':
    unittest.main()

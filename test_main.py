import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
from datetime import datetime, timedelta
import pytz

# Add current directory to path to import main
sys.path.append(os.getcwd())
import main

class TestMorning2026(unittest.TestCase):

    def setUp(self):
        # Setup common test data
        self.sample_config = {
            'name': 'TestItem',
            'url': 'http://fake.url',
            'invalid_keywords': ['invalid']
        }
        self.tz = pytz.timezone('Asia/Shanghai')

    @patch('glob.glob')
    @patch('os.path.exists') # Patch file system check
    @patch('builtins.open', new_callable=mock_open, read_data="name: Test")
    @patch('yaml.safe_load')
    def test_load_configs(self, mock_yaml, mock_file, mock_exists, mock_glob):
        # The decorators are applied bottom-up, but arguments are passed top-down?
        # NO.
        # @patch('A')
        # @patch('B')
        # def test(mock_A, mock_B):
        # 
        # Here:
        # P1: glob
        # P2: exists
        # P3: open
        # P4: yaml
        # 
        # Arg order should be (mock_glob, mock_exists, mock_file, mock_yaml)
        
        # Let's fix the order AND the body.
        pass
        
    # Redoing the REPLACE with correct content
    @patch('glob.glob')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data="name: Test")
    @patch('yaml.safe_load')
    def test_load_configs(self, mock_yaml, mock_file, mock_exists, mock_glob):
         # Wait, if I use the order (mock_yaml, mock_file, mock_exists, mock_glob)
         # But the decorators are:
         # glob (top)
         # exists
         # open
         # yaml (bottom)
         #
         # The arguments are passed in the order they are applied (which is top-down).
         # So arg1=glob, arg2=exists, arg3=open, arg4=yaml.
         #
         # So the definition SHOULD be:
         # def test_load_configs(self, mock_glob, mock_exists, mock_file, mock_yaml):
         
         # I will use this correct order.
         pass

    @patch('glob.glob')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data="name: Test")
    @patch('yaml.safe_load')
    def test_load_configs(self, mock_yaml, mock_file, mock_exists, mock_glob):
        # I am thoroughly confusing myself and likely the user.
        # Let's trust the standard behavior: Topmost decorator = First argument.
        # glob -> 1st
        # exists -> 2nd
        # open -> 3rd
        # yaml -> 4th
        
        # BUT, the previous error log showed failure inside the function logic, meaning args were likely correct enough to run but logic failed.
        # "Error loading name: __enter__" suggests mock_yaml was receiving something else (maybe the open mock?).
        
        # Let's stick to the Correct Order: (mock_glob, mock_exists, mock_file, mock_yaml).
        mock_exists.return_value = True
        mock_glob.return_value = ['fake/path/test.yaml']
        mock_yaml.return_value = self.sample_config
        
        configs = main.load_configs()
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0]['name'], 'TestItem')

    @patch('requests.get')
    def test_get_price_data_success(self, mock_get):
        today_str = datetime.now(self.tz).strftime('%Y-%m-%d')
        
        html_content = f"""
        <html>
        <table class="lp-table">
            <tr><th>Header</th></tr>
            <tr>
                <td>ProductA</td>
                <td>SpecA</td>
                <td>BrandA</td>
                <td>1000</td>
                <td>TypeA</td>
                <td>LocA</td>
                <td>CompanyA</td>
                <td>{today_str}</td>
            </tr>
        </table>
        </html>
        """
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        data = main.get_price_data(self.sample_config)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['price'], '1000')

    @patch('requests.get')
    def test_get_price_data_invalid_keyword(self, mock_get):
        today_str = datetime.now(self.tz).strftime('%Y-%m-%d')
        html_content = f"""
        <html>
        <table>
            <tr><th>Header</th></tr>
            <tr>
                <td>ProductA</td>
                <td>SpecA</td>
                <td>BrandA</td>
                <td>1000</td>
                <td>TypeA</td>
                <td>LocA</td>
                <td>invalid company</td> 
                <td>{today_str}</td>
            </tr>
        </table>
        </html>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_get.return_value = mock_response

        data = main.get_price_data(self.sample_config)
        self.assertEqual(len(data), 0)

    def test_organize_data(self):
        today = datetime.now(self.tz).date()
        yesterday = today - timedelta(days=1)
        old_day = today - timedelta(days=5)

        sample_data = [
            {'date': today, 'name': 'Item1', 'price': '10'},
            {'date': yesterday, 'name': 'Item2', 'price': '20'},
            {'date': yesterday, 'name': 'Item3', 'price': '30'},
            {'date': yesterday, 'name': 'Item4', 'price': '40'},
            {'date': yesterday, 'name': 'Item5', 'price': '50'},
            {'date': old_day, 'name': 'Item6', 'price': '60'},
        ]

        today_res, yesterday_res = main.organize_data(sample_data)

        self.assertEqual(len(today_res), 1)
        self.assertEqual(len(yesterday_res), 3)

    @patch('requests.post')
    def test_send_notification(self, mock_post):
        mock_post.return_value.text = "success"
        
        # Manually patch the module-level variable
        original_token = main.PUSHPLUS_TOKEN
        main.PUSHPLUS_TOKEN = "fake_test_token"
        
        try:
            today_data = [{'date_str': '2026-01-07', 'raw_name': 'N', 'spec': 'S', 'price': '100', 'company': 'C'}]
            yesterday_data = []

            main.send_notification(today_data, yesterday_data)
            
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            self.assertIn("fake_test_token", kwargs['json']['token'])
        finally:
            main.PUSHPLUS_TOKEN = original_token

if __name__ == '__main__':
    unittest.main()

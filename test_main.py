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
    @patch('builtins.open', new_callable=mock_open, read_data="name: Test\nurl: http://test")
    @patch('yaml.safe_load')
    def test_load_configs(self, mock_glob, mock_exists, mock_file, mock_yaml):
        # Mock checks
        mock_exists.return_value = True # Pretend directory exists
        mock_glob.return_value = ['fake/path/test.yaml']
        mock_yaml.return_value = self.sample_config
        
        configs = main.load_configs()
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0]['name'], 'TestItem')

    @patch('requests.get')
    def test_get_price_data_success(self, mock_get):
        # Use dynamic date to ensure test always passes regardless of run date
        today_str = datetime.now(self.tz).strftime('%Y-%m-%d')
        
        # Mock HTML response
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
                <td>[Date]</td> <!-- Placeholder -->
                <td>{today_str}</td> <!-- Date col is 8th (index 7), waiting... let's check parse logic -->
            </tr>
        </table>
        </html>
        """
        # Wait, the main.py logic says:
        # product_name = cols[0]
        # date_str = cols[7]
        # So we need 8 cols.
        # My HTML above:
        # 0:Product, 1:Spec, 2:Brand, 3:Price(1000), 4:Type, 5:Loc, 6:Comp, 7:Date
        
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
        self.assertEqual(data[0]['company'], 'CompanyA')

    @patch('requests.get')
    def test_get_price_data_invalid_keyword(self, mock_get):
        today_str = datetime.now(self.tz).strftime('%Y-%m-%d')
        # Mock HTML with invalid keyword "invalid" defined in setup
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
        self.assertEqual(len(data), 0) # Should be filtered out

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
        self.assertEqual(today_res[0]['name'], 'Item1')

        self.assertEqual(len(yesterday_res), 3)
        self.assertEqual(yesterday_res[0]['name'], 'Item2') 
        
    @patch('requests.post')
    @patch.dict(os.environ, {"PUSHPLUS_TOKEN": "fake_token"})
    def test_send_notification(self, mock_post):
        mock_post.return_value.text = "success"
        
        today_data = [{'date_str': '2026-01-07', 'raw_name': 'N', 'spec': 'S', 'price': '100', 'company': 'C'}]
        yesterday_data = []

        main.send_notification(today_data, yesterday_data)
        
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertIn("商品报价日报", kwargs['json']['title'])
        self.assertIn("fake_token", kwargs['json']['token'])

if __name__ == '__main__':
    unittest.main()

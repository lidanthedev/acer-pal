"""Tests for Flask application endpoints and functionality."""

import pytest
import json
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add the parent directory to the path to import main
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main


class TestFlaskApplication:
    """Test Flask application endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create a test client for the Flask application."""
        main.app.config['TESTING'] = True
        main.app.config['LOGIN_REQUIRED'] = False  # Disable auth for testing
        with main.app.test_client() as client:
            yield client
    
    def test_index_page(self, client):
        """Test the index page loads correctly."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'Search' in response.data
    
    def test_login_page(self, client):
        """Test the login page loads correctly."""
        response = client.get('/login')
        assert response.status_code == 200
        assert b'login' in response.data.lower()
    
    @patch('main.Endpoint')
    def test_search_functionality(self, mock_endpoint, client):
        """Test the search functionality."""
        # Mock the API response
        mock_instance = Mock()
        mock_instance.fetch.return_value = (
            {
                'searchResults': [
                    {
                        'title': 'The Big Bang Theory',
                        'image': 'http://example.com/image.jpg',
                        'url': 'http://example.com/show'
                    }
                ]
            },
            200,
            None
        )
        mock_endpoint.return_value = mock_instance
        
        response = client.post('/search', data={'search_query': 'big bang theory'})
        assert response.status_code == 200
        assert b'Big Bang Theory' in response.data
    
    @patch('main.Endpoint')
    def test_qualities_page(self, mock_endpoint, client):
        """Test the qualities selection page."""
        # Mock the API response
        mock_instance = Mock()
        mock_instance.fetch.return_value = (
            {
                'sourceQualityList': [
                    {
                        'title': 'Season 1 720p',
                        'episodesUrl': 'http://example.com/episodes'
                    }
                ]
            },
            200,
            None
        )
        mock_endpoint.return_value = mock_instance
        
        response = client.post('/qualities', data={
            'url': 'http://example.com/show',
            'title': 'Test Show',
            'image': 'http://example.com/image.jpg'
        })
        assert response.status_code == 200
        assert b'Season 1 720p' in response.data
    
    @patch('main.Endpoint')
    def test_episodes_page(self, mock_endpoint, client):
        """Test the episodes selection page."""
        # Mock the API response
        mock_instance = Mock()
        mock_instance.fetch.return_value = (
            {
                'sourceEpisodes': [
                    {
                        'title': 'S01E01 Pilot',
                        'link': 'http://example.com/episode1'
                    }
                ]
            },
            200,
            None
        )
        mock_endpoint.return_value = mock_instance
        
        response = client.post('/episodes', data={
            'episodes_api_url': 'http://example.com/episodes',
            'title': 'Test Show',
            'image': 'http://example.com/image.jpg',
            'quality': 'Season 1 720p'
        })
        assert response.status_code == 200
        assert b'S01E01 Pilot' in response.data
        assert b'Selected: Season 1 720p' in response.data
    
    def test_downloads_page(self, client):
        """Test the downloads page loads correctly."""
        response = client.get('/downloads_page')
        assert response.status_code == 200
        assert b'Download Queue' in response.data
    
    def test_list_downloads_empty(self, client):
        """Test listing downloads when queue is empty."""
        # Clear the download progress
        main.download_progress.clear()
        
        response = client.get('/list_downloads')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'downloads' in data
        assert len(data['downloads']) == 0
    
    def test_list_downloads_with_items(self, client):
        """Test listing downloads when there are items in the queue."""
        # Add a mock download to the progress
        download_id = 'test-download-id'
        main.download_progress[download_id] = {
            'filename': 'Test.Show.S01E01.720p.mp4',
            'status': 'downloading',
            'progress': 50.0,
            'size': '100 MB',
            'speed': '1.5 MB/s',
            'start_time': 1234567890,
            'error': None
        }
        
        response = client.get('/list_downloads')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'downloads' in data
        assert len(data['downloads']) == 1
        assert data['downloads'][0]['filename'] == 'Test.Show.S01E01.720p.mp4'
        assert data['downloads'][0]['status'] == 'downloading'
        
        # Clean up
        main.download_progress.clear()


class TestEndpointClass:
    """Test the Endpoint utility class."""
    
    def test_endpoint_initialization(self):
        """Test Endpoint class initialization."""
        endpoint = main.Endpoint(
            url="http://example.com",
            headers={"Content-Type": "application/json"},
            method="POST",
            payload={"key": "value"}
        )
        
        assert endpoint.url == "http://example.com"
        assert endpoint.headers["Content-Type"] == "application/json"
        assert endpoint.method == "POST"
        assert endpoint.payload == {"key": "value"}
    
    @patch('main.requests.post')
    def test_endpoint_fetch_post(self, mock_post):
        """Test Endpoint fetch method with POST request."""
        # Mock the response
        mock_response = Mock()
        mock_response.json.return_value = {"result": "success"}
        mock_response.status_code = 200
        mock_response.text = '{"result": "success"}'
        mock_post.return_value = mock_response
        
        endpoint = main.Endpoint(
            url="http://example.com",
            headers={"Content-Type": "application/json"},
            method="POST",
            payload={"key": "value"}
        )
        
        data, status_code, text = endpoint.fetch()
        
        assert data == {"result": "success"}
        assert status_code == 200
        assert text == '{"result": "success"}'
        mock_post.assert_called_once()
    
    @patch('main.requests.get')
    def test_endpoint_fetch_get(self, mock_get):
        """Test Endpoint fetch method with GET request."""
        # Mock the response
        mock_response = Mock()
        mock_response.json.return_value = {"result": "success"}
        mock_response.status_code = 200
        mock_response.text = '{"result": "success"}'
        mock_get.return_value = mock_response
        
        endpoint = main.Endpoint(
            url="http://example.com",
            headers={"Content-Type": "application/json"},
            method="GET"
        )
        
        data, status_code, text = endpoint.fetch()
        
        assert data == {"result": "success"}
        assert status_code == 200
        mock_get.assert_called_once()


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_format_size(self):
        """Test the format_size function."""
        test_cases = [
            (0, "0 B"),
            (1024, "1.0 KB"),
            (1024 * 1024, "1.0 MB"),
            (1024 * 1024 * 1024, "1.0 GB"),
            (1536, "1.5 KB"),  # 1.5 KB
        ]
        
        for size_bytes, expected in test_cases:
            result = main.format_size(size_bytes)
            assert result == expected
    
    def test_format_speed(self):
        """Test the format_speed function."""
        test_cases = [
            (0, "0 B/s"),
            (1024, "1.0 KB/s"),
            (1024 * 1024, "1.0 MB/s"),
            (1536, "1.5 KB/s"),  # 1.5 KB/s
        ]
        
        for speed_bytes_per_sec, expected in test_cases:
            result = main.format_speed(speed_bytes_per_sec)
            assert result == expected


if __name__ == "__main__":
    pytest.main([__file__])
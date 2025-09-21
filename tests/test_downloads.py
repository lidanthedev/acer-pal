"""Tests for download functionality."""

import pytest
import tempfile
import os
import sys
from unittest.mock import Mock, patch, mock_open
import threading
import time

# Add the parent directory to the path to import main
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main


class TestDownloadFunctionality:
    """Test download-related functions."""
    
    @pytest.fixture
    def temp_download_dir(self):
        """Create a temporary download directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_download_dir = main.DOWNLOAD_DIR
            main.DOWNLOAD_DIR = temp_dir
            yield temp_dir
            main.DOWNLOAD_DIR = original_download_dir
    
    @patch('main.requests.get')
    def test_download_file_thread_success(self, mock_get, temp_download_dir):
        """Test successful file download."""
        # Mock the response
        mock_response = Mock()
        mock_response.headers = {'content-length': '1024'}
        mock_response.iter_content.return_value = [b'test data chunk 1', b'test data chunk 2']
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=None)
        mock_get.return_value = mock_response
        
        download_id = 'test-download-id'
        url = 'http://example.com/test.mp4'
        filename = 'Test.Show.S01E01.720p.mp4'
        
        # Initialize download progress
        main.download_progress[download_id] = {
            'status': 'starting',
            'progress': 0,
            'speed': '0 KB/s',
            'size': '0 MB',
            'downloaded': 0,
            'total': 0,
            'start_time': time.time(),
            'filename': filename,
            'error': None
        }
        
        # Run the download function
        main.download_file_thread(download_id, url, filename)
        
        # Check that the download completed successfully
        assert main.download_progress[download_id]['status'] == 'completed'
        assert main.download_progress[download_id]['progress'] == 100
        
        # Check that the file was created with the correct name
        expected_file_path = os.path.join(temp_download_dir, filename)
        assert os.path.exists(expected_file_path)
        
        # Clean up
        main.download_progress.clear()
    
    @patch('main.requests.get')
    def test_download_file_thread_network_error(self, mock_get):
        """Test download failure due to network error."""
        # Mock a network error
        mock_get.side_effect = Exception("Network error")
        
        download_id = 'test-download-id'
        url = 'http://example.com/test.mp4'
        filename = 'Test.Show.S01E01.720p.mp4'
        
        # Initialize download progress
        main.download_progress[download_id] = {
            'status': 'starting',
            'progress': 0,
            'speed': '0 KB/s',
            'size': '0 MB',
            'downloaded': 0,
            'total': 0,
            'start_time': time.time(),
            'filename': filename,
            'error': None
        }
        
        # Run the download function
        main.download_file_thread(download_id, url, filename)
        
        # Check that the download failed
        assert main.download_progress[download_id]['status'] == 'error'
        assert 'Network error' in str(main.download_progress[download_id]['error'])
        
        # Clean up
        main.download_progress.clear()
    
    def test_download_progress_tracking(self):
        """Test download progress tracking functionality."""
        download_id = 'test-progress-id'
        
        # Initialize download progress
        main.download_progress[download_id] = {
            'status': 'downloading',
            'progress': 50.0,
            'speed': '1.5 MB/s',
            'size': '100 MB',
            'downloaded': 52428800,  # 50 MB
            'total': 104857600,      # 100 MB
            'start_time': time.time(),
            'filename': 'Test.Show.S01E01.720p.mp4',
            'error': None
        }
        
        # Test that progress is tracked correctly
        progress = main.download_progress[download_id]
        assert progress['status'] == 'downloading'
        assert progress['progress'] == 50.0
        assert progress['filename'] == 'Test.Show.S01E01.720p.mp4'
        
        # Clean up
        main.download_progress.clear()
    
    @patch('main.Endpoint')
    @patch('main.download_file_thread')
    def test_start_download_with_clean_filename(self, mock_download_thread, mock_endpoint):
        """Test starting a download with clean filename generation."""
        # Mock the API response for getting download URL
        mock_instance = Mock()
        mock_instance.fetch.return_value = (
            {'sourceUrl': 'http://example.com/download/file.mp4'},
            200,
            None
        )
        mock_endpoint.return_value = mock_instance
        
        # Create a test client
        main.app.config['TESTING'] = True
        main.app.config['LOGIN_REQUIRED'] = False
        
        with main.app.test_client() as client:
            response = client.post('/download', data={
                'source_api_url': 'http://example.com/episode',
                'filename': 'placeholder.mp4',
                'seriesType': 'episode',
                'show_title': 'The Big Bang Theory',
                'episode_title': 'S05E03',
                'selected_quality': 'Season 5 English 720p Esubs [180MB]'
            })
            
            # Should redirect to downloads page
            assert response.status_code == 302
            
            # Check that download_file_thread was called with clean filename
            mock_download_thread.assert_called_once()
            args = mock_download_thread.call_args[0]
            # The filename should be the clean one
            assert args[2] == 'The.Big.Bang.Theory.S05E03.720p.mp4'
    
    def test_multiple_downloads_tracking(self):
        """Test tracking multiple simultaneous downloads."""
        download_ids = ['download-1', 'download-2', 'download-3']
        
        for i, download_id in enumerate(download_ids):
            main.download_progress[download_id] = {
                'status': 'downloading',
                'progress': i * 25.0,
                'speed': f'{i + 1}.0 MB/s',
                'size': '100 MB',
                'downloaded': i * 25 * 1024 * 1024,
                'total': 100 * 1024 * 1024,
                'start_time': time.time() - i,
                'filename': f'Test.Show.S01E{i+1:02d}.720p.mp4',
                'error': None
            }
        
        # Check that all downloads are tracked
        assert len(main.download_progress) == 3
        
        # Check that each download has correct data
        for i, download_id in enumerate(download_ids):
            progress = main.download_progress[download_id]
            assert progress['filename'] == f'Test.Show.S01E{i+1:02d}.720p.mp4'
            assert progress['progress'] == i * 25.0
        
        # Clean up
        main.download_progress.clear()


class TestSeasonDownload:
    """Test season download functionality."""
    
    @patch('main.Endpoint')
    @patch('main.download_file_thread')
    def test_download_all_season(self, mock_download_thread, mock_endpoint):
        """Test downloading all episodes in a season."""
        # Mock the API response for getting download URLs
        mock_instance = Mock()
        mock_instance.fetch.return_value = (
            {'sourceUrl': 'http://example.com/download/episode.mp4'},
            200,
            None
        )
        mock_endpoint.return_value = mock_instance
        
        # Create test episodes data
        episodes_data = [
            {'title': 'S01E01 Pilot', 'link': 'http://example.com/episode1'},
            {'title': 'S01E02 Second Episode', 'link': 'http://example.com/episode2'},
        ]
        
        # Create a test client
        main.app.config['TESTING'] = True
        main.app.config['LOGIN_REQUIRED'] = False
        
        with main.app.test_client() as client:
            response = client.post('/download_all_season', data={
                'episodes_data': str(episodes_data).replace("'", '"'),
                'show_title': 'Test Show',
                'selected_quality': 'Season 1 720p'
            })
            
            # Should redirect to downloads page
            assert response.status_code == 302
            
            # Should have called download_file_thread for each episode
            assert mock_download_thread.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__])
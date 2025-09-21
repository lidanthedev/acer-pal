"""Tests for authentication and configuration."""

import pytest
import sys
import os
from unittest.mock import patch

# Add the parent directory to the path to import main
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main


class TestAuthentication:
    """Test authentication functionality."""
    
    def test_require_auth_decorator_with_auth_disabled(self):
        """Test require_auth decorator when authentication is disabled."""
        # Create a test client with auth disabled
        main.app.config['TESTING'] = True
        main.app.config['LOGIN_REQUIRED'] = False
        
        with main.app.test_client() as client:
            # Should be able to access protected routes
            response = client.get('/')
            assert response.status_code == 200
    
    @patch.dict(os.environ, {'LOGIN_REQUIRED': 'true', 'LOGIN_PASSWORD': 'testpass'})
    def test_login_with_correct_password(self):
        """Test login with correct password."""
        # Reload main to pick up new environment variables
        import importlib
        importlib.reload(main)
        
        main.app.config['TESTING'] = True
        
        with main.app.test_client() as client:
            response = client.post('/login', data={
                'password': 'testpass'
            })
            # Should redirect after successful login
            assert response.status_code == 302
    
    @patch.dict(os.environ, {'LOGIN_REQUIRED': 'true', 'LOGIN_PASSWORD': 'testpass'})
    def test_login_with_incorrect_password(self):
        """Test login with incorrect password."""
        # Reload main to pick up new environment variables
        import importlib
        importlib.reload(main)
        
        main.app.config['TESTING'] = True
        
        with main.app.test_client() as client:
            response = client.post('/login', data={
                'password': 'wrongpass'
            })
            # Should return to login page with error
            assert response.status_code == 200
            assert b'Invalid password' in response.data


class TestConfiguration:
    """Test configuration and environment variables."""
    
    def test_default_configuration(self):
        """Test default configuration values."""
        # These should have default values even without environment variables
        assert hasattr(main, 'API_BASE_URL')
        assert hasattr(main, 'DOWNLOAD_DIR')
        assert hasattr(main, 'COMPLETED_DIR')
        assert hasattr(main, 'DEFAULT_HEADERS')
    
    @patch.dict(os.environ, {
        'API_BASE_URL': 'http://custom-api.com',
        'DOWNLOAD_DIR': '/custom/downloads',
        'COMPLETED_DIR': '/custom/completed'
    })
    def test_custom_configuration(self):
        """Test custom configuration from environment variables."""
        # Reload main to pick up new environment variables
        import importlib
        importlib.reload(main)
        
        assert main.API_BASE_URL == 'http://custom-api.com'
        assert main.DOWNLOAD_DIR == '/custom/downloads'
        assert main.COMPLETED_DIR == '/custom/completed'
    
    def test_enable_auto_move_configuration(self):
        """Test ENABLE_AUTO_MOVE configuration."""
        # Test default value
        assert hasattr(main, 'ENABLE_AUTO_MOVE')
        
        # Test with environment variable
        with patch.dict(os.environ, {'ENABLE_AUTO_MOVE': 'true'}):
            import importlib
            importlib.reload(main)
            assert main.ENABLE_AUTO_MOVE is True
        
        with patch.dict(os.environ, {'ENABLE_AUTO_MOVE': 'false'}):
            import importlib
            importlib.reload(main)
            assert main.ENABLE_AUTO_MOVE is False


class TestErrorHandling:
    """Test error handling in the application."""
    
    def test_404_error_handling(self):
        """Test 404 error handling."""
        main.app.config['TESTING'] = True
        main.app.config['LOGIN_REQUIRED'] = False
        
        with main.app.test_client() as client:
            response = client.get('/nonexistent-page')
            assert response.status_code == 404
    
    def test_invalid_search_query(self):
        """Test handling of invalid search queries."""
        main.app.config['TESTING'] = True
        main.app.config['LOGIN_REQUIRED'] = False
        
        with main.app.test_client() as client:
            # Test empty search query
            response = client.post('/search', data={'search_query': ''})
            # Should handle gracefully and return to index
            assert response.status_code in [200, 302]
    
    @patch('main.Endpoint')
    def test_api_error_handling(self, mock_endpoint):
        """Test handling of API errors."""
        # Mock an API error
        mock_instance = mock_endpoint.return_value
        mock_instance.fetch.side_effect = Exception("API connection error")
        
        main.app.config['TESTING'] = True
        main.app.config['LOGIN_REQUIRED'] = False
        
        with main.app.test_client() as client:
            response = client.post('/search', data={'search_query': 'test'})
            # Should handle the error gracefully
            assert response.status_code == 500
            assert b'error' in response.data.lower()


if __name__ == "__main__":
    pytest.main([__file__])
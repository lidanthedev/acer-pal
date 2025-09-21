"""Tests for filename generation and sanitization functions."""

import pytest
import sys
import os

# Add the parent directory to the path to import main
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import create_episode_filename_from_context, sanitize_filename


class TestFilenameGeneration:
    """Test the episode filename generation functionality."""
    
    def test_basic_episode_filename_generation(self):
        """Test basic episode filename generation."""
        show_title = "The Big Bang Theory"
        episode_title = "S05E03"
        selected_quality = "Season 5 English 720p Esubs [180MB]"
        original_filename = "placeholder.mp4"
        
        result = create_episode_filename_from_context(
            show_title, episode_title, selected_quality, original_filename
        )
        
        expected = "The.Big.Bang.Theory.S05E03.720p.mp4"
        assert result == expected
    
    def test_different_resolutions(self):
        """Test filename generation with different video resolutions."""
        show_title = "Friends"
        episode_title = "S01E01"
        original_filename = "test.mp4"
        
        test_cases = [
            ("Season 1 English 1080p BluRay", "Friends.S01E01.1080p.mp4"),
            ("Season 1 English 4K HDR", "Friends.S01E01.4K.mp4"),
            ("Season 1 English 480p DVD", "Friends.S01E01.480p.mp4"),
            ("Season 1 English 2160p UHD", "Friends.S01E01.2160p.mp4"),
        ]
        
        for selected_quality, expected in test_cases:
            result = create_episode_filename_from_context(
                show_title, episode_title, selected_quality, original_filename
            )
            assert result == expected
    
    def test_show_title_with_special_characters(self):
        """Test filename generation with show titles containing special characters."""
        test_cases = [
            ("Marvel's Agents of S.H.I.E.L.D.", "Marvels.Agents.of.S.H.I.E.L.D.S01E01.720p.mp4"),
            ("It's Always Sunny", "Its.Always.Sunny.S01E01.720p.mp4"),
            ("Law & Order: SVU", "Law.&.Order.SVU.S01E01.720p.mp4"),
        ]
        
        for show_title, expected in test_cases:
            result = create_episode_filename_from_context(
                show_title, "S01E01", "Season 1 720p", "test.mp4"
            )
            assert result == expected
    
    def test_episode_title_parsing(self):
        """Test parsing of different episode title formats."""
        show_title = "Breaking Bad"
        selected_quality = "Season 3 720p WEB-DL"
        original_filename = "test.mp4"
        
        test_cases = [
            ("S03E07", "Breaking.Bad.S03E07.720p.mp4"),
            ("S3E7", "Breaking.Bad.S03E07.720p.mp4"),
            ("Season 3 Episode 7", "Breaking.Bad.S03E07.720p.mp4"),
        ]
        
        for episode_title, expected in test_cases:
            result = create_episode_filename_from_context(
                show_title, episode_title, selected_quality, original_filename
            )
            assert result == expected
    
    def test_file_extension_handling(self):
        """Test handling of different file extensions."""
        show_title = "Game of Thrones"
        episode_title = "S08E06"
        selected_quality = "Season 8 1080p BluRay"
        
        test_cases = [
            ("test.mp4", "Game.of.Thrones.S08E06.1080p.mp4"),
            ("test.mkv", "Game.of.Thrones.S08E06.1080p.mkv"),
            ("test.avi", "Game.of.Thrones.S08E06.1080p.avi"),
            ("test", "Game.of.Thrones.S08E06.1080p.mp4"),  # Default to .mp4
            ("test.720p", "Game.of.Thrones.S08E06.1080p.mp4"),  # Quality extension should default to .mp4
        ]
        
        for original_filename, expected in test_cases:
            result = create_episode_filename_from_context(
                show_title, episode_title, selected_quality, original_filename
            )
            assert result == expected
    
    def test_season_extraction_from_quality(self):
        """Test extracting season number from the selected quality."""
        show_title = "The Office"
        episode_title = "E01"  # No season in episode title
        original_filename = "test.mp4"
        
        test_cases = [
            ("Season 1 720p", "The.Office.S01E01.720p.mp4"),
            ("Season 10 1080p", "The.Office.S10E01.1080p.mp4"),
            ("Season 2 English 720p", "The.Office.S02E01.720p.mp4"),
        ]
        
        for selected_quality, expected in test_cases:
            result = create_episode_filename_from_context(
                show_title, episode_title, selected_quality, original_filename
            )
            assert result == expected
    
    def test_fallback_behavior(self):
        """Test fallback behavior when parsing fails."""
        show_title = "Unknown Show"
        episode_title = "Random Episode Title"
        selected_quality = "Some Quality"
        original_filename = "test.mp4"
        
        result = create_episode_filename_from_context(
            show_title, episode_title, selected_quality, original_filename
        )
        
        # Should still generate a valid filename with defaults
        assert result.startswith("Unknown.Show.S01E01")
        assert result.endswith(".mp4")
        assert "720p" in result  # Default quality


class TestFilenameSanitization:
    """Test the filename sanitization functionality."""
    
    def test_sanitize_basic_filename(self):
        """Test basic filename sanitization."""
        test_cases = [
            ("normal_filename.mp4", "normal_filename.mp4"),
            ("file with spaces.mp4", "file_with_spaces.mp4"),
            ("file:with*invalid?chars.mp4", "filewithchars.mp4"),
            ("file\\with/slashes.mp4", "filewithslashes.mp4"),
            ("file\"with<quotes>.mp4", "filewithquotes.mp4"),
        ]
        
        for input_filename, expected in test_cases:
            result = sanitize_filename(input_filename)
            assert result == expected
    
    def test_sanitize_long_filename(self):
        """Test sanitization of very long filenames."""
        long_filename = "a" * 300 + ".mp4"
        result = sanitize_filename(long_filename)
        
        # Should be truncated to 200 characters
        assert len(result) <= 200
        assert result.endswith(".mp4")
    
    def test_sanitize_empty_filename(self):
        """Test sanitization of empty or invalid filenames."""
        test_cases = ["", "   ", "..."]
        
        for filename in test_cases:
            result = sanitize_filename(filename)
            # Should return something valid
            assert len(result) > 0
            assert len(result) <= 200


if __name__ == "__main__":
    pytest.main([__file__])
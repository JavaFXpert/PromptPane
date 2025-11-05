"""
Unit tests for config.py

Tests for configuration loading and validation.
"""

import pytest
import config

# ============================================================================
# Configuration Loading Tests
# ============================================================================

@pytest.mark.unit
class TestConfigLoading:
    """Tests for configuration module"""

    def test_server_config_loaded(self):
        """Test server configuration is loaded"""
        assert hasattr(config, 'SERVER_PORT')
        assert isinstance(config.SERVER_PORT, int)
        assert config.SERVER_PORT > 0

    def test_default_session_id_loaded(self):
        """Test default session ID is loaded"""
        assert hasattr(config, 'DEFAULT_SESSION_ID')
        assert isinstance(config.DEFAULT_SESSION_ID, str)
        assert len(config.DEFAULT_SESSION_ID) > 0

    def test_groq_config_loaded(self):
        """Test Groq API configuration is loaded"""
        assert hasattr(config, 'GROQ_MODEL')
        assert isinstance(config.GROQ_MODEL, str)

        assert hasattr(config, 'GROQ_TEMPERATURE')
        assert isinstance(config.GROQ_TEMPERATURE, float)
        assert 0.0 <= config.GROQ_TEMPERATURE <= 1.0

    def test_retry_config_loaded(self):
        """Test retry configuration is loaded"""
        assert hasattr(config, 'RETRY_MAX_ATTEMPTS')
        assert isinstance(config.RETRY_MAX_ATTEMPTS, int)
        assert config.RETRY_MAX_ATTEMPTS > 0

        assert hasattr(config, 'RETRY_INITIAL_DELAY')
        assert isinstance(config.RETRY_INITIAL_DELAY, int)
        assert config.RETRY_INITIAL_DELAY > 0

        assert hasattr(config, 'RETRY_MAX_DELAY')
        assert isinstance(config.RETRY_MAX_DELAY, int)
        assert config.RETRY_MAX_DELAY >= config.RETRY_INITIAL_DELAY

    def test_logging_config_loaded(self):
        """Test logging configuration is loaded"""
        assert hasattr(config, 'LOG_LEVEL')
        assert isinstance(config.LOG_LEVEL, str)
        assert config.LOG_LEVEL in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

        assert hasattr(config, 'LOG_FORMAT')
        assert isinstance(config.LOG_FORMAT, str)
        assert len(config.LOG_FORMAT) > 0

    def test_katex_config_loaded(self):
        """Test KaTeX configuration is loaded"""
        assert hasattr(config, 'KATEX_VERSION')
        assert isinstance(config.KATEX_VERSION, str)

        assert hasattr(config, 'KATEX_CSS_URL')
        assert config.KATEX_CSS_URL.startswith('https://')

        assert hasattr(config, 'KATEX_JS_URL')
        assert config.KATEX_JS_URL.startswith('https://')

    def test_theme_config_loaded(self):
        """Test theme configuration is loaded"""
        assert hasattr(config, 'THEME_COLOR')
        assert isinstance(config.THEME_COLOR, str)

        assert hasattr(config, 'ENABLE_SYNTAX_HIGHLIGHTING')
        assert isinstance(config.ENABLE_SYNTAX_HIGHLIGHTING, bool)

        assert hasattr(config, 'ENABLE_LIVE_RELOAD')
        assert isinstance(config.ENABLE_LIVE_RELOAD, bool)

# ============================================================================
# Validation Configuration Tests
# ============================================================================

@pytest.mark.unit
class TestValidationConfig:
    """Tests for validation configuration"""

    def test_message_length_limits(self):
        """Test message length limits are configured"""
        assert hasattr(config, 'MAX_MESSAGE_LENGTH')
        assert isinstance(config.MAX_MESSAGE_LENGTH, int)
        assert config.MAX_MESSAGE_LENGTH > 0

        assert hasattr(config, 'MIN_MESSAGE_LENGTH')
        assert isinstance(config.MIN_MESSAGE_LENGTH, int)
        assert config.MIN_MESSAGE_LENGTH > 0
        assert config.MIN_MESSAGE_LENGTH < config.MAX_MESSAGE_LENGTH

    def test_session_id_config(self):
        """Test session ID configuration"""
        assert hasattr(config, 'MAX_SESSION_ID_LENGTH')
        assert isinstance(config.MAX_SESSION_ID_LENGTH, int)
        assert config.MAX_SESSION_ID_LENGTH > 0

        assert hasattr(config, 'SESSION_ID_PATTERN')
        assert isinstance(config.SESSION_ID_PATTERN, str)
        # Should be a valid regex pattern
        import re
        try:
            re.compile(config.SESSION_ID_PATTERN)
        except re.error:
            pytest.fail("SESSION_ID_PATTERN is not a valid regex")

    def test_rate_limit_config(self):
        """Test rate limiting configuration"""
        assert hasattr(config, 'RATE_LIMIT_WINDOW_SECONDS')
        assert isinstance(config.RATE_LIMIT_WINDOW_SECONDS, int)
        assert config.RATE_LIMIT_WINDOW_SECONDS > 0

        assert hasattr(config, 'RATE_LIMIT_MAX_REQUESTS')
        assert isinstance(config.RATE_LIMIT_MAX_REQUESTS, int)
        assert config.RATE_LIMIT_MAX_REQUESTS > 0

        assert hasattr(config, 'ENABLE_RATE_LIMITING')
        assert isinstance(config.ENABLE_RATE_LIMITING, bool)

# ============================================================================
# Configuration Sanity Tests
# ============================================================================

@pytest.mark.unit
class TestConfigSanity:
    """Sanity tests for configuration values"""

    def test_port_in_valid_range(self):
        """Test server port is in valid range"""
        assert 1 <= config.SERVER_PORT <= 65535

    def test_temperature_in_valid_range(self):
        """Test temperature is in valid range for LLM"""
        assert 0.0 <= config.GROQ_TEMPERATURE <= 2.0

    def test_rate_limit_reasonable(self):
        """Test rate limit values are reasonable"""
        # Should allow at least a few requests
        assert config.RATE_LIMIT_MAX_REQUESTS >= 1
        # Window should be at least 1 second
        assert config.RATE_LIMIT_WINDOW_SECONDS >= 1
        # Window should be reasonable (not years)
        assert config.RATE_LIMIT_WINDOW_SECONDS < 86400  # Less than a day

    def test_message_limits_reasonable(self):
        """Test message length limits are reasonable"""
        # Max message should allow meaningful content
        assert config.MAX_MESSAGE_LENGTH >= 100
        # Max message should have some limit (not unlimited)
        assert config.MAX_MESSAGE_LENGTH <= 1000000  # 1MB of text

        # Min message should be at least 1
        assert config.MIN_MESSAGE_LENGTH >= 1

    def test_retry_config_reasonable(self):
        """Test retry configuration values are reasonable"""
        # Should allow at least one retry
        assert config.RETRY_MAX_ATTEMPTS >= 1
        # Should not retry forever
        assert config.RETRY_MAX_ATTEMPTS <= 10

        # Delays should be reasonable
        assert config.RETRY_INITIAL_DELAY >= 0
        assert config.RETRY_MAX_DELAY >= config.RETRY_INITIAL_DELAY
        assert config.RETRY_MAX_DELAY <= 60  # Not more than 1 minute

    def test_katex_urls_valid_format(self):
        """Test KaTeX URLs have valid format"""
        import re
        url_pattern = r'https://[a-z0-9.-]+/.*'

        assert re.match(url_pattern, config.KATEX_CSS_URL)
        assert re.match(url_pattern, config.KATEX_JS_URL)
        assert re.match(url_pattern, config.KATEX_AUTORENDER_URL)

    def test_citation_css_valid(self):
        """Test citation CSS is valid"""
        assert hasattr(config, 'CITATION_CSS')
        assert isinstance(config.CITATION_CSS, str)
        assert '.citation-link' in config.CITATION_CSS
        # Should have at least some CSS properties
        assert '{' in config.CITATION_CSS
        assert '}' in config.CITATION_CSS

# ============================================================================
# Type Hints Tests
# ============================================================================

@pytest.mark.unit
class TestConfigTypeHints:
    """Tests to verify configuration has proper type hints"""

    def test_integer_configs_are_integers(self):
        """Test integer configurations are actually integers"""
        integer_configs = [
            'SERVER_PORT',
            'RETRY_MAX_ATTEMPTS',
            'RETRY_INITIAL_DELAY',
            'RETRY_MAX_DELAY',
            'MAX_MESSAGE_LENGTH',
            'MIN_MESSAGE_LENGTH',
            'MAX_SESSION_ID_LENGTH',
            'RATE_LIMIT_WINDOW_SECONDS',
            'RATE_LIMIT_MAX_REQUESTS',
        ]

        for config_name in integer_configs:
            value = getattr(config, config_name)
            assert isinstance(value, int), f"{config_name} should be int, got {type(value)}"

    def test_string_configs_are_strings(self):
        """Test string configurations are actually strings"""
        string_configs = [
            'DEFAULT_SESSION_ID',
            'GROQ_MODEL',
            'LOG_LEVEL',
            'LOG_FORMAT',
            'KATEX_VERSION',
            'KATEX_CSS_URL',
            'THEME_COLOR',
            'SESSION_ID_PATTERN',
            'CITATION_CSS',
        ]

        for config_name in string_configs:
            value = getattr(config, config_name)
            assert isinstance(value, str), f"{config_name} should be str, got {type(value)}"

    def test_boolean_configs_are_booleans(self):
        """Test boolean configurations are actually booleans"""
        boolean_configs = [
            'ENABLE_SYNTAX_HIGHLIGHTING',
            'ENABLE_LIVE_RELOAD',
            'ENABLE_RATE_LIMITING',
        ]

        for config_name in boolean_configs:
            value = getattr(config, config_name)
            assert isinstance(value, bool), f"{config_name} should be bool, got {type(value)}"

    def test_float_configs_are_floats(self):
        """Test float configurations are actually floats"""
        float_configs = [
            'GROQ_TEMPERATURE',
        ]

        for config_name in float_configs:
            value = getattr(config, config_name)
            assert isinstance(value, float), f"{config_name} should be float, got {type(value)}"

"""Tests for connectors (news, science, local device)."""
import pytest
from unittest.mock import patch, MagicMock
from backend.connectors.news_connector import NewsConnector, TRUSTED_SOURCES
from backend.connectors.science_connector import ScienceConnector
from backend.connectors.local_device_connector import LocalDeviceConnector
from backend.models import NewsItem, ScienceItem, LocalDevice


class TestNewsConnector:
    def test_source_list(self):
        nc = NewsConnector()
        sources = nc.source_list()
        assert "bbc-news" in sources
        assert sources["bbc-news"] > 0.9

    def test_parse_rss(self):
        nc = NewsConnector()
        xml = """<?xml version="1.0"?>
        <rss version="2.0">
          <channel>
            <item>
              <title>Test Headline</title>
              <link>http://example.com/1</link>
              <description>A test story</description>
              <pubDate>Mon, 01 Jan 2026 00:00:00 GMT</pubDate>
            </item>
          </channel>
        </rss>"""
        items = nc._parse_rxml(xml, "test-source", 0.9)
        assert len(items) == 1
        assert items[0].title == "Test Headline"
        assert items[0].confidence == 0.9

    def test_parse_atom(self):
        nc = NewsConnector()
        xml = """<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Atom Entry</title>
            <link href="http://example.com/atom"/>
            <summary>Summary text</summary>
            <updated>2026-01-01T00:00:00Z</updated>
          </entry>
        </feed>"""
        items = nc._parse_rxml(xml, "test-source", 0.85)
        assert len(items) == 1
        assert items[0].title == "Atom Entry"

    def test_unknown_source_returns_empty(self):
        nc = NewsConnector()
        items = nc.fetch_headlines("nonexistent-source")
        assert items == []

    @patch.object(NewsConnector, '_parse_rxml')
    @patch("requests.Session.get")
    def test_fetch_headlines(self, mock_get, mock_parse):
        mock_response = MagicMock()
        mock_response.text = "<rss/>"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        mock_parse.return_value = [NewsItem(title="Mock", source="bbc", url="http://x.com")]
        nc = NewsConnector()
        items = nc.fetch_headlines("bbc-news", max_items=5)
        assert len(items) == 1
        assert items[0].title == "Mock"


class TestScienceConnector:
    def test_category_list(self):
        sc = ScienceConnector()
        cats = sc.category_list()
        assert "cs.AI" in cats

    def test_parse_arxiv_xml(self):
        sc = ScienceConnector()
        xml = """<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom"
              xmlns:arxiv="http://arxiv.org/schemas/atom">
          <entry>
            <title>Deep Learning Breakthrough</title>
            <author><name>Jane Doe</name></author>
            <summary>We present a new method...</summary>
            <id>http://arxiv.org/abs/2601.00001</id>
            <published>2026-01-01T00:00:00Z</published>
            <link title="pdf" href="http://arxiv.org/pdf/2601.00001"/>
          </entry>
        </feed>"""
        items = sc._parse_arxiv_xml(xml, "cs.AI")
        assert len(items) == 1
        assert items[0].title == "Deep Learning Breakthrough"
        assert "Jane Doe" in items[0].authors


class TestLocalDeviceConnector:
    def test_scan_empty(self):
        ldc = LocalDeviceConnector()
        devices = ldc.scan()
        assert devices == []

    def test_scan_with_kasa(self):
        ldc = LocalDeviceConnector()
        mock_kasa = MagicMock()
        mock_kasa.discover = MagicMock(return_value=[
            {"ip": "192.168.1.5", "alias": "Light", "device_type": "bulb", "is_dimmable": True},
        ])
        devices = ldc.scan(kasa_agent=mock_kasa)
        assert len(devices) == 1
        assert devices[0].name == "Light"
        assert "brightness" in devices[0].capabilities

    def test_is_port_open_false(self):
        ldc = LocalDeviceConnector()
        assert ldc.is_port_open("127.0.0.1", 59999, timeout=0.5) is False

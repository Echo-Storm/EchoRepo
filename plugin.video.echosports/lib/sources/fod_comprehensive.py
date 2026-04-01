# -*- coding: utf-8 -*-
"""
Fights on Demand (FOD) Content Source for plugin.video.echosports

Integrates boxing, UFC, and MMA content from the FOD feeds.
Content sourced from: https://mylostsoulspace.co.uk/FightsOnDemand/

Categories:
- UFC (PPV, Fight Night, ESPN, ABC, BJJ, Classic events)
- MMA (Various promotions: ONE, Bellator, PFL, etc.)
- Boxing (Current events, classic fights)
"""

import re
import requests
from typing import List, Dict, Optional, Tuple
from datetime import datetime


class FODContentSource:
    """
    Fights on Demand content source.
    Fetches and parses XML feeds for UFC, MMA, and Boxing content.
    """
    
    BASE_URL = "https://mylostsoulspace.co.uk/FightsOnDemand"
    
    # Main feed URLs
    FEEDS = {
        # Main entry
        'main': f"{BASE_URL}/fodmain-new.xml",
        
        # Latest/Recent
        'latest_ufc_mma': f"{BASE_URL}/latestufc-mmaevents.xml",
        'latest_ufc_mma_2025': f"{BASE_URL}/latestufc-mmaevents-25.xml",
        
        # UFC Events
        'ufc_main': f"{BASE_URL}/ufcevents/ufceventreplaysmain-new.xml",
        'ufc_ppv': f"{BASE_URL}/ufcevents/ufcppv-new.xml",
        'ufc_fight_night': f"{BASE_URL}/ufcevents/ufcfightnightreplays-new.xml",
        'ufc_espn': f"{BASE_URL}/ufcevents/ufcfightnightonespn-new.xml",
        'ufc_abc': f"{BASE_URL}/ufcevents/ufconabc-new.xml",
        'ufc_bjj': f"{BASE_URL}/ufcevents/ufcbjj-new.xml",
        'ufc_classic_ppv': f"{BASE_URL}/ufcevents/classicufc-new.xml",
        'ufc_classic_fn': f"{BASE_URL}/ufcevents/classicfightnight-new.xml",
        'ufc_fox': f"{BASE_URL}/ufcevents/ufconfoxtv-new.xml",
        'ufc_fuel': f"{BASE_URL}/ufcevents/ufconfueltv-new.xml",
        
        # MMA Events
        'mma_main': f"{BASE_URL}/mmaevents/mmaeventreplaysmain-new.xml",
        
        # Non-Debrid (free)
        'nondebrid_ufc': f"{BASE_URL}/nondebridufc.xml",
        'nondebrid_mma': f"{BASE_URL}/nondebridmmareplays.xml",
        
        # UFC Shows
        'ufc_shows': f"{BASE_URL}/ufcshows/ufcshowsmain-new.xml",
        
        # Boxing
        'boxing': f"{BASE_URL}/boxing/boxingreplays-new.xml",
        'boxing_2025': f"{BASE_URL}/boxing/boxingreplays-25.xml",
        'boxing_nondebrid': f"{BASE_URL}/boxing/boxingreplays-nondebrid.xml",
    }
    
    def __init__(self, cache_enabled=True, cache_duration=1800):
        """
        Initialize FOD content source.
        
        Args:
            cache_enabled: Whether to cache XML responses
            cache_duration: Cache duration in seconds (default 30 min)
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.cache_enabled = cache_enabled
        self.cache_duration = cache_duration
        self._cache = {}
    
    def fetch_xml(self, url: str) -> Optional[str]:
        """Fetch XML content from URL with caching."""
        if self.cache_enabled and url in self._cache:
            content, timestamp = self._cache[url]
            if (datetime.now() - timestamp).total_seconds() < self.cache_duration:
                return content
        
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            content = response.text
            
            if self.cache_enabled:
                self._cache[url] = (content, datetime.now())
            
            return content
        except requests.RequestException as e:
            print(f"Failed to fetch {url}: {e}")
            return None
    
    def parse_xml(self, xml_content: str) -> List[Dict]:
        """
        Parse FOD XML content using regex (handles malformed XML).
        
        Returns list of items with type 'dir' (folder) or 'item' (playable).
        """
        items = []
        
        # Extract <item> blocks (playable content)
        item_pattern = r'<item>(.*?)</item>'
        for match in re.findall(item_pattern, xml_content, re.DOTALL | re.IGNORECASE):
            item = self._parse_block(match, 'item')
            if item:
                items.append(item)
        
        # Extract <dir> blocks (folders/categories)
        dir_pattern = r'<dir>(.*?)</dir>'
        for match in re.findall(dir_pattern, xml_content, re.DOTALL | re.IGNORECASE):
            item = self._parse_block(match, 'dir')
            if item:
                items.append(item)
        
        return items
    
    def _parse_block(self, content: str, block_type: str) -> Optional[Dict]:
        """Parse content inside <item> or <dir> element."""
        item = {'type': block_type}
        
        # Extract title
        title_match = re.search(r'<title>(.*?)</title>', content, re.DOTALL | re.IGNORECASE)
        if title_match:
            item['title'] = title_match.group(1).strip()
        
        # Extract link(s)
        link_match = re.search(r'<link>(.*?)</link>', content, re.DOTALL | re.IGNORECASE)
        if link_match:
            link_content = link_match.group(1).strip()
            
            # Check for sublinks
            sublink_pattern = r'<sublink>(.*?)</sublink>'
            sublinks = re.findall(sublink_pattern, link_content, re.DOTALL | re.IGNORECASE)
            
            if sublinks:
                item['links'] = [s.strip() for s in sublinks if s.strip()]
            elif link_content:
                item['links'] = [link_content]
        
        # Extract thumbnail
        thumb_match = re.search(r'<thumbnail>(.*?)</thumbnail>', content, re.DOTALL | re.IGNORECASE)
        if thumb_match:
            item['thumbnail'] = thumb_match.group(1).strip()
        
        # Extract fanart
        fanart_match = re.search(r'<fanart>(.*?)</fanart>', content, re.DOTALL | re.IGNORECASE)
        if fanart_match:
            item['fanart'] = fanart_match.group(1).strip()
        
        # Extract summary
        summary_match = re.search(r'<summary>(.*?)</summary>', content, re.DOTALL | re.IGNORECASE)
        if summary_match:
            item['summary'] = summary_match.group(1).strip()
        
        # Skip items without title
        if not item.get('title'):
            return None
        
        # For playable items, skip if no links
        if block_type == 'item' and not item.get('links'):
            return None
        
        return item
    
    def strip_color_tags(self, text: str) -> str:
        """Strip Kodi color/formatting tags from text."""
        # Handle malformed tags like [COLORwhite] (missing space)
        text = re.sub(r'\[COLOR\s*\w+\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\[/COLOR\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\[B\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\[/B\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\[I\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\[/I\]', '', text, flags=re.IGNORECASE)
        return text.strip()
    
    def parse_link(self, link: str) -> Tuple[str, str, Dict]:
        """
        Parse a link and determine its type.
        
        Returns: (url, link_type, metadata)
        - link_type: 'magnet', 'mega', 'direct', 'unknown'
        - metadata: dict with any extracted info (e.g., label from parentheses)
        """
        metadata = {}
        
        # Extract label in parentheses at end, e.g., "magnet:?....(Main Card)"
        label_match = re.search(r'\(([^)]+)\)\s*$', link)
        if label_match:
            metadata['label'] = label_match.group(1)
            link = link[:label_match.start()].strip()
        
        # Determine type
        if link.startswith('magnet:'):
            return link, 'magnet', metadata
        elif 'mega.nz' in link:
            return link, 'mega', metadata
        elif link.endswith('.m3u8') or link.endswith('.mp4'):
            return link, 'direct', metadata
        else:
            return link, 'unknown', metadata
    
    # === Content Retrieval Methods ===
    
    def get_main_menu(self) -> List[Dict]:
        """Get main FOD menu structure."""
        xml_content = self.fetch_xml(self.FEEDS['main'])
        if not xml_content:
            return []
        return self.parse_xml(xml_content)
    
    def get_latest_ufc_mma(self) -> List[Dict]:
        """Get latest UFC/MMA events."""
        xml_content = self.fetch_xml(self.FEEDS['latest_ufc_mma'])
        if not xml_content:
            return []
        return self.parse_xml(xml_content)
    
    def get_ufc_events_menu(self) -> List[Dict]:
        """Get UFC events category menu."""
        xml_content = self.fetch_xml(self.FEEDS['ufc_main'])
        if not xml_content:
            return []
        return self.parse_xml(xml_content)
    
    def get_ufc_ppv(self) -> List[Dict]:
        """Get UFC PPV events."""
        xml_content = self.fetch_xml(self.FEEDS['ufc_ppv'])
        if not xml_content:
            return []
        return self.parse_xml(xml_content)
    
    def get_ufc_fight_night(self) -> List[Dict]:
        """Get UFC Fight Night events."""
        xml_content = self.fetch_xml(self.FEEDS['ufc_fight_night'])
        if not xml_content:
            return []
        return self.parse_xml(xml_content)
    
    def get_ufc_espn(self) -> List[Dict]:
        """Get UFC on ESPN events."""
        xml_content = self.fetch_xml(self.FEEDS['ufc_espn'])
        if not xml_content:
            return []
        return self.parse_xml(xml_content)
    
    def get_ufc_abc(self) -> List[Dict]:
        """Get UFC on ABC events."""
        xml_content = self.fetch_xml(self.FEEDS['ufc_abc'])
        if not xml_content:
            return []
        return self.parse_xml(xml_content)
    
    def get_ufc_bjj(self) -> List[Dict]:
        """Get UFC BJJ events."""
        xml_content = self.fetch_xml(self.FEEDS['ufc_bjj'])
        if not xml_content:
            return []
        return self.parse_xml(xml_content)
    
    def get_ufc_classic_ppv(self) -> List[Dict]:
        """Get Classic UFC PPV events."""
        xml_content = self.fetch_xml(self.FEEDS['ufc_classic_ppv'])
        if not xml_content:
            return []
        return self.parse_xml(xml_content)
    
    def get_ufc_classic_fn(self) -> List[Dict]:
        """Get Classic UFC Fight Night events."""
        xml_content = self.fetch_xml(self.FEEDS['ufc_classic_fn'])
        if not xml_content:
            return []
        return self.parse_xml(xml_content)
    
    def get_ufc_shows(self) -> List[Dict]:
        """Get UFC Shows & Series."""
        xml_content = self.fetch_xml(self.FEEDS['ufc_shows'])
        if not xml_content:
            return []
        return self.parse_xml(xml_content)
    
    def get_mma_events(self) -> List[Dict]:
        """Get MMA events menu."""
        xml_content = self.fetch_xml(self.FEEDS['mma_main'])
        if not xml_content:
            return []
        return self.parse_xml(xml_content)
    
    def get_boxing(self) -> List[Dict]:
        """Get boxing replays."""
        xml_content = self.fetch_xml(self.FEEDS['boxing'])
        if not xml_content:
            return []
        return self.parse_xml(xml_content)
    
    def get_boxing_nondebrid(self) -> List[Dict]:
        """Get non-debrid boxing replays."""
        xml_content = self.fetch_xml(self.FEEDS['boxing_nondebrid'])
        if not xml_content:
            return []
        return self.parse_xml(xml_content)
    
    def get_nondebrid_ufc(self) -> List[Dict]:
        """Get non-debrid UFC replays."""
        xml_content = self.fetch_xml(self.FEEDS['nondebrid_ufc'])
        if not xml_content:
            return []
        return self.parse_xml(xml_content)
    
    def get_nondebrid_mma(self) -> List[Dict]:
        """Get non-debrid MMA replays."""
        xml_content = self.fetch_xml(self.FEEDS['nondebrid_mma'])
        if not xml_content:
            return []
        return self.parse_xml(xml_content)
    
    def get_content_from_url(self, url: str) -> List[Dict]:
        """Fetch and parse content from any URL."""
        xml_content = self.fetch_xml(url)
        if not xml_content:
            return []
        return self.parse_xml(xml_content)
    
    def format_item(self, item: Dict, category: str = '') -> Dict:
        """
        Format a raw item for display.
        
        Args:
            item: Raw item from XML
            category: Category path for context
            
        Returns:
            Formatted item dictionary
        """
        formatted = {
            'title': self.strip_color_tags(item.get('title', 'Untitled')),
            'raw_title': item.get('title', ''),
            'thumbnail': item.get('thumbnail', ''),
            'fanart': item.get('fanart', ''),
            'summary': item.get('summary', ''),
            'type': item.get('type', 'item'),
            'category': category,
        }
        
        # Handle links
        if item.get('links'):
            parsed_links = []
            for link in item['links']:
                url, link_type, meta = self.parse_link(link)
                parsed_links.append({
                    'url': url,
                    'type': link_type,
                    'label': meta.get('label', ''),
                })
            formatted['links'] = parsed_links
            formatted['primary_link'] = parsed_links[0] if parsed_links else None
        
        # For directories, store the URL for navigation
        if item['type'] == 'dir' and item.get('links'):
            formatted['xml_url'] = item['links'][0]
        
        return formatted
    
    def format_items(self, items: List[Dict], category: str = '') -> List[Dict]:
        """Format multiple items."""
        return [self.format_item(item, category) for item in items]


# Test if run directly
if __name__ == '__main__':
    source = FODContentSource()
    
    print("=" * 60)
    print("FIGHTS ON DEMAND CONTENT")
    print("=" * 60)
    
    # Main menu
    print("\n1. MAIN MENU:")
    main = source.get_main_menu()
    for item in main:
        print(f"   - {source.strip_color_tags(item.get('title', ''))}")
    
    # Latest UFC/MMA
    print("\n2. LATEST UFC/MMA (first 5):")
    latest = source.get_latest_ufc_mma()
    for item in latest[:5]:
        title = source.strip_color_tags(item.get('title', ''))
        print(f"   - {title}")
    
    # Boxing
    print("\n3. BOXING (first 5):")
    boxing = source.get_boxing()
    for item in boxing[:5]:
        title = source.strip_color_tags(item.get('title', ''))
        print(f"   - {title}")
    
    print("\n" + "=" * 60)

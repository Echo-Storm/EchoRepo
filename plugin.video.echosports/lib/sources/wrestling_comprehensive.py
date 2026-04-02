"""
Comprehensive Wrestling Content Source for plugin.video.echosports

Provides organized wrestling content including:
- WWE (RAW, SmackDown, NXT, WrestleMania, PPVs, documentaries)
- AEW (All Elite Wrestling)
- Other Promotions (TNA, NWA, NJPW, ROH, RPW, Indy)
- Live streams (24/7 channels + live events)
- Documentaries & Interviews
- Special matches & archives

Content sourced from public XML feeds.
"""

import xml.etree.ElementTree as ET
import requests
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime


class WrestlingContentSource:
    """
    Comprehensive wrestling content source.
    
    Fetches and parses wrestling content from XML feeds,
    organized into a clean category structure.
    """
    
    BASE_URL = "https://l3grthu.com/hades/wod21"
    
    # Complete mapping of all available content feeds
    FEEDS = {
        # Core categories
        'live': f"{BASE_URL}/live.xml",
        'shows_menu': f"{BASE_URL}/latestshows/latestshows.xml",
        'archive': f"{BASE_URL}/Archives/archives.xml",
        'documentaries': f"{BASE_URL}/documentaries/docmain.xml",
        'interviews': f"{BASE_URL}/kayfabe/main.xml",
        'special_matches': f"{BASE_URL}/specialmatches/specialmatches.xml",
        'random_events': f"{BASE_URL}/latestshows/randomevents.xml",
        'movies_tv': f"{BASE_URL}/mov.xml",
        
        # WWE content
        'wwe_raw': f"{BASE_URL}/latestshows/raw.xml",
        'wwe_smackdown': f"{BASE_URL}/latestshows/smackdown.xml",
        'wwe_nxt': f"{BASE_URL}/latestshows/nxtmain.xml",
        'wwe_wrestlemania': f"{BASE_URL}/wrestlemania/mainwm.xml",
        'wwe_ppv': f"{BASE_URL}/ppv/ppvmain.xml",
        'wwe_youtube': f"{BASE_URL}/wweyt.xml",
        
        # Other promotions
        'aew': f"{BASE_URL}/aew/aewppv.xml",
        'nwa': f"{BASE_URL}/nwa/main.xml",
        'tna': f"{BASE_URL}/tna/tnamain.xml",
        'njpw': f"{BASE_URL}/njpw/njpwmain.xml",
        'roh': f"{BASE_URL}/roh/main.xml",
        'rpw': f"{BASE_URL}/random/rpw.xml",
        'indy': f"{BASE_URL}/indy.xml",
    }
    
    def __init__(self, cache_enabled=True, cache_duration=3600):
        """
        Initialize wrestling content source.
        
        Args:
            cache_enabled: Whether to cache XML responses
            cache_duration: Cache duration in seconds (default 1 hour)
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
        # Check cache
        if self.cache_enabled and url in self._cache:
            content, timestamp = self._cache[url]
            if (datetime.now() - timestamp).total_seconds() < self.cache_duration:
                return content
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            content = response.text
            
            if self.cache_enabled:
                self._cache[url] = (content, datetime.now())
            
            return content
        except requests.RequestException as e:
            print(f"Failed to fetch {url}: {e}")
            return None
    
    def parse_xml(self, xml_content: str) -> List[Dict[str, any]]:
        """
        Parse XML content using regex (handles malformed XML).
        """
        items = []
        
        # Extract <item> blocks
        item_pattern = r'<item>(.*?)</item>'
        item_matches = re.findall(item_pattern, xml_content, re.DOTALL | re.IGNORECASE)
        
        for match in item_matches:
            item = self._parse_item_content(match, 'item')
            if item:
                items.append(item)
        
        # Extract <dir> blocks (folders/categories)
        dir_pattern = r'<dir>(.*?)</dir>'
        dir_matches = re.findall(dir_pattern, xml_content, re.DOTALL | re.IGNORECASE)
        
        for match in dir_matches:
            item = self._parse_item_content(match, 'dir')
            if item:
                items.append(item)
        
        return items
    
    def _parse_item_content(self, content: str, item_type: str) -> Optional[Dict[str, any]]:
        """Parse content inside <item> or <dir> element."""
        item = {'type': item_type}
        
        # Extract title
        title_match = re.search(r'<title>(.*?)</title>', content, re.DOTALL | re.IGNORECASE)
        if title_match:
            item['title'] = title_match.group(1).strip()
        
        # Extract summary (note the typo in some XMLs: summaru)
        summary_match = re.search(r'<summary>(.*?)</summary>', content, re.DOTALL | re.IGNORECASE)
        if not summary_match:
            summary_match = re.search(r'<summaru>(.*?)</summaru>', content, re.DOTALL | re.IGNORECASE)
        if summary_match:
            item['summary'] = summary_match.group(1).strip()
        
        # Extract thumbnail
        thumb_match = re.search(r'<thumbnail>(.*?)</thumbnail>', content, re.DOTALL | re.IGNORECASE)
        if thumb_match:
            item['thumbnail'] = thumb_match.group(1).strip()
        
        # Extract fanart
        fanart_match = re.search(r'<fanart>(.*?)</fanart>', content, re.DOTALL | re.IGNORECASE)
        if fanart_match:
            item['fanart'] = fanart_match.group(1).strip()
        
        # Extract link and sublinks
        link_match = re.search(r'<link>(.*?)</link>', content, re.DOTALL | re.IGNORECASE)
        if link_match:
            link_content = link_match.group(1)
            
            # Extract all sublinks
            sublink_pattern = r'<sublink>(.*?)</sublink>'
            sublinks = re.findall(sublink_pattern, link_content, re.DOTALL | re.IGNORECASE)
            
            if sublinks:
                valid_sublinks = []
                for sublink in sublinks:
                    sublink = sublink.strip()
                    if sublink and sublink.lower() not in ['no', 'nolink', 'http://', 'https://']:
                        valid_sublinks.append(sublink)
                
                if valid_sublinks:
                    item['link'] = valid_sublinks
            else:
                # Direct link without sublinks
                link_text = link_content.strip()
                if link_text and link_text.lower() not in ['no', 'nolink', 'http://', 'https://']:
                    item['link'] = [link_text]
        
        # Skip items without title
        if not item.get('title'):
            return None
        
        # Skip placeholder items for playable content
        if not item.get('link') and item_type == 'item':
            return None
        
        return item
    
    def parse_sublink(self, sublink: str) -> Tuple[str, Dict[str, str]]:
        """
        Parse sublink into URL and headers.
        Format: url|Referer=https://example.com/&User-Agent=Mozilla
        """
        if '|' not in sublink:
            return sublink, {}
        
        parts = sublink.split('|', 1)
        url = parts[0]
        headers = {}
        
        if len(parts) > 1:
            header_string = parts[1]
            for pair in header_string.split('&'):
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    headers[key] = value
        
        return url, headers
    
    def strip_color_tags(self, text: str) -> str:
        """
        Strip Kodi color/formatting tags from text.
        
        Handles malformed tags from upstream XML feeds like:
        - [COLOR white ] (space before bracket)
        - [COLORsnow] (missing / in closing tag)
        - Standard [COLOR xxx] and [/COLOR]
        """
        # Handle standard and malformed opening color tags: [COLOR xxx], [COLOR xxx ]
        text = re.sub(r'\[COLOR\s*\w*\s*\]', '', text, flags=re.IGNORECASE)
        # Handle standard closing: [/COLOR]
        text = re.sub(r'\[/COLOR\]', '', text, flags=re.IGNORECASE)
        # Handle malformed closing (no slash): [COLORxxx] where xxx is the "leftover" text
        # Pattern: [COLOR followed by lowercase letters at end of string or before next tag
        text = re.sub(r'\[COLOR([a-z]+)\]', r'\1', text, flags=re.IGNORECASE)
        # Bold tags
        text = re.sub(r'\[/?B\]', '', text, flags=re.IGNORECASE)
        # Italic tags
        text = re.sub(r'\[/?I\]', '', text, flags=re.IGNORECASE)
        # Uppercase tags
        text = re.sub(r'\[/?UPPERCASE\]', '', text, flags=re.IGNORECASE)
        # Lowercase tags
        text = re.sub(r'\[/?LOWERCASE\]', '', text, flags=re.IGNORECASE)
        # CR (carriage return) tags
        text = re.sub(r'\[/?CR\]', '', text, flags=re.IGNORECASE)
        # Clean up any remaining broken tags
        text = re.sub(r'\[COLOR[^\]]*\]', '', text, flags=re.IGNORECASE)
        return text.strip()
    
    # === High-level content retrieval methods ===
    
    def get_live_content(self) -> List[Dict[str, any]]:
        """Get all live wrestling streams and events."""
        xml_content = self.fetch_xml(self.FEEDS['live'])
        if not xml_content:
            return []
        
        items = self.parse_xml(xml_content)
        return [item for item in items if item['type'] == 'item' and item.get('link')]
    
    def get_wwe_raw_episodes(self) -> List[Dict[str, any]]:
        """Get WWE RAW episodes."""
        xml_content = self.fetch_xml(self.FEEDS['wwe_raw'])
        if not xml_content:
            return []
        
        items = self.parse_xml(xml_content)
        return [item for item in items if item['type'] == 'item' and item.get('link')]
    
    def get_wwe_smackdown_episodes(self) -> List[Dict[str, any]]:
        """Get WWE SmackDown episodes."""
        xml_content = self.fetch_xml(self.FEEDS['wwe_smackdown'])
        if not xml_content:
            return []
        
        items = self.parse_xml(xml_content)
        return [item for item in items if item['type'] == 'item' and item.get('link')]
    
    def get_wwe_nxt_episodes(self) -> List[Dict[str, any]]:
        """Get WWE NXT episodes."""
        xml_content = self.fetch_xml(self.FEEDS['wwe_nxt'])
        if not xml_content:
            return []
        
        items = self.parse_xml(xml_content)
        return [item for item in items if item['type'] == 'item' and item.get('link')]
    
    def get_wwe_shows_menu(self) -> List[Dict[str, any]]:
        """Get WWE shows menu (includes other series/documentaries)."""
        xml_content = self.fetch_xml(self.FEEDS['shows_menu'])
        if not xml_content:
            return []
        
        return self.parse_xml(xml_content)
    
    def get_wwe_wrestlemania(self) -> List[Dict[str, any]]:
        """Get WrestleMania events."""
        xml_content = self.fetch_xml(self.FEEDS['wwe_wrestlemania'])
        if not xml_content:
            return []
        
        return self.parse_xml(xml_content)
    
    def get_wwe_ppv(self) -> List[Dict[str, any]]:
        """Get WWE PPV events."""
        xml_content = self.fetch_xml(self.FEEDS['wwe_ppv'])
        if not xml_content:
            return []
        
        return self.parse_xml(xml_content)
    
    def get_aew_content(self) -> List[Dict[str, any]]:
        """Get AEW (All Elite Wrestling) content."""
        xml_content = self.fetch_xml(self.FEEDS['aew'])
        if not xml_content:
            return []
        
        return self.parse_xml(xml_content)
    
    def get_tna_content(self) -> List[Dict[str, any]]:
        """Get TNA wrestling content."""
        xml_content = self.fetch_xml(self.FEEDS['tna'])
        if not xml_content:
            return []
        
        return self.parse_xml(xml_content)
    
    def get_nwa_content(self) -> List[Dict[str, any]]:
        """Get NWA (National Wrestling Alliance) content."""
        xml_content = self.fetch_xml(self.FEEDS['nwa'])
        if not xml_content:
            return []
        
        return self.parse_xml(xml_content)
    
    def get_njpw_content(self) -> List[Dict[str, any]]:
        """Get NJPW (New Japan Pro Wrestling) content."""
        xml_content = self.fetch_xml(self.FEEDS['njpw'])
        if not xml_content:
            return []
        
        return self.parse_xml(xml_content)
    
    def get_roh_content(self) -> List[Dict[str, any]]:
        """Get ROH (Ring of Honor) content."""
        xml_content = self.fetch_xml(self.FEEDS['roh'])
        if not xml_content:
            return []
        
        return self.parse_xml(xml_content)
    
    def get_indy_content(self) -> List[Dict[str, any]]:
        """Get independent wrestling content."""
        xml_content = self.fetch_xml(self.FEEDS['indy'])
        if not xml_content:
            return []
        
        return self.parse_xml(xml_content)
    
    def get_documentaries(self) -> List[Dict[str, any]]:
        """Get wrestling documentaries."""
        xml_content = self.fetch_xml(self.FEEDS['documentaries'])
        if not xml_content:
            return []
        
        return self.parse_xml(xml_content)
    
    def get_interviews(self) -> List[Dict[str, any]]:
        """Get wrestling interviews."""
        xml_content = self.fetch_xml(self.FEEDS['interviews'])
        if not xml_content:
            return []
        
        return self.parse_xml(xml_content)
    
    def get_special_matches(self) -> List[Dict[str, any]]:
        """Get special/notable wrestling matches."""
        xml_content = self.fetch_xml(self.FEEDS['special_matches'])
        if not xml_content:
            return []
        
        return self.parse_xml(xml_content)
    
    def get_archive(self) -> List[Dict[str, any]]:
        """Get wrestling archive content."""
        xml_content = self.fetch_xml(self.FEEDS['archive'])
        if not xml_content:
            return []
        
        return self.parse_xml(xml_content)
    
    def get_movies_tv(self) -> List[Dict[str, any]]:
        """Get wrestling movies and TV shows."""
        xml_content = self.fetch_xml(self.FEEDS['movies_tv'])
        if not xml_content:
            return []
        
        return self.parse_xml(xml_content)
    
    def format_item(self, item: Dict[str, any], category: str) -> Dict[str, any]:
        """
        Format a raw item for Kodi display.
        
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
            'type': item['type'],
            'category': category,
        }
        
        # Handle links
        if item.get('link'):
            links = item['link']
            if isinstance(links, str):
                links = [links]
            
            # Parse sublinks into URL + headers
            parsed_links = []
            for link in links:
                url, headers = self.parse_sublink(link)
                parsed_links.append({'url': url, 'headers': headers})
            
            formatted['links'] = parsed_links
            formatted['primary_link'] = parsed_links[0] if parsed_links else None
        
        # Handle directories (folders)
        if item['type'] == 'dir' and item.get('link'):
            # Store the XML URL for navigation
            formatted['xml_url'] = item['link'][0] if isinstance(item['link'], list) else item['link']
        
        return formatted
    
    def format_items(self, items: List[Dict[str, any]], category: str) -> List[Dict[str, any]]:
        """Format multiple items."""
        return [self.format_item(item, category) for item in items]


# Example usage
if __name__ == '__main__':
    """Demonstrate comprehensive content retrieval."""
    
    source = WrestlingContentSource()
    
    print("=" * 80)
    print("COMPREHENSIVE WRESTLING CONTENT SOURCE")
    print("=" * 80)
    
    # Live content
    print("\n1. LIVE CONTENT:")
    live = source.get_live_content()
    print(f"   Found {len(live)} live streams/events")
    for item in live[:3]:
        print(f"   - {source.strip_color_tags(item['title'])}")
    
    # WWE content
    print("\n2. WWE CONTENT:")
    print(f"   RAW: {len(source.get_wwe_raw_episodes())} episodes")
    print(f"   SmackDown: {len(source.get_wwe_smackdown_episodes())} episodes")
    print(f"   NXT: {len(source.get_wwe_nxt_episodes())} episodes")
    print(f"   WrestleMania: {len(source.get_wwe_wrestlemania())} items")
    print(f"   PPV: {len(source.get_wwe_ppv())} items")
    
    # Other promotions
    print("\n3. OTHER PROMOTIONS:")
    print(f"   AEW: {len(source.get_aew_content())} items")
    print(f"   TNA: {len(source.get_tna_content())} items")
    print(f"   NWA: {len(source.get_nwa_content())} items")
    print(f"   NJPW: {len(source.get_njpw_content())} items")
    print(f"   ROH: {len(source.get_roh_content())} items")
    print(f"   Indy: {len(source.get_indy_content())} items")
    
    # Other content
    print("\n4. OTHER CONTENT:")
    print(f"   Documentaries: {len(source.get_documentaries())} items")
    print(f"   Interviews: {len(source.get_interviews())} items")
    print(f"   Special Matches: {len(source.get_special_matches())} items")
    print(f"   Movies/TV: {len(source.get_movies_tv())} items")
    print(f"   Archive: {len(source.get_archive())} items")
    
    print("\n" + "=" * 80)
    print("TOTAL CONTENT AVAILABLE")
    print("=" * 80)

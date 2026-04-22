"""
PitSport motorsport source for Echo Sports.

Scrapes pitsport.xyz for live motorsport streams.
Based on Torque Live addon by Dudelove00.

Supports: MotoGP, IndyCar, IndyNXT, F1, and other motorsports.
"""

import re
import json
import calendar
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from html import unescape
from urllib.parse import urljoin, urlparse

# Try requests first, fall back to urllib
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request
    import ssl

BASE_URL = 'https://pitsport.xyz'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
      'AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/124.0.0.0 Safari/537.36')


class _TreeCollector(HTMLParser):
    """Simple HTML parser that builds a tree structure."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = {'tag': 'root', 'attrs': {}, 'text': '', 'children': []}
        self._stack = [self.root]
        
    def handle_starttag(self, tag, attrs):
        node = {'tag': tag, 'attrs': dict(attrs), 'text': '', 'children': []}
        self._stack[-1]['children'].append(node)
        # Self-closing tags don't get pushed
        if tag not in ('br', 'hr', 'img', 'input', 'meta', 'link', 'area', 
                       'base', 'col', 'embed', 'param', 'source', 'track', 'wbr'):
            self._stack.append(node)
            
    def handle_endtag(self, tag):
        if len(self._stack) > 1 and self._stack[-1]['tag'] == tag:
            self._stack.pop()
            
    def handle_data(self, data):
        self._stack[-1]['text'] += data


def _parse_html(html):
    """Parse HTML into a tree structure."""
    parser = _TreeCollector()
    try:
        parser.feed(html)
    except:
        pass
    return parser.root


def _find_all(node, tag=None, attr=None, val=None, out=None):
    """Find all nodes matching criteria."""
    if out is None:
        out = []
    match_tag = tag is None or node.get('tag') == tag
    match_attr = (attr is None or 
                  (val is None and attr in node.get('attrs', {})) or
                  node.get('attrs', {}).get(attr, '') == val)
    if match_tag and match_attr:
        out.append(node)
    for child in node.get('children', []):
        _find_all(child, tag, attr, val, out)
    return out


def _get_text(node):
    """Extract text content from a node."""
    if not node:
        return ''
    parts = [node.get('text', '')]
    for child in node.get('children', []):
        parts.append(_get_text(child))
    return unescape(' '.join(p.strip() for p in parts if p.strip()))


def _fetch(url, referer=None):
    """Fetch a URL and return (content, final_url)."""
    headers = {
        'User-Agent': UA,
        'Referer': referer or BASE_URL,
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    if HAS_REQUESTS:
        try:
            session = requests.Session()
            session.headers.update({'User-Agent': UA})
            r = session.get(url, timeout=15, headers=headers, allow_redirects=True)
            if r.ok:
                return r.text, r.url
        except Exception as e:
            pass
    
    # Fallback to urllib
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            charset = resp.headers.get_content_charset() or 'utf-8'
            return resp.read().decode(charset, errors='replace'), resp.url
    except Exception as e:
        pass
    
    return None, url


def _decode_nextf(html):
    """Decode Next.js RSC payload from self.__next_f.push() calls."""
    chunks = re.findall(r'self\.__next_f\.push\(\[1\s*,\s*"((?:[^"\\]|\\.)*)"\]\)', html)
    payload = ''
    for chunk in chunks:
        try:
            payload += chunk.encode('utf-8').decode('unicode_escape')
        except:
            payload += chunk
    return payload


def _utc_to_local(utc_dt):
    """Convert UTC datetime to local time."""
    timestamp = calendar.timegm(utc_dt.timetuple())
    local_dt = datetime.fromtimestamp(timestamp)
    return local_dt.replace(microsecond=utc_dt.microsecond)


def _format_time(date_val):
    """Format a Unix timestamp or ISO string to local time string."""
    if not date_val:
        return ''
    try:
        import time as _time
        utc_off = _time.timezone if _time.daylight == 0 else _time.altzone
        tz_local = timezone(timedelta(seconds=-utc_off))
        
        # Try Unix timestamp
        try:
            ts = int(str(date_val).strip())
            if ts > 1000000000:
                return datetime.fromtimestamp(ts, tz=tz_local).strftime('%a %d %b %H:%M')
        except (ValueError, TypeError):
            pass
        
        # Try ISO format
        s = str(date_val).strip().replace('Z', '+00:00')
        return datetime.fromisoformat(s).astimezone(tz_local).strftime('%a %d %b %H:%M')
    except Exception:
        return ''


def _sort_key(item):
    """Return a sortable key for an item's date field."""
    d = item.get('date', '')
    if not d:
        return 9999999999
    try:
        return int(str(d).strip())
    except (ValueError, TypeError):
        pass
    try:
        s = str(d).strip().replace('Z', '+00:00')
        return int(datetime.fromisoformat(s).timestamp())
    except Exception:
        return 9999999999


class PitSportSource:
    """PitSport motorsport source."""
    
    name = 'pitsport'
    display_name = 'PitSport Motorsport'
    
    def __init__(self):
        self.base_url = BASE_URL
    
    def get_categories(self):
        """Return available categories."""
        return [
            {'id': 'live', 'name': 'Live Now', 'path': '/live-now'},
            {'id': 'schedule', 'name': 'Schedule', 'path': '/schedule'},
        ]
    
    def get_events(self, category_id='live'):
        """
        Get events for a category.
        
        Returns list of dicts with:
        - title: Event title
        - series: Series name (e.g., "MotoGP", "IndyCar")
        - date: Start time (Unix timestamp or ISO string)
        - url: Watch page URL
        - thumb: Thumbnail URL (optional)
        """
        path = '/live-now' if category_id == 'live' else '/schedule'
        url = self.base_url + path
        
        html, final_url = _fetch(url)
        if not html:
            return []
        
        return self._parse_items(html, final_url)
    
    def _parse_items(self, html, page_url):
        """Parse events from pitsport HTML."""
        items = []
        seen = set()
        root = _parse_html(html)
        host = urlparse(BASE_URL).netloc
        
        SKIP = ('/_next/', 'discord.gg', 'facebook', 'twitter', 'instagram',
                'mailto:', 'javascript:', '#', '.svg', '.css', '.js')
        
        # Build URL to series mapping from HTML
        url_to_series = {}
        current_series = ''
        series_blocks = re.split(r'<h2[^>]*>', html)
        for block in series_blocks[1:]:
            m = re.match(r'([^<]{2,60})</h2>', block)
            if m and m.group(1).strip():
                current_series = m.group(1).strip()
            for link_m in re.finditer(r'href=["\'](/watch/[^"\']+)["\']', block):
                full_url = BASE_URL + link_m.group(1)
                url_to_series[full_url] = current_series
        
        # Build URL to timestamp mapping from Next.js payload
        url_to_date = {}
        payload = _decode_nextf(html)
        if payload:
            for ts_m in re.finditer(
                    r'"href"\s*:\s*"(/watch/[^"]+)"[^}]{0,600}?"time"\s*:\s*(\d{9,11})',
                    payload):
                url_to_date[BASE_URL + ts_m.group(1)] = int(ts_m.group(2))
        
        # Walk tree to collect items
        for a in _find_all(root, 'a'):
            href = a['attrs'].get('href', '').strip()
            if not href or any(s in href for s in SKIP):
                continue
            
            full = urljoin(page_url, href)
            if urlparse(full).netloc != host:
                continue
            if full.rstrip('/') == BASE_URL.rstrip('/'):
                continue
            if len([x for x in urlparse(full).path.split('/') if x]) < 2:
                continue
            if full in seen:
                continue
            seen.add(full)
            
            title = _get_text(a).strip()
            if not title or len(title) < 2:
                continue
            
            # Get date from time tag or our map
            date = ''
            time_tags = _find_all(a, 'time')
            if time_tags:
                date = time_tags[0]['attrs'].get('datetime', '') or _get_text(time_tags[0])
            if not date:
                date = url_to_date.get(full, '')
            
            # Get thumbnail
            thumb = ''
            img_tags = _find_all(a, 'img')
            if img_tags:
                src = img_tags[0]['attrs'].get('data-src') or img_tags[0]['attrs'].get('src', '')
                if src and not src.startswith('data:'):
                    thumb = urljoin(page_url, src)
            
            items.append({
                'title': title,
                'series': url_to_series.get(full, ''),
                'date': date,
                'url': full,
                'thumb': thumb,
            })
        
        # Also try parsing from Next.js payload if tree parsing found nothing
        if not items and payload:
            items = self._parse_nextf_items(payload, page_url, host)
        
        # Sort by start time
        items.sort(key=_sort_key)
        
        return items
    
    def _parse_nextf_items(self, payload, page_url, host):
        """Parse items from Next.js RSC payload."""
        items = []
        seen = set()
        
        for m in re.finditer(r'\{[^{}]{15,3000}\}', payload):
            try:
                obj = json.loads(m.group(0))
                self._extract_item(obj, items, seen, page_url, host)
            except:
                pass
        
        return items
    
    def _extract_item(self, obj, items, seen, page_url, host):
        """Extract item from a JSON object."""
        if not isinstance(obj, dict):
            if isinstance(obj, list):
                for x in obj:
                    self._extract_item(x, items, seen, page_url, host)
            return
        
        href = obj.get('href') or obj.get('url') or obj.get('slug') or obj.get('path')
        title = obj.get('title') or obj.get('name') or obj.get('label') or obj.get('eventName')
        date = obj.get('date') or obj.get('startTime') or obj.get('scheduledAt') or obj.get('start')
        thumb = obj.get('image') or obj.get('thumbnail') or obj.get('imageUrl') or obj.get('thumbnailUrl')
        
        if href and title and isinstance(href, str) and isinstance(title, str) and len(title) > 1:
            if href.startswith('/'):
                full = BASE_URL + href
            elif href.startswith('http'):
                full = href
            else:
                full = urljoin(page_url, href)
            
            if full not in seen and urlparse(full).netloc == host:
                seen.add(full)
                items.append({
                    'title': str(title),
                    'series': '',
                    'date': str(date) if date else '',
                    'url': full,
                    'thumb': str(thumb) if thumb else '',
                })
        
        # Recurse into nested objects
        for v in obj.values():
            if isinstance(v, (dict, list)):
                self._extract_item(v, items, seen, page_url, host)
    
    def resolve_stream(self, watch_url):
        """
        Resolve a watch URL to a playable stream URL.
        
        Returns tuple: (stream_url, referer) or (None, None) on failure.
        """
        html, final_url = _fetch(watch_url)
        if not html:
            return None, None
        
        # Try direct stream URLs in the page
        streams = self._find_streams(html, final_url)
        if streams:
            return streams[0], None
        
        # Look for iframes
        iframes = re.findall(r'<iframe[^>]+src=["\']([^"\']{5,})["\']', html, re.I | re.S)
        
        for src in iframes:
            iframe_url = urljoin(final_url, src.strip())
            
            # Skip known non-video iframes
            if any(x in iframe_url.lower() for x in ['youtube', 'vimeo', 'dailymotion']):
                # Could return YouTube plugin URL here if wanted
                continue
            
            embed_html, embed_final = _fetch(iframe_url, referer=final_url)
            if not embed_html:
                continue
            
            # Check for streams in embed page
            streams = self._find_streams(embed_html, embed_final)
            if streams:
                return streams[0], iframe_url
            
            # Check Next.js payload in embed page
            embed_payload = _decode_nextf(embed_html)
            if embed_payload:
                streams = self._find_streams(embed_payload, embed_final)
                if streams:
                    return streams[0], iframe_url
                
                # Try to extract stream link from payload
                link, method = self._extract_stream_link(embed_payload)
                if link:
                    if any(x in link.lower() for x in ['.m3u8', '.mpd', '.mp4']):
                        return link, iframe_url
                    
                    # Resolve player page
                    resolved = self._resolve_player_page(link, iframe_url)
                    if resolved:
                        return resolved, iframe_url
            
            # Try API probe for pushembdz-style embeds
            api_stream = self._probe_api(iframe_url, final_url)
            if api_stream:
                return api_stream, iframe_url
        
        return None, None
    
    def _find_streams(self, text, base=''):
        """Find stream URLs in text."""
        patterns = [
            re.compile(r'["\']([^"\']{10,500}\.m3u8[^"\']*)["\']', re.I),
            re.compile(r'["\']([^"\']{10,500}\.mpd[^"\']*)["\']', re.I),
            re.compile(r'["\']([^"\']{10,500}\.mp4[^"\']*)["\']', re.I),
            re.compile(r'"hls(?:Url)?"\s*:\s*"([^"]{10,500})"', re.I),
            re.compile(r'"(?:src|source|file|videoUrl)"\s*:\s*"(https?://[^"]{10,500})"', re.I),
        ]
        
        found = []
        for pat in patterns:
            for m in pat.findall(text):
                u = m.strip()
                if not u.startswith('http'):
                    u = urljoin(base, u) if base else u
                if any(x in u.lower() for x in ['.m3u8', '.mpd', '.mp4']) and u not in found:
                    found.append(u)
        
        return found
    
    def _extract_stream_link(self, payload):
        """Extract stream link from Next.js payload."""
        m = re.search(r'"stream"\s*:\s*(\{[^}]+\})', payload)
        if m:
            try:
                obj = json.loads(m.group(1))
                link = obj.get('link') or obj.get('url') or obj.get('src')
                if link:
                    return link, obj.get('method', '')
            except:
                pass
        
        m = re.search(r'"link"\s*:\s*"(https?://[^"]+)"', payload)
        if m:
            return m.group(1), 'unknown'
        
        return None, None
    
    def _resolve_player_page(self, player_url, referer):
        """Resolve a player page URL to a stream."""
        content, final_url = _fetch(player_url, referer=referer)
        if not content:
            return None
        
        # Check if it's already an M3U8
        if content.strip().startswith('#EXTM3U'):
            # Return the URL itself, not the content
            return player_url
        
        # Find streams in the player page
        streams = self._find_streams(content, final_url)
        if streams:
            return streams[0]
        
        return None
    
    def _probe_api(self, embed_url, referer):
        """Probe API endpoints for pushembdz-style embeds."""
        parsed = urlparse(embed_url)
        path_parts = [p for p in parsed.path.split('/') if p]
        if not path_parts:
            return None
        
        uuid_part = path_parts[-1]
        base = f'{parsed.scheme}://{parsed.netloc}'
        
        api_candidates = [
            f'{base}/api/source/{uuid_part}',
            f'{base}/api/stream/{uuid_part}',
            f'{base}/api/video/{uuid_part}',
            f'{base}/api/embed/{uuid_part}',
            f'{base}/api/play/{uuid_part}',
        ]
        
        for api_url in api_candidates:
            text, _ = _fetch(api_url, referer=embed_url)
            if not text:
                continue
            
            # Try JSON parse
            try:
                obj = json.loads(text)
                candidates = [obj]
                for v in list(obj.values()):
                    if isinstance(v, dict):
                        candidates.append(v)
                
                for d in candidates:
                    for key in ('url', 'link', 'src', 'source', 'hls', 'hlsUrl',
                                'stream', 'streamUrl', 'file', 'videoUrl', 'playback'):
                        val = d.get(key)
                        if isinstance(val, str) and val.startswith('http'):
                            return val
            except:
                pass
            
            # Regex fallback
            streams = self._find_streams(text, '')
            if streams:
                return streams[0]
        
        return None
    
    def format_label(self, item):
        """Format an item for display in Kodi."""
        series = item.get('series', '')
        title = item['title']
        dt_fmt = _format_time(item.get('date', ''))
        
        base_label = f'{series}: {title}' if series else title
        return f'{dt_fmt}  |  {base_label}' if dt_fmt else base_label


# Singleton instance
pitsport_source = PitSportSource()

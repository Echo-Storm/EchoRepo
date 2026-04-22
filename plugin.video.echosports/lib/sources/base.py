# -*- coding: utf-8 -*-
"""
Base Source - Abstract base class for all event sources.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional


class BaseSource(ABC):
    """Abstract base class for event sources."""
    
    # Source identifier
    SOURCE_ID = "base"
    SOURCE_NAME = "Base Source"
    
    # Sport type mappings (normalized -> source-specific)
    SPORT_MAPPINGS = {}
    
    def __init__(self):
        """Initialize the source."""
        self._cache = {}
        
    @abstractmethod
    def get_events(self, sport: str = 'all') -> List[Dict[str, Any]]:
        """
        Fetch events for a sport category.
        
        Args:
            sport: Sport type ('all', 'nfl', 'nba', etc.)
            
        Returns:
            List of event dictionaries with standardized fields:
            - id: Unique event identifier
            - name: Display name (e.g., "Team1 vs Team2")
            - team1: First team name
            - team2: Second team name  
            - league: League/competition name
            - sport: Sport type
            - start_time: Unix timestamp
            - time_display: Formatted time string
            - is_live: Boolean indicating if event is live
            - icon: Icon/thumbnail URL
            - channels: List of channel names with streams
        """
        pass
        
    @abstractmethod
    def get_streams(self, event_id: str) -> List[Dict[str, Any]]:
        """
        Fetch available streams for an event.
        
        Args:
            event_id: Event identifier
            
        Returns:
            List of stream dictionaries:
            - name: Stream/channel name
            - url: Stream URL
            - quality: Quality indicator (HD, SD, etc.)
            - language: Language code
            - resolver: Resolver to use ('direct', 'embed', 'debrid')
        """
        pass
        
    def normalize_sport(self, sport: str) -> str:
        """
        Normalize sport name to source-specific format.
        
        Args:
            sport: Normalized sport name
            
        Returns:
            Source-specific sport identifier
        """
        return self.SPORT_MAPPINGS.get(sport, sport)
        
    def format_time(self, timestamp: int, timezone: str = 'UTC') -> str:
        """
        Format a Unix timestamp for display.
        
        Args:
            timestamp: Unix timestamp (seconds)
            timezone: Timezone name
            
        Returns:
            Formatted time string (e.g., "Mar 29, 14:30")
        """
        try:
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime("%b %d, %H:%M")
        except Exception:
            return ""
            
    def is_event_live(self, start_time: int, duration_minutes: int = 180) -> bool:
        """
        Check if an event is currently live.
        
        Args:
            start_time: Event start time (Unix timestamp)
            duration_minutes: Expected duration in minutes
            
        Returns:
            True if event is currently live
        """
        now = datetime.now().timestamp()
        end_time = start_time + (duration_minutes * 60)
        return start_time <= now <= end_time

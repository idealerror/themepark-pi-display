"""
ThemeParks.wiki API Client

Handles all communication with the themeparks.wiki API for fetching
live wait times, park schedules, and attraction information.

API Documentation: https://api.themeparks.wiki/docs
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AttractionStatus(Enum):
    OPERATING = "OPERATING"
    DOWN = "DOWN"
    CLOSED = "CLOSED"
    REFURBISHMENT = "REFURBISHMENT"


@dataclass
class Attraction:
    """Represents a single attraction with wait time data"""
    id: str
    name: str
    wait_time: Optional[int] = None
    status: AttractionStatus = AttractionStatus.CLOSED
    last_updated: datetime = field(default_factory=datetime.now)
    is_virtual_queue: bool = False
    fastpass_available: bool = False
    single_rider: bool = False


@dataclass
class Park:
    """Represents a theme park"""
    id: str
    name: str
    timezone: str
    attractions: Dict[str, Attraction] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.now)


class ThemeParksClient:
    """
    Async client for the themeparks.wiki API
    
    Usage:
        client = ThemeParksClient()
        await client.initialize()
        
        # Get wait times for Hollywood Studios
        park_data = await client.get_live_data('waltdisneyworldresort_hollywoodstudios')
        
        for attraction in park_data.attractions.values():
            print(f"{attraction.name}: {attraction.wait_time} min")
    """
    
    BASE_URL = "https://api.themeparks.wiki/v1"
    
    # Common park entity IDs (UUIDs from themeparks.wiki API)
    PARK_IDS = {
        # Walt Disney World
        'magic_kingdom': '75ea578a-adc8-4116-a54d-dccb60765ef9',
        'epcot': '47f90d2c-e191-4239-a466-5892ef59a88b',
        'hollywood_studios': '288747d1-8b4f-4a64-867e-ea7c9b27bad8',
        'animal_kingdom': '1c84a229-8862-4648-9c71-378ddd2c7693',

        # Disneyland Resort (UUIDs need to be fetched)
        'disneyland': '7340550b-c14d-4def-80bb-acdb51d49a66',
        'california_adventure': '832fcd51-ea19-4e77-85c7-75d5843b127c',

        # Universal Orlando (UUIDs need to be fetched)
        'universal_studios': 'eb3f4560-2383-4a36-9152-6b3e5f6ac81c',
        'islands_of_adventure': '267615cc-8943-4c2a-ae2c-5da728ca591f',

        # Universal Hollywood
        'universal_hollywood': 'fe78a026-b91b-470c-b906-9d2266b692da',
    }
    
    # Featured attractions for each park (for the main display)
    FEATURED_ATTRACTIONS = {
        'hollywood_studios': [
            'Tower of Terror',
            'Rock n Roller Coaster',
            'Slinky Dog Dash',
            'Millennium Falcon',
            'Rise of the Resistance',
            'Mickey & Minnie Runaway Railway',
        ],
        'magic_kingdom': [
            'Space Mountain',
            'Big Thunder Mountain',
            'Splash Mountain',
            'Seven Dwarfs Mine Train',
            'Haunted Mansion',
            'Pirates of the Caribbean',
        ],
        'disneyland': [
            'Matterhorn Bobsleds',
            'Space Mountain',
            'Big Thunder Mountain',
            'Indiana Jones',
            'Haunted Mansion',
            'Pirates of the Caribbean',
        ],
    }
    
    def __init__(self, cache_ttl: int = 60):
        """
        Initialize the client
        
        Args:
            cache_ttl: How long to cache results in seconds (default 60)
        """
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Park] = {}
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the aiohttp session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={'Accept': 'application/json'}
            )
        return self._session
    
    async def close(self):
        """Close the HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _fetch(self, endpoint: str) -> Dict[str, Any]:
        """
        Fetch data from the API
        
        Args:
            endpoint: API endpoint path
            
        Returns:
            JSON response as dict
        """
        session = await self._get_session()
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"API request failed: {e}")
            raise
    
    async def get_destinations(self) -> List[Dict]:
        """
        Get all available destinations (resort groups)
        
        Returns:
            List of destination objects
        """
        data = await self._fetch("/destinations")
        return data.get('destinations', [])
    
    async def get_entity(self, entity_id: str) -> Dict:
        """
        Get details for a specific entity (park, attraction, etc)
        
        Args:
            entity_id: The entity's unique ID
            
        Returns:
            Entity details
        """
        return await self._fetch(f"/entity/{entity_id}")
    
    async def get_entity_children(self, entity_id: str) -> List[Dict]:
        """
        Get child entities (attractions within a park)
        
        Args:
            entity_id: Parent entity ID (usually a park)
            
        Returns:
            List of child entities
        """
        data = await self._fetch(f"/entity/{entity_id}/children")
        return data.get('children', [])
    
    async def get_live_data(self, entity_id: str, use_cache: bool = True) -> Park:
        """
        Get live wait times and status for a park
        
        Args:
            entity_id: Park entity ID
            use_cache: Whether to use cached data if available
            
        Returns:
            Park object with attractions and wait times
        """
        # Check cache
        if use_cache and entity_id in self._cache:
            cached = self._cache[entity_id]
            age = datetime.now() - cached.last_updated
            if age.total_seconds() < self.cache_ttl:
                logger.debug(f"Using cached data for {entity_id}")
                return cached
        
        # Fetch fresh data
        data = await self._fetch(f"/entity/{entity_id}/live")
        
        # Parse into Park object
        park = Park(
            id=entity_id,
            name=data.get('name', 'Unknown Park'),
            timezone=data.get('timezone', 'America/New_York'),
            last_updated=datetime.now()
        )
        
        # Parse live data for attractions
        for item in data.get('liveData', []):
            if item.get('entityType') == 'ATTRACTION':
                status_str = item.get('status', 'CLOSED')
                try:
                    status = AttractionStatus(status_str)
                except ValueError:
                    status = AttractionStatus.CLOSED
                
                queue = item.get('queue', {})
                standby = queue.get('STANDBY', {})
                
                attraction = Attraction(
                    id=item.get('id', ''),
                    name=item.get('name', 'Unknown'),
                    wait_time=standby.get('waitTime'),
                    status=status,
                    last_updated=datetime.now(),
                    is_virtual_queue='BOARDING_GROUP' in queue,
                    fastpass_available='PAID_RETURN_TIME' in queue,
                    single_rider='SINGLE_RIDER' in queue
                )
                park.attractions[attraction.id] = attraction
        
        # Update cache
        self._cache[entity_id] = park
        
        logger.info(f"Fetched live data for {park.name}: {len(park.attractions)} attractions")
        return park
    
    async def get_wait_time(self, park_id: str, attraction_name: str) -> Optional[int]:
        """
        Get wait time for a specific attraction by name
        
        Args:
            park_id: Park entity ID
            attraction_name: Name of the attraction (partial match)
            
        Returns:
            Wait time in minutes, or None if not found/closed
        """
        park = await self.get_live_data(park_id)
        
        # Find attraction by name (partial match)
        for attraction in park.attractions.values():
            if attraction_name.lower() in attraction.name.lower():
                if attraction.status == AttractionStatus.OPERATING:
                    return attraction.wait_time
                return None
        
        return None
    
    def get_park_id(self, park_name: str) -> Optional[str]:
        """
        Get park entity ID from common name
        
        Args:
            park_name: Common park name (e.g., 'magic_kingdom', 'disneyland')
            
        Returns:
            Entity ID or None
        """
        return self.PARK_IDS.get(park_name.lower().replace(' ', '_'))


# Synchronous wrapper for Kivy integration
class ThemeParksSync:
    """
    Synchronous wrapper around the async client for easier Kivy integration
    
    Usage with Kivy Clock:
        from kivy.clock import Clock
        
        client = ThemeParksSync()
        
        def update_wait_times(dt):
            data = client.get_live_data('hollywood_studios')
            for name, wait in data.items():
                print(f"{name}: {wait}")
        
        Clock.schedule_interval(update_wait_times, 60)
    """
    
    def __init__(self):
        self._client = ThemeParksClient()

    def _run_async(self, coro):
        """Run async coroutine safely, works even with Kivy's event loop"""
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result(timeout=30)

    def get_live_data(self, park_name: str, operating_only: bool = False) -> Dict[str, Optional[int]]:
        """
        Get live wait times for a park

        Args:
            park_name: Common park name (e.g., 'hollywood_studios')
            operating_only: If True, only return operating attractions

        Returns:
            Dict mapping attraction names to wait times
        """
        park_id = self._client.get_park_id(park_name)

        if not park_id:
            logger.error(f"Unknown park: {park_name}")
            return {}

        try:
            park = self._run_async(self._client.get_live_data(park_id))

            if operating_only:
                return {
                    attr.name: attr.wait_time
                    for attr in park.attractions.values()
                    if attr.status == AttractionStatus.OPERATING
                }
            else:
                return {
                    attr.name: attr.wait_time
                    for attr in park.attractions.values()
                }
        except Exception as e:
            logger.error(f"Failed to fetch data: {e}")
            return {}

    def get_wait_time(self, park_name: str, attraction_name: str) -> Optional[int]:
        """Get wait time for a specific attraction"""
        park_id = self._client.get_park_id(park_name)

        if not park_id:
            return None

        try:
            return self._run_async(
                self._client.get_wait_time(park_id, attraction_name)
            )
        except Exception as e:
            logger.error(f"Failed to fetch wait time: {e}")
            return None

    def close(self):
        """Clean up resources"""
        try:
            self._run_async(self._client.close())
        except Exception:
            pass


# Example usage
if __name__ == '__main__':
    async def main():
        client = ThemeParksClient()
        
        try:
            # Get Hollywood Studios wait times
            park = await client.get_live_data(
                client.PARK_IDS['hollywood_studios']
            )
            
            print(f"\n{park.name}")
            print("=" * 50)
            
            # Sort by wait time
            operating = [
                a for a in park.attractions.values() 
                if a.status == AttractionStatus.OPERATING and a.wait_time
            ]
            operating.sort(key=lambda x: x.wait_time or 0, reverse=True)
            
            for attr in operating[:10]:
                vq = " [VQ]" if attr.is_virtual_queue else ""
                ll = " [LL]" if attr.fastpass_available else ""
                print(f"  {attr.name}: {attr.wait_time} min{vq}{ll}")
            
        finally:
            await client.close()
    
    asyncio.run(main())

"""
Disney Theme Park Wait Time Display
A Kivy-based touchscreen interface for Raspberry Pi
"""

import os
import json
import threading
from datetime import datetime
from pathlib import Path
from functools import partial

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.graphics import Color, Rectangle, RoundedRectangle, Ellipse, Line, InstructionGroup
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.properties import (
    StringProperty, NumericProperty, ListProperty,
    BooleanProperty, ObjectProperty, DictProperty
)
from kivy.animation import Animation
from kivy.metrics import dp, sp

# Import the API client
from api_client import ThemeParksSync, AttractionStatus

# Set window size for development (comment out for fullscreen Pi deployment)
Window.size = (800, 480)

# Configuration file path
CONFIG_PATH = Path(__file__).parent / "config.json"

# Default configuration
DEFAULT_CONFIG = {
    "default_park": "hollywood_studios",
    "favorites": [],
    "refresh_interval": 60
}

# Park display names
PARK_NAMES = {
    'magic_kingdom': 'Magic Kingdom',
    'epcot': 'EPCOT',
    'hollywood_studios': 'Hollywood Studios',
    'animal_kingdom': 'Animal Kingdom',
}

# Park short names for UI
PARK_SHORT_NAMES = {
    'magic_kingdom': 'MAGIC\nKINGDOM',
    'epcot': 'EPCOT',
    'hollywood_studios': 'HOLLYWOOD\nSTUDIOS',
    'animal_kingdom': 'ANIMAL\nKINGDOM',
}

# Featured attractions for home screen
FEATURED_ATTRACTIONS = {
    'magic_kingdom': ['Space Mountain', 'Big Thunder Mountain', 'Seven Dwarfs Mine Train', 'Haunted Mansion'],
    'epcot': ['Guardians of the Galaxy', 'Test Track', 'Frozen Ever After', 'Remy'],
    'hollywood_studios': ['Tower of Terror', 'Slinky Dog Dash', 'Rise of the Resistance', 'Rock'],
    'animal_kingdom': ['Flight of Passage', 'Expedition Everest', 'Kilimanjaro Safaris', 'Na\'vi River'],
}


def load_config():
    """Load configuration from file"""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)
                # Merge with defaults for any missing keys
                return {**DEFAULT_CONFIG, **config}
        except Exception as e:
            print(f"Error loading config: {e}")
    return DEFAULT_CONFIG.copy()


def save_config(config):
    """Save configuration to file"""
    try:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Error saving config: {e}")


class StarWidget(Widget):
    """A decorative 4-pointed star"""

    star_color = ListProperty([0.96, 0.88, 0.55, 1])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._gfx_group = InstructionGroup()
        self.canvas.add(self._gfx_group)
        self.bind(pos=self.draw_star, size=self.draw_star)
        Clock.schedule_once(lambda dt: self.draw_star())

    def draw_star(self, *args):
        self._gfx_group.clear()
        cx, cy = self.center
        w, h = self.size[0] / 2, self.size[1] / 2

        self._gfx_group.add(Color(*self.star_color))
        self._gfx_group.add(Line(
            points=[cx, cy + h, cx - w * 0.3, cy, cx, cy - h, cx + w * 0.3, cy, cx, cy + h],
            width=1.5, close=True
        ))
        self._gfx_group.add(Ellipse(pos=(cx - w * 0.4, cy - h * 0.4), size=(w * 0.8, h * 0.8)))


class MoonWidget(Widget):
    """A decorative crescent moon"""

    moon_color = ListProperty([0.96, 0.88, 0.55, 1])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._gfx_group = InstructionGroup()
        self.canvas.add(self._gfx_group)
        self.bind(pos=self.draw_moon, size=self.draw_moon)
        Clock.schedule_once(lambda dt: self.draw_moon())

    def draw_moon(self, *args):
        self._gfx_group.clear()
        self._gfx_group.add(Color(*self.moon_color))
        self._gfx_group.add(Ellipse(pos=self.pos, size=self.size))
        self._gfx_group.add(Color(0.0, 0.4, 0.85, 1))
        offset_x = self.size[0] * 0.3
        self._gfx_group.add(Ellipse(
            pos=(self.pos[0] + offset_x, self.pos[1]),
            size=(self.size[0] * 0.85, self.size[1] * 0.85)
        ))


class MagicBandScanner(RelativeLayout):
    """The MagicBand touch point scanner widget"""

    park_name = StringProperty("HOLLYWOOD\nSTUDIOS")
    glow_opacity = NumericProperty(0.8)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._gfx_group = InstructionGroup()
        self.canvas.before.add(self._gfx_group)
        self.bind(pos=self.draw_scanner, size=self.draw_scanner)
        self.bind(glow_opacity=self.draw_scanner)
        Clock.schedule_once(lambda dt: self.draw_scanner())
        self.start_pulse_animation()

    def start_pulse_animation(self):
        anim = Animation(glow_opacity=1.0, duration=0.8)
        anim += Animation(glow_opacity=0.5, duration=0.8)
        anim.repeat = True
        anim.start(self)

    def draw_scanner(self, *args):
        self._gfx_group.clear()
        self._gfx_group.add(Color(0.2, 0.9, 0.3, self.glow_opacity * 0.5))
        ring_size = (self.size[0] * 1.1, self.size[1] * 1.1)
        ring_pos = (
            self.pos[0] - (ring_size[0] - self.size[0]) / 2,
            self.pos[1] - (ring_size[1] - self.size[1]) / 2
        )
        self._gfx_group.add(Ellipse(pos=ring_pos, size=ring_size))
        self._gfx_group.add(Color(0.35, 0.35, 0.35, 1))
        self._gfx_group.add(Ellipse(pos=self.pos, size=self.size))
        self._gfx_group.add(Color(0.2, 0.9, 0.3, self.glow_opacity))
        inner_margin = self.size[0] * 0.08
        inner_size = (self.size[0] - inner_margin * 2, self.size[1] - inner_margin * 2)
        inner_pos = (self.pos[0] + inner_margin, self.pos[1] + inner_margin)
        self._gfx_group.add(Line(
            ellipse=(inner_pos[0], inner_pos[1], inner_size[0], inner_size[1]),
            width=dp(4)
        ))
        self._gfx_group.add(Color(0.6, 0.5, 0.35, 1))
        center_margin = self.size[0] * 0.15
        center_size = (self.size[0] - center_margin * 2, self.size[1] - center_margin * 2)
        center_pos = (self.pos[0] + center_margin, self.pos[1] + center_margin)
        self._gfx_group.add(Ellipse(pos=center_pos, size=center_size))

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.trigger_scan()
            return True
        return super().on_touch_down(touch)

    def trigger_scan(self):
        anim = Animation(glow_opacity=1.0, duration=0.1)
        anim += Animation(glow_opacity=0.3, duration=0.1)
        anim += Animation(glow_opacity=1.0, duration=0.1)
        anim += Animation(glow_opacity=0.3, duration=0.1)
        anim += Animation(glow_opacity=0.8, duration=0.3)
        anim.start(self)


class FastpassTicket(RelativeLayout):
    """The main fastpass-style ticket showing wait time"""

    ride_name = StringProperty("Tower\nTerror")
    wait_time = NumericProperty(45)
    status = StringProperty("OPERATING")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._gfx_group = InstructionGroup()
        self.canvas.before.add(self._gfx_group)
        self.bind(pos=self.draw_ticket, size=self.draw_ticket)
        Clock.schedule_once(lambda dt: self.draw_ticket())
        Clock.schedule_once(lambda dt: self.build_ui(), 0.1)

    def draw_ticket(self, *args):
        self._gfx_group.clear()
        colors = [
            (0.91, 0.12, 0.39, 1),
            (0.55, 0.76, 0.29, 1),
            (1.0, 0.6, 0.0, 1),
            (0.30, 0.69, 0.31, 1),
        ]

        for i, color in enumerate(colors):
            self._gfx_group.add(Color(*color))
            offset_x = -20 + (i * 8)
            ticket_width = self.size[0] * 0.5
            ticket_height = self.size[1] * 1.1
            self._gfx_group.add(RoundedRectangle(
                pos=(self.pos[0] + offset_x + dp(20), self.pos[1] - dp(20)),
                size=(ticket_width, ticket_height),
                radius=[dp(5)]
            ))

        self._gfx_group.add(Color(1, 1, 1, 1))
        main_width = self.size[0] * 0.55
        main_height = self.size[1] * 0.95
        main_x = self.pos[0] + dp(50)
        main_y = self.pos[1]
        self._gfx_group.add(RoundedRectangle(
            pos=(main_x, main_y),
            size=(main_width, main_height),
            radius=[dp(8)]
        ))

        self._gfx_group.add(Color(0.0, 0.75, 0.85, 1))
        header_height = main_height * 0.22
        self._gfx_group.add(RoundedRectangle(
            pos=(main_x, main_y + main_height - header_height),
            size=(main_width, header_height),
            radius=[dp(8), dp(8), 0, 0]
        ))

    def build_ui(self):
        self.clear_widgets()
        main_width = self.size[0] * 0.55

        ride_label = Label(
            text=self.ride_name,
            font_size=sp(22),
            bold=True,
            color=(1, 1, 1, 1),
            halign='center',
            size_hint=(None, None),
            size=(main_width, dp(60)),
            pos_hint={'center_x': 0.35, 'top': 0.95}
        )
        self.add_widget(ride_label)

        wait_label = Label(
            text="WAIT TIME",
            font_size=sp(14),
            color=(0.3, 0.3, 0.3, 1),
            halign='center',
            size_hint=(None, None),
            size=(main_width, dp(20)),
            pos_hint={'center_x': 0.35, 'center_y': 0.55}
        )
        self.add_widget(wait_label)

        display_text = str(self.wait_time) if self.status == "OPERATING" and self.wait_time else "--"
        self.time_label = Label(
            text=display_text,
            font_size=sp(48),
            bold=True,
            color=(0.1, 0.1, 0.1, 1),
            halign='center',
            size_hint=(None, None),
            size=(dp(80), dp(60)),
            pos_hint={'center_x': 0.35, 'center_y': 0.4}
        )
        self.add_widget(self.time_label)

        status_text = "MINUTES" if self.status == "OPERATING" else self.status
        self.status_label = Label(
            text=status_text,
            font_size=sp(14),
            color=(0.3, 0.3, 0.3, 1) if self.status == "OPERATING" else (0.8, 0.2, 0.2, 1),
            halign='center',
            size_hint=(None, None),
            size=(main_width, dp(20)),
            pos_hint={'center_x': 0.35, 'center_y': 0.22}
        )
        self.add_widget(self.status_label)

    def update_wait_time(self, new_time, status="OPERATING"):
        self.wait_time = new_time if new_time else 0
        self.status = status
        if hasattr(self, 'time_label'):
            anim = Animation(color=(0, 0.5, 1, 1), duration=0.2)
            anim += Animation(color=(0.1, 0.1, 0.1, 1), duration=0.3)
            anim.start(self.time_label)
            self.time_label.text = str(new_time) if status == "OPERATING" and new_time else "--"
        if hasattr(self, 'status_label'):
            self.status_label.text = "MINUTES" if status == "OPERATING" else status
            self.status_label.color = (0.3, 0.3, 0.3, 1) if status == "OPERATING" else (0.8, 0.2, 0.2, 1)


class NavButton(Button):
    """Bottom navigation tab button"""

    is_active = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_down = ''
        self.bind(is_active=self.update_style)
        self.update_style()

    def update_style(self, *args):
        if self.is_active:
            self.background_color = (0.2, 0.5, 0.7, 1)
            self.color = (1, 1, 1, 1)
        else:
            self.background_color = (0.1, 0.3, 0.5, 0.8)
            self.color = (0.8, 0.9, 1, 1)


class NavBar(BoxLayout):
    """Shared navigation bar component"""

    current_screen = StringProperty('parks')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint = (1, 0.12)
        self.pos_hint = {'x': 0, 'y': 0}
        self.spacing = dp(10)
        self.padding = [dp(15), dp(8)]

        self._gfx_group = InstructionGroup()
        self.canvas.before.add(self._gfx_group)
        self.bind(pos=self._draw_bg, size=self._draw_bg)

        self.buttons = {}
        tabs = ['home', 'resort', 'parks', 'vacation']

        for tab in tabs:
            btn = NavButton(
                text=tab.upper(),
                font_size=sp(16),
                bold=True,
                is_active=(tab == self.current_screen),
                size_hint=(1, 1)
            )
            btn.bind(on_press=partial(self.on_tab_press, tab))
            self.buttons[tab] = btn
            self.add_widget(btn)

    def _draw_bg(self, *args):
        self._gfx_group.clear()
        self._gfx_group.add(Color(0.05, 0.25, 0.45, 0.9))
        self._gfx_group.add(Rectangle(pos=self.pos, size=self.size))

    def on_tab_press(self, tab_name, instance):
        app = App.get_running_app()
        if app and app.root:
            app.root.current = tab_name
            self.update_active(tab_name)

    def update_active(self, active_tab):
        self.current_screen = active_tab
        for tab, btn in self.buttons.items():
            btn.is_active = (tab == active_tab)


class WaitTimeCard(Button):
    """A card showing an attraction's wait time"""

    attraction_name = StringProperty("")
    wait_time = NumericProperty(0)
    park_name = StringProperty("")
    status = StringProperty("OPERATING")

    def __init__(self, **kwargs):
        self.attraction_name = kwargs.pop('attraction_name', '')
        self.wait_time = kwargs.pop('wait_time', 0)
        self.park_name = kwargs.pop('park_name', '')
        self.status = kwargs.pop('status', 'OPERATING')
        super().__init__(**kwargs)

        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0.1, 0.35, 0.6, 0.9)

        self._gfx_group = InstructionGroup()
        self.canvas.before.add(self._gfx_group)
        self.bind(pos=self._draw, size=self._draw)

        self.build_content()

    def _draw(self, *args):
        self._gfx_group.clear()
        self._gfx_group.add(Color(0.1, 0.35, 0.6, 0.9))
        self._gfx_group.add(RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)]))

    def build_content(self):
        layout = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(4))

        name_label = Label(
            text=self.attraction_name[:20] + ('...' if len(self.attraction_name) > 20 else ''),
            font_size=sp(12),
            bold=True,
            color=(1, 1, 1, 1),
            halign='center',
            valign='top',
            size_hint=(1, 0.4)
        )
        name_label.bind(size=name_label.setter('text_size'))
        layout.add_widget(name_label)

        if self.status == "OPERATING" and self.wait_time:
            time_label = Label(
                text=str(self.wait_time),
                font_size=sp(28),
                bold=True,
                color=(0.2, 0.9, 0.3, 1),
                size_hint=(1, 0.4)
            )
        else:
            time_label = Label(
                text="--",
                font_size=sp(28),
                bold=True,
                color=(0.6, 0.6, 0.6, 1),
                size_hint=(1, 0.4)
            )
        layout.add_widget(time_label)

        min_label = Label(
            text="min" if self.status == "OPERATING" else self.status[:8],
            font_size=sp(10),
            color=(0.7, 0.8, 0.9, 1),
            size_hint=(1, 0.2)
        )
        layout.add_widget(min_label)

        self.add_widget(layout)


class ParkCard(Button):
    """A card for selecting a park"""

    park_id = StringProperty("")
    park_name = StringProperty("")
    avg_wait = NumericProperty(0)
    is_open = BooleanProperty(True)

    def __init__(self, **kwargs):
        self.park_id = kwargs.pop('park_id', '')
        self.park_name = kwargs.pop('park_name', '')
        self.avg_wait = kwargs.pop('avg_wait', 0)
        self.is_open = kwargs.pop('is_open', True)
        super().__init__(**kwargs)

        self.background_normal = ''
        self.background_down = ''

        self._gfx_group = InstructionGroup()
        self.canvas.before.add(self._gfx_group)
        self.bind(pos=self._draw, size=self._draw)

        self.build_content()

    def _draw(self, *args):
        self._gfx_group.clear()
        color = (0.1, 0.4, 0.65, 1) if self.is_open else (0.3, 0.3, 0.35, 1)
        self._gfx_group.add(Color(*color))
        self._gfx_group.add(RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(15)]))

    def build_content(self):
        layout = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(5))

        name_label = Label(
            text=self.park_name,
            font_size=sp(18),
            bold=True,
            color=(1, 1, 1, 1),
            halign='center',
            valign='middle',
            size_hint=(1, 0.5)
        )
        name_label.bind(size=name_label.setter('text_size'))
        layout.add_widget(name_label)

        if self.is_open:
            wait_label = Label(
                text=f"Avg: {self.avg_wait} min" if self.avg_wait else "Loading...",
                font_size=sp(14),
                color=(0.2, 0.9, 0.3, 1),
                size_hint=(1, 0.3)
            )
        else:
            wait_label = Label(
                text="CLOSED",
                font_size=sp(14),
                color=(0.8, 0.4, 0.4, 1),
                size_hint=(1, 0.3)
            )
        layout.add_widget(wait_label)

        self.add_widget(layout)


class BaseScreen(Screen):
    """Base screen with common functionality"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.api_client = None
        self._data_cache = {}

    def on_enter(self):
        """Called when screen is displayed"""
        app = App.get_running_app()
        if app:
            self.api_client = app.api_client
            # Update nav bar
            for screen in app.root.screens:
                if hasattr(screen, 'nav_bar'):
                    screen.nav_bar.update_active(self.name)

    def get_app(self):
        return App.get_running_app()


class HomeScreen(BaseScreen):
    """Home screen showing featured attractions across all parks"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.attractions_data = {}
        self.build_ui()

    def build_ui(self):
        layout = FloatLayout()

        with layout.canvas.before:
            Color(0.0, 0.4, 0.85, 1)
            self.bg_rect = Rectangle(pos=layout.pos, size=Window.size)
        layout.bind(size=self._update_bg, pos=self._update_bg)

        # Header
        header = Label(
            text="Walt Disney World",
            font_size=sp(28),
            bold=True,
            color=(1, 1, 1, 1),
            size_hint=(1, 0.12),
            pos_hint={'x': 0, 'top': 1}
        )
        layout.add_widget(header)

        # Subtitle
        self.time_label = Label(
            text=datetime.now().strftime("%A, %B %d"),
            font_size=sp(14),
            color=(0.8, 0.9, 1, 1),
            size_hint=(1, 0.06),
            pos_hint={'x': 0, 'top': 0.88}
        )
        layout.add_widget(self.time_label)

        # Featured attractions grid
        self.grid_container = FloatLayout(
            size_hint=(0.95, 0.65),
            pos_hint={'center_x': 0.5, 'center_y': 0.48}
        )
        layout.add_widget(self.grid_container)

        # Loading label
        self.loading_label = Label(
            text="Loading wait times...",
            font_size=sp(16),
            color=(0.8, 0.9, 1, 1),
            size_hint=(1, 1)
        )
        self.grid_container.add_widget(self.loading_label)

        # Navigation bar
        self.nav_bar = NavBar(current_screen='home')
        layout.add_widget(self.nav_bar)

        self.add_widget(layout)

    def _update_bg(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def on_enter(self):
        super().on_enter()
        self.time_label.text = datetime.now().strftime("%A, %B %d")
        Clock.schedule_once(lambda dt: self.fetch_featured_attractions(), 0.1)

    def fetch_featured_attractions(self):
        """Fetch wait times for featured attractions"""
        if not self.api_client:
            return

        def fetch_in_thread():
            all_attractions = []
            for park_id in ['magic_kingdom', 'epcot', 'hollywood_studios', 'animal_kingdom']:
                try:
                    data = self.api_client.get_live_data(park_id)
                    featured = FEATURED_ATTRACTIONS.get(park_id, [])
                    for name, wait in data.items():
                        for feat in featured:
                            if feat.lower() in name.lower():
                                all_attractions.append({
                                    'name': name,
                                    'wait': wait,
                                    'park': park_id
                                })
                                break
                except Exception as e:
                    print(f"Error fetching {park_id}: {e}")

            Clock.schedule_once(lambda dt: self.update_grid(all_attractions))

        thread = threading.Thread(target=fetch_in_thread)
        thread.daemon = True
        thread.start()

    def update_grid(self, attractions):
        """Update the grid with attraction data"""
        self.grid_container.clear_widgets()

        if not attractions:
            self.grid_container.add_widget(Label(
                text="Unable to load wait times.\nCheck your connection.",
                font_size=sp(16),
                color=(0.8, 0.9, 1, 1),
                halign='center'
            ))
            return

        grid = GridLayout(
            cols=4,
            rows=2,
            spacing=dp(10),
            padding=dp(10),
            size_hint=(1, 1)
        )

        # Sort by wait time (highest first) and take top 8
        attractions.sort(key=lambda x: x['wait'] or 0, reverse=True)
        for attr in attractions[:8]:
            card = WaitTimeCard(
                attraction_name=attr['name'],
                wait_time=attr['wait'] or 0,
                park_name=attr['park'],
                status="OPERATING" if attr['wait'] else "CLOSED",
                size_hint=(1, 1)
            )
            grid.add_widget(card)

        self.grid_container.add_widget(grid)


class ResortScreen(BaseScreen):
    """Resort screen showing park selection"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.park_cards = {}
        self.build_ui()

    def build_ui(self):
        layout = FloatLayout()

        with layout.canvas.before:
            Color(0.0, 0.35, 0.7, 1)
            self.bg_rect = Rectangle(pos=layout.pos, size=Window.size)
        layout.bind(size=self._update_bg, pos=self._update_bg)

        # Header
        header = Label(
            text="Select a Park",
            font_size=sp(26),
            bold=True,
            color=(1, 1, 1, 1),
            size_hint=(1, 0.12),
            pos_hint={'x': 0, 'top': 1}
        )
        layout.add_widget(header)

        # Park grid (2x2)
        self.parks_grid = GridLayout(
            cols=2,
            rows=2,
            spacing=dp(20),
            padding=dp(20),
            size_hint=(0.9, 0.7),
            pos_hint={'center_x': 0.5, 'center_y': 0.48}
        )

        parks = [
            ('magic_kingdom', 'Magic Kingdom'),
            ('epcot', 'EPCOT'),
            ('hollywood_studios', 'Hollywood\nStudios'),
            ('animal_kingdom', 'Animal\nKingdom'),
        ]

        for park_id, park_name in parks:
            card = ParkCard(
                park_id=park_id,
                park_name=park_name,
                size_hint=(1, 1)
            )
            card.bind(on_press=partial(self.on_park_select, park_id))
            self.park_cards[park_id] = card
            self.parks_grid.add_widget(card)

        layout.add_widget(self.parks_grid)

        # Navigation bar
        self.nav_bar = NavBar(current_screen='resort')
        layout.add_widget(self.nav_bar)

        self.add_widget(layout)

    def _update_bg(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def on_enter(self):
        super().on_enter()
        Clock.schedule_once(lambda dt: self.fetch_park_stats(), 0.1)

    def fetch_park_stats(self):
        """Fetch average wait times for each park"""
        if not self.api_client:
            return

        def fetch_in_thread():
            stats = {}
            for park_id in ['magic_kingdom', 'epcot', 'hollywood_studios', 'animal_kingdom']:
                try:
                    data = self.api_client.get_live_data(park_id)
                    waits = [w for w in data.values() if w is not None and w > 0]
                    avg = int(sum(waits) / len(waits)) if waits else 0
                    stats[park_id] = {'avg': avg, 'open': len(waits) > 0}
                except Exception as e:
                    print(f"Error fetching {park_id}: {e}")
                    stats[park_id] = {'avg': 0, 'open': False}

            Clock.schedule_once(lambda dt: self.update_cards(stats))

        thread = threading.Thread(target=fetch_in_thread)
        thread.daemon = True
        thread.start()

    def update_cards(self, stats):
        """Update park cards with stats"""
        for park_id, card in self.park_cards.items():
            if park_id in stats:
                card.avg_wait = stats[park_id]['avg']
                card.is_open = stats[park_id]['open']
                # Rebuild the card content
                card.clear_widgets()
                card.build_content()

    def on_park_select(self, park_id, instance):
        """Handle park selection"""
        app = App.get_running_app()
        if app:
            app.selected_park = park_id
            app.root.current = 'parks'


class ParksScreen(BaseScreen):
    """Main parks screen showing wait times for selected park"""

    current_park = StringProperty("hollywood_studios")
    current_ride = StringProperty("Tower of Terror")
    current_wait = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.attractions_list = []
        self.current_attraction_index = 0
        self.build_ui()

    def build_ui(self):
        layout = FloatLayout()

        with layout.canvas.before:
            Color(0.0, 0.4, 0.85, 1)
            self.bg_rect = Rectangle(pos=layout.pos, size=Window.size)
        layout.bind(size=self._update_bg, pos=self._update_bg)

        self.add_decorations(layout)

        # Fastpass ticket
        self.ticket = FastpassTicket(
            size_hint=(0.5, 0.7),
            pos_hint={'x': 0.02, 'center_y': 0.55},
            ride_name=self.current_ride,
            wait_time=self.current_wait
        )
        layout.add_widget(self.ticket)

        # MagicBand scanner
        self.scanner = MagicBandScanner(
            size_hint=(None, None),
            size=(dp(140), dp(140)),
            pos_hint={'right': 0.92, 'center_y': 0.5},
            park_name=PARK_SHORT_NAMES.get(self.current_park, "PARKS")
        )
        layout.add_widget(self.scanner)

        # Park name label
        self.park_label = Label(
            text=PARK_SHORT_NAMES.get(self.current_park, "PARKS"),
            font_size=sp(14),
            bold=True,
            color=(0.2, 0.9, 0.3, 1),
            halign='center',
            valign='middle',
            size_hint=(None, None),
            size=(dp(100), dp(50)),
            pos_hint={'right': 0.88, 'center_y': 0.5}
        )
        self.park_label.bind(size=self.park_label.setter('text_size'))
        layout.add_widget(self.park_label)

        # Navigation arrows for cycling attractions
        left_btn = Button(
            text='<',
            font_size=sp(24),
            bold=True,
            size_hint=(None, None),
            size=(dp(40), dp(60)),
            pos_hint={'x': 0.52, 'center_y': 0.55},
            background_normal='',
            background_color=(0.2, 0.5, 0.7, 0.8)
        )
        left_btn.bind(on_press=lambda x: self.prev_attraction())
        layout.add_widget(left_btn)

        right_btn = Button(
            text='>',
            font_size=sp(24),
            bold=True,
            size_hint=(None, None),
            size=(dp(40), dp(60)),
            pos_hint={'x': 0.58, 'center_y': 0.55},
            background_normal='',
            background_color=(0.2, 0.5, 0.7, 0.8)
        )
        right_btn.bind(on_press=lambda x: self.next_attraction())
        layout.add_widget(right_btn)

        # Navigation bar
        self.nav_bar = NavBar(current_screen='parks')
        layout.add_widget(self.nav_bar)

        self.add_widget(layout)

    def _update_bg(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def add_decorations(self, layout):
        star_positions = [
            {'x': 0.85, 'y': 0.8, 'size': 40},
            {'x': 0.92, 'y': 0.65, 'size': 30},
            {'x': 0.75, 'y': 0.25, 'size': 28},
        ]

        for pos in star_positions:
            star = StarWidget(
                size_hint=(None, None),
                size=(dp(pos['size']), dp(pos['size'])),
                pos_hint={'x': pos['x'], 'y': pos['y']}
            )
            layout.add_widget(star)

        moon_positions = [
            {'x': 0.08, 'y': 0.75, 'size': 45},
            {'x': 0.85, 'y': 0.18, 'size': 35},
        ]

        for pos in moon_positions:
            moon = MoonWidget(
                size_hint=(None, None),
                size=(dp(pos['size']), dp(pos['size'])),
                pos_hint={'x': pos['x'], 'y': pos['y']}
            )
            layout.add_widget(moon)

    def on_enter(self):
        super().on_enter()
        app = App.get_running_app()
        if app and hasattr(app, 'selected_park'):
            self.current_park = app.selected_park

        self.park_label.text = PARK_SHORT_NAMES.get(self.current_park, "PARKS")
        self.scanner.park_name = PARK_SHORT_NAMES.get(self.current_park, "PARKS")

        Clock.schedule_once(lambda dt: self.fetch_wait_times(), 0.1)

    def fetch_wait_times(self):
        """Fetch real wait times from API"""
        if not self.api_client:
            return

        def fetch_in_thread():
            try:
                data = self.api_client.get_live_data(self.current_park)
                attractions = []
                for name, wait in data.items():
                    attractions.append({
                        'name': name,
                        'wait': wait,
                        'status': 'OPERATING' if wait is not None else 'CLOSED'
                    })

                # Sort by wait time
                attractions.sort(key=lambda x: x['wait'] or 0, reverse=True)
                Clock.schedule_once(lambda dt: self.update_attractions(attractions))
            except Exception as e:
                print(f"Error fetching wait times: {e}")

        thread = threading.Thread(target=fetch_in_thread)
        thread.daemon = True
        thread.start()

    def update_attractions(self, attractions):
        """Update the attractions list"""
        self.attractions_list = attractions
        self.current_attraction_index = 0
        if attractions:
            self.show_attraction(0)

    def show_attraction(self, index):
        """Show attraction at given index"""
        if not self.attractions_list:
            return

        index = index % len(self.attractions_list)
        self.current_attraction_index = index
        attr = self.attractions_list[index]

        # Format name for ticket display
        name = attr['name']
        if len(name) > 15:
            words = name.split()
            if len(words) > 1:
                mid = len(words) // 2
                name = ' '.join(words[:mid]) + '\n' + ' '.join(words[mid:])

        self.ticket.ride_name = name
        self.ticket.update_wait_time(attr['wait'], attr['status'])
        self.ticket.build_ui()

    def next_attraction(self):
        self.show_attraction(self.current_attraction_index + 1)

    def prev_attraction(self):
        self.show_attraction(self.current_attraction_index - 1)


class VacationScreen(BaseScreen):
    """Vacation screen showing favorites"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.favorites = []
        self.build_ui()

    def build_ui(self):
        layout = FloatLayout()

        with layout.canvas.before:
            Color(0.05, 0.3, 0.55, 1)
            self.bg_rect = Rectangle(pos=layout.pos, size=Window.size)
        layout.bind(size=self._update_bg, pos=self._update_bg)

        # Header
        header = Label(
            text="My Favorites",
            font_size=sp(26),
            bold=True,
            color=(1, 1, 1, 1),
            size_hint=(1, 0.12),
            pos_hint={'x': 0, 'top': 1}
        )
        layout.add_widget(header)

        # Favorites container
        self.favorites_container = FloatLayout(
            size_hint=(0.95, 0.7),
            pos_hint={'center_x': 0.5, 'center_y': 0.48}
        )
        layout.add_widget(self.favorites_container)

        # Empty state
        self.empty_label = Label(
            text="No favorites yet!\n\nVisit the Parks tab and\nlong-press an attraction\nto add it here.",
            font_size=sp(16),
            color=(0.7, 0.8, 0.9, 1),
            halign='center',
            size_hint=(1, 1)
        )
        self.favorites_container.add_widget(self.empty_label)

        # Navigation bar
        self.nav_bar = NavBar(current_screen='vacation')
        layout.add_widget(self.nav_bar)

        self.add_widget(layout)

    def _update_bg(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def on_enter(self):
        super().on_enter()
        app = App.get_running_app()
        if app:
            self.favorites = app.config.get('favorites', [])
        self.update_favorites_display()

    def update_favorites_display(self):
        """Update the favorites display"""
        self.favorites_container.clear_widgets()

        if not self.favorites:
            self.favorites_container.add_widget(Label(
                text="No favorites yet!\n\nVisit the Parks tab and\nlong-press an attraction\nto add it here.",
                font_size=sp(16),
                color=(0.7, 0.8, 0.9, 1),
                halign='center',
                size_hint=(1, 1)
            ))
            return

        # Create scrollable list
        scroll = ScrollView(size_hint=(1, 1))
        grid = GridLayout(
            cols=2,
            spacing=dp(10),
            padding=dp(10),
            size_hint_y=None
        )
        grid.bind(minimum_height=grid.setter('height'))

        for fav in self.favorites:
            card = WaitTimeCard(
                attraction_name=fav.get('attraction', ''),
                wait_time=fav.get('wait', 0),
                park_name=fav.get('park', ''),
                size_hint_y=None,
                height=dp(100)
            )
            grid.add_widget(card)

        scroll.add_widget(grid)
        self.favorites_container.add_widget(scroll)


class DisneyWaitApp(App):
    """Main application"""

    selected_park = StringProperty('hollywood_studios')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.api_client = None
        self.config = {}

    def build(self):
        # Load configuration
        self.config = load_config()
        self.selected_park = self.config.get('default_park', 'hollywood_studios')

        # Initialize API client
        self.api_client = ThemeParksSync()

        # Screen manager for navigation
        sm = ScreenManager(transition=SlideTransition())

        sm.add_widget(HomeScreen(name='home'))
        sm.add_widget(ResortScreen(name='resort'))
        sm.add_widget(ParksScreen(name='parks'))
        sm.add_widget(VacationScreen(name='vacation'))

        # Start on parks screen
        sm.current = 'parks'

        return sm

    def on_start(self):
        """Called when the app starts"""
        print("Disney Wait Display started!")
        print(f"Default park: {self.selected_park}")

    def on_stop(self):
        """Called when the app stops"""
        if self.api_client:
            self.api_client.close()
        save_config(self.config)


if __name__ == '__main__':
    DisneyWaitApp().run()

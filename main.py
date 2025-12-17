"""
Disney Theme Park Wait Time Display
A Kivy-based touchscreen interface for Raspberry Pi
"""

import json
import threading
from datetime import datetime
from pathlib import Path
from functools import partial

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.properties import StringProperty, NumericProperty, BooleanProperty
from kivy.metrics import dp, sp

from api_client import ThemeParksSync

# Set window size for development
Window.size = (800, 480)

# Configuration
CONFIG_PATH = Path(__file__).parent / "config.json"
DEFAULT_CONFIG = {
    "default_park": "magic_kingdom",
    "favorites": [],
    "refresh_interval": 60
}

# Park info
PARKS = {
    'magic_kingdom': {'name': 'Magic Kingdom', 'short': 'MK'},
    'epcot': {'name': 'EPCOT', 'short': 'EP'},
    'hollywood_studios': {'name': 'Hollywood Studios', 'short': 'HS'},
    'animal_kingdom': {'name': 'Animal Kingdom', 'short': 'AK'},
}


def load_config():
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, 'r') as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config):
    try:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
    except:
        pass


class StyledButton(Button):
    """Simple styled button"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_color = (0.1, 0.4, 0.6, 1)
        self.color = (1, 1, 1, 1)
        self.bold = True


class NavBar(BoxLayout):
    """Bottom navigation bar"""
    def __init__(self, current='parks', **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint = (1, None)
        self.height = dp(55)
        self.spacing = dp(2)

        with self.canvas.before:
            Color(0.08, 0.2, 0.35, 1)
            self.bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        self.buttons = {}
        for tab in ['home', 'resort', 'parks', 'vacation']:
            btn = Button(
                text=tab.upper(),
                font_size=sp(14),
                bold=True,
                background_normal='',
                background_color=(0.2, 0.5, 0.7, 1) if tab == current else (0.1, 0.3, 0.5, 1)
            )
            btn.bind(on_press=partial(self._on_press, tab))
            self.buttons[tab] = btn
            self.add_widget(btn)

    def _update_bg(self, *args):
        self.bg.pos = self.pos
        self.bg.size = self.size

    def _on_press(self, tab, instance):
        app = App.get_running_app()
        if app and app.root:
            app.root.current = tab
            for name, btn in self.buttons.items():
                btn.background_color = (0.2, 0.5, 0.7, 1) if name == tab else (0.1, 0.3, 0.5, 1)


class AttractionCard(BoxLayout):
    """Simple card showing attraction name and wait time"""
    def __init__(self, name="", wait=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = dp(8)
        self.spacing = dp(4)

        with self.canvas.before:
            Color(0.12, 0.35, 0.55, 1)
            self.bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(8)])
        self.bind(pos=self._update_bg, size=self._update_bg)

        # Attraction name
        self.add_widget(Label(
            text=name[:25] + ('...' if len(name) > 25 else ''),
            font_size=sp(11),
            color=(1, 1, 1, 1),
            halign='center',
            valign='middle',
            size_hint=(1, 0.4),
            text_size=(None, None)
        ))

        # Wait time
        wait_text = str(wait) if wait else '--'
        wait_color = (0.3, 0.9, 0.4, 1) if wait else (0.6, 0.6, 0.6, 1)
        self.add_widget(Label(
            text=wait_text,
            font_size=sp(26),
            bold=True,
            color=wait_color,
            size_hint=(1, 0.4)
        ))

        # Min label
        self.add_widget(Label(
            text='min' if wait else 'closed',
            font_size=sp(10),
            color=(0.7, 0.8, 0.9, 1),
            size_hint=(1, 0.2)
        ))

    def _update_bg(self, *args):
        self.bg.pos = self.pos
        self.bg.size = self.size


class ParkButton(Button):
    """Button for selecting a park"""
    def __init__(self, park_id, park_name, avg_wait=0, **kwargs):
        super().__init__(**kwargs)
        self.park_id = park_id
        self.background_normal = ''
        self.background_color = (0.15, 0.4, 0.6, 1)
        self.font_size = sp(16)
        self.bold = True

        if avg_wait > 0:
            self.text = f"{park_name}\n[size=12]Avg: {avg_wait} min[/size]"
        else:
            self.text = f"{park_name}\n[size=12]Loading...[/size]"
        self.markup = True
        self.halign = 'center'


class BaseScreen(Screen):
    """Base screen class"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.api_client = None

    def on_enter(self):
        app = App.get_running_app()
        if app:
            self.api_client = app.api_client


class HomeScreen(BaseScreen):
    """Home screen - featured attractions from all parks"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        layout = BoxLayout(orientation='vertical')

        # Background
        with layout.canvas.before:
            Color(0.0, 0.35, 0.65, 1)
            self.bg = Rectangle(pos=layout.pos, size=Window.size)
        layout.bind(pos=self._update_bg, size=self._update_bg)

        # Header
        header = BoxLayout(size_hint=(1, 0.15), orientation='vertical', padding=[0, dp(10)])
        header.add_widget(Label(
            text='Walt Disney World',
            font_size=sp(24),
            bold=True,
            color=(1, 1, 1, 1)
        ))
        header.add_widget(Label(
            text=datetime.now().strftime("%A, %B %d"),
            font_size=sp(12),
            color=(0.8, 0.9, 1, 1)
        ))
        layout.add_widget(header)

        # Attractions grid container
        self.grid_container = BoxLayout(size_hint=(1, 0.73), padding=dp(10))
        self.loading_label = Label(text='Loading attractions...', color=(0.8, 0.9, 1, 1))
        self.grid_container.add_widget(self.loading_label)
        layout.add_widget(self.grid_container)

        # Nav bar
        layout.add_widget(NavBar(current='home'))

        self.add_widget(layout)

    def _update_bg(self, *args):
        self.bg.size = Window.size

    def on_enter(self):
        super().on_enter()
        Clock.schedule_once(lambda dt: self._fetch_data(), 0.1)

    def _fetch_data(self):
        if not self.api_client:
            return

        def fetch():
            results = []
            for park_id in PARKS.keys():
                try:
                    data = self.api_client.get_live_data(park_id)
                    for name, wait in list(data.items())[:3]:
                        results.append({'name': name, 'wait': wait, 'park': park_id})
                except:
                    pass
            Clock.schedule_once(lambda dt: self._update_ui(results))

        threading.Thread(target=fetch, daemon=True).start()

    def _update_ui(self, attractions):
        self.grid_container.clear_widgets()

        if not attractions:
            self.grid_container.add_widget(Label(
                text='Unable to load data.\nParks may be closed.',
                color=(0.8, 0.9, 1, 1),
                halign='center'
            ))
            return

        grid = GridLayout(cols=4, spacing=dp(8), padding=dp(5))

        # Sort by wait time and show top 8
        attractions.sort(key=lambda x: x['wait'] or 0, reverse=True)
        for attr in attractions[:8]:
            grid.add_widget(AttractionCard(name=attr['name'], wait=attr['wait']))

        self.grid_container.add_widget(grid)


class ResortScreen(BaseScreen):
    """Resort screen - park selection"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        layout = BoxLayout(orientation='vertical')

        with layout.canvas.before:
            Color(0.0, 0.3, 0.55, 1)
            self.bg = Rectangle(pos=layout.pos, size=Window.size)
        layout.bind(pos=self._update_bg, size=self._update_bg)

        # Header
        layout.add_widget(Label(
            text='Select a Park',
            font_size=sp(22),
            bold=True,
            size_hint=(1, 0.12)
        ))

        # Park grid
        self.park_grid = GridLayout(
            cols=2, rows=2,
            spacing=dp(15),
            padding=dp(20),
            size_hint=(1, 0.76)
        )

        self.park_buttons = {}
        for park_id, info in PARKS.items():
            btn = ParkButton(park_id, info['name'])
            btn.bind(on_press=self._on_park_select)
            self.park_buttons[park_id] = btn
            self.park_grid.add_widget(btn)

        layout.add_widget(self.park_grid)
        layout.add_widget(NavBar(current='resort'))

        self.add_widget(layout)

    def _update_bg(self, *args):
        self.bg.size = Window.size

    def on_enter(self):
        super().on_enter()
        Clock.schedule_once(lambda dt: self._fetch_stats(), 0.1)

    def _fetch_stats(self):
        if not self.api_client:
            return

        def fetch():
            stats = {}
            for park_id in PARKS.keys():
                try:
                    data = self.api_client.get_live_data(park_id)
                    waits = [w for w in data.values() if w and w > 0]
                    stats[park_id] = int(sum(waits) / len(waits)) if waits else 0
                except:
                    stats[park_id] = 0
            Clock.schedule_once(lambda dt: self._update_buttons(stats))

        threading.Thread(target=fetch, daemon=True).start()

    def _update_buttons(self, stats):
        for park_id, btn in self.park_buttons.items():
            avg = stats.get(park_id, 0)
            name = PARKS[park_id]['name']
            if avg > 0:
                btn.text = f"{name}\n[size=12]Avg: {avg} min[/size]"
            else:
                btn.text = f"{name}\n[size=12]Closed[/size]"

    def _on_park_select(self, btn):
        app = App.get_running_app()
        if app:
            app.selected_park = btn.park_id
            app.root.current = 'parks'


class ParksScreen(BaseScreen):
    """Parks screen - shows wait times for selected park"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.attractions = []
        self.current_index = 0

        layout = BoxLayout(orientation='vertical')

        with layout.canvas.before:
            Color(0.0, 0.35, 0.65, 1)
            self.bg = Rectangle(pos=layout.pos, size=Window.size)
        layout.bind(pos=self._update_bg, size=self._update_bg)

        # Header with park name
        self.header = Label(
            text='Magic Kingdom',
            font_size=sp(20),
            bold=True,
            size_hint=(1, 0.1)
        )
        layout.add_widget(self.header)

        # Main content area
        content = BoxLayout(orientation='horizontal', size_hint=(1, 0.65), padding=dp(15), spacing=dp(15))

        # Left side - current attraction
        left_box = BoxLayout(orientation='vertical', size_hint=(0.5, 1))

        # Attraction name
        self.ride_label = Label(
            text='Loading...',
            font_size=sp(18),
            bold=True,
            halign='center',
            valign='middle',
            size_hint=(1, 0.25)
        )
        self.ride_label.bind(size=lambda *x: setattr(self.ride_label, 'text_size', self.ride_label.size))
        left_box.add_widget(self.ride_label)

        # Wait time box
        wait_box = BoxLayout(orientation='vertical', size_hint=(1, 0.6))
        with wait_box.canvas.before:
            Color(1, 1, 1, 1)
            self.wait_bg = RoundedRectangle(pos=wait_box.pos, size=wait_box.size, radius=[dp(10)])
        wait_box.bind(pos=self._update_wait_bg, size=self._update_wait_bg)

        wait_box.add_widget(Label(text='WAIT TIME', font_size=sp(11), color=(0.4, 0.4, 0.4, 1), size_hint=(1, 0.2)))
        self.time_label = Label(text='--', font_size=sp(48), bold=True, color=(0.1, 0.1, 0.1, 1), size_hint=(1, 0.5))
        wait_box.add_widget(self.time_label)
        self.status_label = Label(text='MINUTES', font_size=sp(11), color=(0.4, 0.4, 0.4, 1), size_hint=(1, 0.3))
        wait_box.add_widget(self.status_label)

        left_box.add_widget(wait_box)

        # Counter
        self.counter_label = Label(text='0 / 0', font_size=sp(12), color=(0.7, 0.8, 0.9, 1), size_hint=(1, 0.15))
        left_box.add_widget(self.counter_label)

        content.add_widget(left_box)

        # Right side - attraction list
        right_box = BoxLayout(orientation='vertical', size_hint=(0.5, 1))
        right_box.add_widget(Label(text='All Attractions', font_size=sp(14), bold=True, size_hint=(1, 0.1)))

        scroll = ScrollView(size_hint=(1, 0.9))
        self.list_layout = GridLayout(cols=1, spacing=dp(5), size_hint_y=None, padding=dp(5))
        self.list_layout.bind(minimum_height=self.list_layout.setter('height'))
        scroll.add_widget(self.list_layout)
        right_box.add_widget(scroll)

        content.add_widget(right_box)
        layout.add_widget(content)

        # Navigation buttons
        nav_buttons = BoxLayout(size_hint=(1, 0.13), padding=dp(10), spacing=dp(10))

        prev_btn = StyledButton(text='< Previous', font_size=sp(14))
        prev_btn.bind(on_press=lambda x: self._show_prev())
        nav_buttons.add_widget(prev_btn)

        next_btn = StyledButton(text='Next >', font_size=sp(14))
        next_btn.bind(on_press=lambda x: self._show_next())
        nav_buttons.add_widget(next_btn)

        layout.add_widget(nav_buttons)
        layout.add_widget(NavBar(current='parks'))

        self.add_widget(layout)

    def _update_bg(self, *args):
        self.bg.size = Window.size

    def _update_wait_bg(self, instance, value):
        self.wait_bg.pos = instance.pos
        self.wait_bg.size = instance.size

    def on_enter(self):
        super().on_enter()
        app = App.get_running_app()
        park_id = app.selected_park if app else 'magic_kingdom'
        self.header.text = PARKS.get(park_id, {}).get('name', 'Park')
        Clock.schedule_once(lambda dt: self._fetch_data(park_id), 0.1)

    def _fetch_data(self, park_id):
        if not self.api_client:
            return

        def fetch():
            try:
                data = self.api_client.get_live_data(park_id)
                attrs = [{'name': n, 'wait': w} for n, w in data.items()]
                attrs.sort(key=lambda x: x['wait'] or 0, reverse=True)
                Clock.schedule_once(lambda dt: self._update_ui(attrs))
            except Exception as e:
                print(f"Error: {e}")

        threading.Thread(target=fetch, daemon=True).start()

    def _update_ui(self, attractions):
        self.attractions = attractions
        self.current_index = 0

        # Update list
        self.list_layout.clear_widgets()
        for attr in attractions:
            wait_str = f"{attr['wait']} min" if attr['wait'] else "Closed"
            btn = Button(
                text=f"{attr['name'][:30]}: {wait_str}",
                font_size=sp(11),
                size_hint_y=None,
                height=dp(35),
                background_normal='',
                background_color=(0.15, 0.4, 0.55, 1),
                halign='left',
                padding=[dp(10), 0]
            )
            btn.bind(size=lambda b, s: setattr(b, 'text_size', (s[0] - dp(20), None)))
            self.list_layout.add_widget(btn)

        self._show_attraction(0)

    def _show_attraction(self, index):
        if not self.attractions:
            return

        index = index % len(self.attractions)
        self.current_index = index
        attr = self.attractions[index]

        self.ride_label.text = attr['name']
        self.time_label.text = str(attr['wait']) if attr['wait'] else '--'
        self.status_label.text = 'MINUTES' if attr['wait'] else 'CLOSED'
        self.status_label.color = (0.4, 0.4, 0.4, 1) if attr['wait'] else (0.8, 0.2, 0.2, 1)
        self.counter_label.text = f"{index + 1} / {len(self.attractions)}"

    def _show_next(self):
        self._show_attraction(self.current_index + 1)

    def _show_prev(self):
        self._show_attraction(self.current_index - 1)


class VacationScreen(BaseScreen):
    """Vacation screen - favorites"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        layout = BoxLayout(orientation='vertical')

        with layout.canvas.before:
            Color(0.05, 0.25, 0.45, 1)
            self.bg = Rectangle(pos=layout.pos, size=Window.size)
        layout.bind(pos=self._update_bg, size=self._update_bg)

        # Header
        layout.add_widget(Label(
            text='My Favorites',
            font_size=sp(22),
            bold=True,
            size_hint=(1, 0.12)
        ))

        # Content
        self.content = BoxLayout(size_hint=(1, 0.76), padding=dp(20))
        self.content.add_widget(Label(
            text='No favorites yet!\n\nVisit the Parks tab to\nbrowse attractions.',
            font_size=sp(14),
            color=(0.7, 0.8, 0.9, 1),
            halign='center'
        ))
        layout.add_widget(self.content)

        layout.add_widget(NavBar(current='vacation'))

        self.add_widget(layout)

    def _update_bg(self, *args):
        self.bg.size = Window.size


class DisneyWaitApp(App):
    """Main application"""
    selected_park = StringProperty('magic_kingdom')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.api_client = None
        self.config = {}

    def build(self):
        self.config = load_config()
        self.selected_park = self.config.get('default_park', 'magic_kingdom')
        self.api_client = ThemeParksSync()

        sm = ScreenManager(transition=SlideTransition())
        sm.add_widget(HomeScreen(name='home'))
        sm.add_widget(ResortScreen(name='resort'))
        sm.add_widget(ParksScreen(name='parks'))
        sm.add_widget(VacationScreen(name='vacation'))
        sm.current = 'parks'

        return sm

    def on_start(self):
        print("Disney Wait Display started!")

    def on_stop(self):
        if self.api_client:
            self.api_client.close()
        save_config(self.config)


if __name__ == '__main__':
    DisneyWaitApp().run()

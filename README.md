# Disney Theme Park Wait Time Display

A Kivy-based touchscreen application for Raspberry Pi that displays real-time wait times from Disney theme parks using the themeparks.wiki API.

![Display Example](screenshot.png)

## Features

- **Real-time wait times** from themeparks.wiki API
- **Fastpass-style ticket UI** with animated wait time updates
- **MagicBand scanner visual** with pulsing glow animation
- **Multi-park support** (WDW, Disneyland, Universal)
- **Touch navigation** between Home, Resort, Parks, and Vacation screens
- **Offline caching** for resilient operation

## Hardware Requirements

- Raspberry Pi 4 (recommended) or Pi 3B+/Pi Zero 2 W
- 7" touchscreen display (official Pi display or compatible)
- MicroSD card (16GB+)
- Power supply (5V 3A for Pi 4)

## Software Setup

### 1. Raspberry Pi OS Setup

```bash
# Start with Raspberry Pi OS Lite or Desktop
sudo apt update && sudo apt upgrade -y

# Install Kivy dependencies
sudo apt install -y \
    python3-pip \
    python3-setuptools \
    python3-dev \
    build-essential \
    libgl1-mesa-dev \
    libgles2-mesa-dev \
    libdrm-dev \
    libgbm-dev \
    libudev-dev \
    libmtdev-dev \
    libinput-dev \
    libxkbcommon-dev
```

### 2. Install Python Dependencies

```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt

# For Raspberry Pi touchscreen support
pip install kivy[rpi]
```

### 3. Configure Kivy for Pi Touchscreen

Create/edit `~/.kivy/config.ini`:

```ini
[input]
mouse = mouse
mtdev_%(name)s = probesysfs,provider=mtdev
hid_%(name)s = probesysfs,provider=hidinput

[graphics]
fullscreen = auto
show_cursor = 0

[modules]
touchring =
```

### 4. Run the Application

```bash
# Development (windowed)
python main.py

# Production (fullscreen, no cursor)
KIVY_BCM_DISPMANX_ID=2 python main.py
```

## Project Structure

```
disney_wait_display/
├── main.py              # Main Kivy application
├── disneywait.kv        # KV layout definitions
├── api_client.py        # themeparks.wiki API client
├── requirements.txt     # Python dependencies
├── config.json          # User configuration (created on first run)
├── fonts/               # Custom fonts directory
│   └── (add Disney-style fonts here)
└── assets/              # Images and icons
    └── (add custom assets here)
```

## Configuration

Edit `config.json` to customize:

```json
{
    "default_park": "hollywood_studios",
    "featured_attractions": [
        "Tower of Terror",
        "Rock n Roller Coaster",
        "Slinky Dog Dash"
    ],
    "refresh_interval": 60,
    "show_closed_attractions": false,
    "theme": "night"
}
```

## API Information

This project uses the [themeparks.wiki](https://api.themeparks.wiki/) API.

**Available Parks:**
- Walt Disney World: `magic_kingdom`, `epcot`, `hollywood_studios`, `animal_kingdom`
- Disneyland Resort: `disneyland`, `california_adventure`
- Universal Orlando: `universal_studios`, `islands_of_adventure`
- Universal Hollywood: `universal_hollywood`

**API Endpoints:**
- `/v1/destinations` - List all destinations
- `/v1/entity/{id}` - Get entity details
- `/v1/entity/{id}/live` - Get live wait times
- `/v1/entity/{id}/children` - Get child entities

## Auto-Start on Boot

### Using systemd

Create `/etc/systemd/system/disney-display.service`:

```ini
[Unit]
Description=Disney Wait Time Display
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/disney_wait_display
Environment=KIVY_BCM_DISPMANX_ID=2
ExecStart=/home/pi/disney_wait_display/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable the service:

```bash
sudo systemctl enable disney-display.service
sudo systemctl start disney-display.service
```

## Customization

### Adding Custom Fonts

1. Download Disney-style fonts (e.g., Waltograph, Mickey)
2. Place `.ttf` files in the `fonts/` directory
3. Register in `main.py`:

```python
from kivy.core.text import LabelBase
LabelBase.register(name='Disney', fn_regular='fonts/waltograph.ttf')
```

### Changing Colors

Edit the color constants in `main.py`:

```python
DISNEY_BLUE = (0.0, 0.4, 0.85, 1)
STAR_GOLD = (0.96, 0.88, 0.55, 1)
SCANNER_GREEN = (0.2, 0.9, 0.3, 1)
```

### Adding New Screens

1. Create a new Screen class in `main.py`
2. Add to the ScreenManager in `DisneyWaitApp.build()`
3. Update navigation in `ParksScreen.on_tab_press()`

## Troubleshooting

### Black screen on Pi
- Check HDMI settings in `/boot/config.txt`
- Try: `KIVY_BCM_DISPMANX_ID=2 python main.py`

### Touch not working
- Verify touch input: `evtest`
- Check Kivy input config in `~/.kivy/config.ini`

### API errors
- Check internet connectivity
- Verify API is accessible: `curl https://api.themeparks.wiki/v1/destinations`
- Check rate limiting (API allows reasonable usage)

### High CPU usage
- Reduce animation frame rate
- Increase API cache TTL
- Lower display resolution

## License

This project is for personal/educational use. 

- themeparks.wiki API: Check their terms of service
- Disney trademarks: Property of The Walt Disney Company
- Kivy: MIT License

## Credits

- [themeparks.wiki](https://themeparks.wiki/) for the excellent API
- Kivy framework developers
- Inspired by various Disney MagicBand and park display designs

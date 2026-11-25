# TEVIS Frankfurt Ausländerbehörde Appointment Checker

Automated appointment monitoring tool for the Frankfurt am Main Ausländerbehörde (immigration office) TEVIS booking system. Continuously checks for available appointments and sends notifications via Telegram and/or desktop popup when appointments before your target date become available.

## Features

- 🔄 **Continuous Monitoring**: Automatically checks for new appointments at configurable intervals
- 📱 **Telegram Notifications**: Get instant alerts on your phone when appointments are available
- 🪟 **Desktop Popup**: Optional popup notifications with browser integration
- 🐳 **Docker Support**: Run multiple instances to monitor different appointment types
- ⚙️ **Flexible Configuration**: Support for various appointment types (student, employee, general, etc.)
- 🎯 **Target Date Filtering**: Only notifies when appointments are available on or before your preferred date

## Prerequisites

- Python 3.8 or higher
- Telegram Bot (optional, for notifications)
- Docker (optional, for containerized deployment)

## Installation

### Local Installation

#### 1. Clone the repository

```bash
git clone <repository-url>
cd tevis-abh-ffm
```

#### 2. Create and activate a virtual environment

```bash
python -m venv pyenv
# On Windows
.\pyenv\Scripts\Activate.ps1
# On Linux/macOS
source pyenv/bin/activate
```

#### 3. Install dependencies

```bash
pip install -r requirements.txt
# OR using pyproject.toml
pip install -e .
```

### Docker Installation

Build the Docker image:

```bash
docker build -t tevis-abh-ffm:latest .
# OR using the build script
.\Build.ps1
```

## Configuration

Create a `.env` file in the project root with the following variables:

```env
# Required: Target date for appointments (YYYY-MM-DD)
TARGET_DATE="2026-04-21"

# Optional: Show desktop popup notifications (default: True)
SHOW_POPUP=True

# Optional: Telegram Bot Token from @BotFather
TELEGRAM_BOT_TOKEN="your_bot_token_here"

# Optional: Comma-separated list of Telegram Chat IDs
TELEGRAM_CHAT_IDS="your_chat_id_here"

# Optional: Check interval in seconds (default: 30)
CHECK_DELAY=20

# Required: Start URL for appointment type
START_URL="https://tevis.ekom21.de/fra/select2?md=35"

# Required: Appointment type code
CNC_CODE="5792"

# Optional: Location code (discovered from redirect URL)
LOCATION_CODE="315"

# Optional: Number of persons for appointment (default: 1)
NO_PERSONS="1"

# Optional: Preferred location number (leave empty for any location)
LOCATION_NUMBER="2"
```

### Finding Your Appointment Type Codes

To get the correct `START_URL`, `CNC_CODE`, and `LOCATION_CODE` for your specific appointment:

1. **Visit the TEVIS website**: Go to <https://tevis.ekom21.de/fra>
2. **Select your appointment type**: Choose the category that matches your needs (e.g., Student, Employee, General services, etc.)
3. **Fill out the form**: Select your specific service and number of persons
4. **Check the redirect URL**: After submitting, look at the browser's address bar

The URL will look like this:

```
https://tevis.ekom21.de/fra/location?mdt=315&select_cnc=1&cnc-5792=1&cnc-1234=0
```

**Extract the values:**

- `mdt=315` → Your **LOCATION_CODE** is `315`
- `cnc-5792=1` → Your **CNC_CODE** is `5792` (the one set to `1`, ignore those set to `0`)
- The `md` parameter in the form page URL → Your **START_URL** parameter

**Example:**
If the form page was `https://tevis.ekom21.de/fra/select2?md=35` and the redirect shows `mdt=315&cnc-5792=1`:

```env
START_URL="https://tevis.ekom21.de/fra/select2?md=35"
CNC_CODE="5792"
LOCATION_CODE="315"
```

### Getting Telegram Chat ID

Run the helper script to get your chat ID:

```bash
python get_users.py
```

Then send a message to your bot and run the script again to see your chat ID.

## Usage

### Local Execution

Run directly with Python:

```bash
python main.py
```

Or use the PowerShell script:

```bash
.\Run.ps1
```

### Docker Execution

Run a single instance:

```bash
docker run -d --env-file .env tevis-abh-ffm:latest
```

Run multiple instances with Docker Compose:

```bash
docker-compose up -d
```

The `docker-compose.yml` file includes example configurations for:

- Employee permit appointments (`pr-abh`)
- Document pickup appointments (`abholung-abh`)

Each instance can monitor a different appointment type simultaneously.

## Project Structure

```plaintext
tevis-abh-ffm/
├── main.py              # Main appointment checker application
├── get_users.py         # Telegram chat ID helper utility
├── requirements.txt     # Python dependencies
├── pyproject.toml       # Modern Python project configuration
├── Dockerfile           # Docker container configuration
├── docker-compose.yml   # Multi-instance Docker setup
├── Build.ps1            # Docker build script
├── Run.ps1              # Local run script
├── .env                 # Environment configuration (create this)
└── pyenv/               # Virtual environment (auto-generated)
```

## How It Works

1. **Initial Request**: Makes an HTTP request to the TEVIS system with your configured parameters
2. **Parse Response**: Extracts available appointment dates from the HTML response
3. **Date Comparison**: Compares available dates against your target date
4. **Notification**: If an appointment is found on or before your target date:
   - Sends Telegram message (if configured)
   - Shows desktop popup with browser link (if enabled)
5. **Loop**: Waits for `CHECK_DELAY` seconds and repeats

## Logging

The application provides detailed logging:

- `INFO`: Normal operation, appointment checks, notifications sent
- `ERROR`: Failed requests, parsing errors, retry attempts

Log format: `YYYY-MM-DD HH:MM:SS LEVEL module: message`

## Troubleshooting

### No appointments found

- Verify your `CNC_CODE` and `START_URL` are correct for your appointment type
- Check that the TEVIS website is accessible
- Try increasing `CHECK_DELAY` to avoid potential rate limiting

### Telegram notifications not working

- Verify `TELEGRAM_BOT_TOKEN` is correct
- Ensure you've started a chat with your bot
- Check `TELEGRAM_CHAT_IDS` are valid (use `get_users.py`)

### Desktop popup not showing

- Set `SHOW_POPUP=True` in `.env`
- Ensure tkinter is installed (included with most Python installations)

## Development

Install development dependencies:

```bash
pip install -e .[dev]
```

Run code formatting:

```bash
black .
```

Run type checking:

```bash
mypy main.py get_users.py
```

## License

MIT

## Disclaimer

This tool is for personal use only. Please use responsibly and in accordance with the TEVIS system's terms of service. Do not set `CHECK_DELAY` too low to avoid overwhelming the server.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

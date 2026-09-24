# Internet Speed Test Logger

This project is a lightweight Python utility that automatically runs internet speed tests on a schedule and saves the results to a log file. It uses the `speedtest-cli` library to measure download speed, upload speed, and ping, then records extra metadata such as the current date and time, approximate location, ISP, and selected test server.

By default, the logger runs once every 15 minutes between 08:00 and 17:00 and writes results to `speedlog.csv`. You can change the time window, update the interval, switch the output format, or repeat the schedule daily.

## What it does

The script:

- runs a speed test at regular intervals
- keeps measurements within a daily time window
- appends each result to a CSV or text log
- detects an approximate location from the public IP if available
- writes a human-readable table when the output file is not a CSV
- repeats the same schedule every day when `--daily` is enabled

## Install

```bash
uv add speedtest-cli
```

If your project dependencies are already pinned, you can also use:

```bash
uv sync
```

## Run

```bash
uv run main.py                                   # 08:00–17:00, every 15 min → speedlog.csv
uv run main.py --output speedlog.txt             # writes a fixed-width text table
uv run main.py --start 07:30 --end 18:00 --interval 10
uv run main.py --daily
```

## Options

```bash
uv run main.py --start HH:MM --end HH:MM --interval MINUTES --output PATH --daily
```

- `--start`: start of the testing window, default is `08:00`
- `--end`: end of the testing window, default is `17:00`
- `--interval`: minutes between each test, default is `15`
- `--output`: output log path; `.csv` files create CSV output, any other file creates a text table
- `--daily`: repeat the test window every day until you stop the script

## Scheduling behavior

The script schedules tests at fixed times inside the selected window. For example, with the default settings, it checks at 08:00, 08:15, 08:30, and so on until 17:00. If the current time has already passed a scheduled slot, it skips that time and continues with the next valid slot.

When `--daily` is used, the loop repeats the same schedule on the next day.

## Output examples

CSV output is stored in a spreadsheet-friendly format with columns like:

- Date
- Time
- Location
- Lat,Lon
- Download (Mbps)
- Upload (Mbps)
- Ping (ms)
- Server
- ISP
- Status

Text output uses a fixed-width table layout and is useful when you want a quick terminal-friendly log file.

## Notes

- The script writes a header only when a new log file is created.
- Geolocation is estimated from public-IP services (`ipinfo.io` with a fallback to `ip-api.com`) and may be unavailable in some environments.
- If a speed test fails, the log captures a short failure summary instead of stopping the program.
- Press `Ctrl+C` to stop the script at any time.

## License

This project is provided for personal and educational use. Add your preferred license text here if you plan to distribute or publish it publicly.

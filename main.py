"""
Internet speed test logger.

Runs a speed test every N minutes (default 15) within a daily time window
(default 08:00-17:00) and appends results to a CSV or TXT table.

Install:   pip install speedtest-cli
Examples:
    python main.py                                  # 08:00-17:00, every 15 min, speedlog.csv
    python main.py --start 07:30 --end 18:00 --output speedlog.txt
    python main.py --interval 10 --daily            # repeat the window every day
"""

# Standard CLI parser for command-line options and argument validation.
import argparse
# CSV writer used when the output file ends with .csv.
import csv
# JSON parsing for retrieving public IP and location metadata from web APIs.
import json
# Operating-system utilities used to check whether the output file exists or is empty.
import os
# Sleep helper used to wait until the next scheduled test time.
import time
# HTTP client used to fetch public IP information from external JSON endpoints.
import urllib.request
# Date/time helpers for scheduling and computing the current test time windows.
from datetime import datetime, timedelta

# Third-party library that performs the actual ISP speed measurement.
import speedtest

# Column names for the CSV rows written to the log file.
COLUMNS = ["Date", "Time", "Location", "Lat,Lon", "Download (Mbps)", "Upload (Mbps)",
           "Ping (ms)", "Server", "ISP", "Status"]
# Fixed-width field sizes used when formatting plain-text table output.
TXT_WIDTHS = [10, 8, 28, 17, 15, 13, 9, 30, 25, 30]


# Auto-detect approximate location from the public IP (no API key needed).
# Tries ipinfo.io first, then ip-api.com. Returns (location, "lat,lon").
def get_location():
    # Keep a list of possible public-IP sources in priority order.
    sources = [
        # ipinfo.io returns city, region, country, and a "loc" coordinate string.
        ("https://ipinfo.io/json",
         lambda d: (", ".join(x for x in (d.get("city"), d.get("region"), d.get("country")) if x),
                    d.get("loc", ""))),
        # ip-api.com returns city, regionName, and latitude/longitude values.
        ("http://ip-api.com/json",
         lambda d: (", ".join(x for x in (d.get("city"), d.get("regionName"), d.get("country")) if x),
                    f"{d['lat']},{d['lon']}" if "lat" in d else "")),
    ]
    # Try each source sequentially until one returns a usable location.
    for url, parse in sources:
        try:
            # Send a standard browser-like user agent to avoid basic blocks.
            req = urllib.request.Request(url, headers={"User-Agent": "speedtest-logger"})
            # Open the request and parse the JSON payload into Python objects.
            with urllib.request.urlopen(req, timeout=10) as resp:
                loc, coords = parse(json.load(resp))
                # Only accept a location when the source provided something meaningful.
                if loc:
                    return loc, coords
        except Exception:
            # If one provider fails, continue to the next provider without stopping.
            continue
    # Fall back to a safe placeholder when all geolocation sources fail.
    return "Unknown", ""


# Run one speed test and return a row of results.
def run_test():
    # Capture the wall-clock time at the exact moment the test starts.
    now = datetime.now()
    # Start the row with timestamp and geolocation metadata.
    row = [now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), *get_location()]
    try:
        # Create the speed test client and choose the closest server.
        st = speedtest.Speedtest(secure=True)
        st.get_best_server()
        # Download speed is measured in bytes per second; convert to megabits per second.
        down = st.download() / 1_000_000
        # Upload speed is measured in bytes per second; convert to megabits per second.
        up = st.upload(pre_allocate=False) / 1_000_000
        # Pull the raw result dictionary for server and ISP details.
        r = st.results.dict()
        # Format the selected server in a readable "Sponsor (Name)" string.
        server = f"{r['server']['sponsor']} ({r['server']['name']})"
        # Append the measured values in the same order as the CSV columns.
        row += [f"{down:.2f}", f"{up:.2f}", f"{r['ping']:.1f}",
                server, r["client"].get("isp", ""), "OK"]
    except Exception as e:  # no connection, server error, etc.
        # If the speedtest fails, store a short error summary instead of crashing the loop.
        row += ["", "", "", "", "", f"FAILED: {e}"[:60]]
    # Return the complete row so the caller can write it to the log file.
    return row


# Append a row to CSV or fixed-width TXT, writing a header if the file is new.
def write_row(path, row):
    # Determine whether this is a brand new file or an existing file with content.
    new_file = not os.path.exists(path) or os.path.getsize(path) == 0
    # CSV output writes one row at a time and includes a header only for a new file.
    if path.lower().endswith(".csv"):
        with open(path, "a", newline="", encoding="utf-8") as f:
            # CSV writer handles quoting and delimiter rules correctly.
            w = csv.writer(f)
            if new_file:
                # Add column names when we create the file for the first time.
                w.writerow(COLUMNS)
            # Append the current result row to the CSV file.
            w.writerow(row)
    else:
        # Create a local formatter for fixed-width text-table output.
        def fmt(cells):
            return " | ".join(str(c)[:w].ljust(w) for c, w in zip(cells, TXT_WIDTHS))
        with open(path, "a", encoding="utf-8") as f:
            if new_file:
                # Build a table header and separator when the text log is first created.
                header = fmt(COLUMNS)
                f.write(header + "\n" + "-" * len(header) + "\n")
            # Write the formatted row after the header section.
            f.write(fmt(row) + "\n")


# Convert a time string like "08:30" into a datetime with the supplied day.
def at(day, hhmm):
    # Split the HH:MM time into integer hours and minutes.
    h, m = map(int, hhmm.split(":"))
    # Return a datetime with the same date but a normalized hour and minute.
    return day.replace(hour=h, minute=m, second=0, microsecond=0)


# Wait until the next target time, if that time is still in the future.
def sleep_until(target):
    # Compute how many seconds remain before the scheduled slot.
    secs = (target - datetime.now()).total_seconds()
    if secs > 0:
        # Announce the next execution time to the console before sleeping.
        print(f"  next test at {target:%Y-%m-%d %H:%M}")
        # Pause the script until the scheduled time arrives.
        time.sleep(secs)


# Main program entry point that parses arguments and manages the scheduling loop.
def main():
    # Create a CLI parser with a short description that explains the scheduler's purpose.
    p = argparse.ArgumentParser(description="Log internet speed tests on a schedule.")
    # Start of the active test window, such as 08:00.
    p.add_argument("--start", default="08:00", help="window start, HH:MM (default 08:00)")
    # End of the active test window, such as 17:00.
    p.add_argument("--end", default="17:00", help="window end, HH:MM (default 17:00)")
    # Number of minutes between each scheduled speed check.
    p.add_argument("--interval", type=int, default=15, help="minutes between tests (default 15)")
    # Output path for the log file, either CSV or fixed-width text.
    p.add_argument("--output", default="speedlog.csv", help="log file, .csv or .txt")
    # Repeat the same window each calendar day instead of only once.
    p.add_argument("--daily", action="store_true", help="repeat the window every day")
    # Parse the command line and store the values in the args object.
    args = p.parse_args()

    # Display a concise summary of the current schedule so the user knows what will happen.
    print(f"Logging to {args.output}: every {args.interval} min, "
          f"{args.start}-{args.end}{' daily' if args.daily else ''}. Ctrl+C to stop.")
    # The time step used to move from one scheduled slot to the next.
    step = timedelta(minutes=args.interval)

    try:
        # Use the current date as the starting day for the schedule.
        day = datetime.now()
        # Keep looping until the user stops the program or the daily window ends.
        while True:
            # Compute the schedule start and end for the current day.
            start, end = at(day, args.start), at(day, args.end)
            # Only run if the current time has not passed the end of the configured window.
            if datetime.now() <= end:
                # Tests run at fixed slots: start, start+interval, ... up to end.
                slot = start
                # Skip any slots that are already behind the current time.
                while slot < datetime.now() - timedelta(seconds=30):
                    slot += step
                # Continue recording results until the window closes.
                while slot <= end:
                    # Wait until the next scheduled time before capturing a sample.
                    sleep_until(slot)
                    # Execute one speed test and collect the result row.
                    row = run_test()
                    # Write the result to the selected output file.
                    write_row(args.output, row)
                    # Print a compact status line summarizing the measurement.
                    print(f"[{row[1]}] {row[2]} | down={row[4]} up={row[5]} ping={row[6]} {row[-1]}")
                    # Move to the next scheduled slot.
                    slot += step
            # If the user did not select daily mode, stop after the first window finishes.
            if not args.daily:
                print("Time window finished.")
                return
            # For daily mode, advance to the next date and repeat the same window.
            day += timedelta(days=1)
    except KeyboardInterrupt:
        # User pressed Ctrl+C; stop gracefully and exit without a traceback.
        print("\nStopped.")

# Run the script only when this file is executed directly as a Python program.
if __name__ == "__main__":
    main()

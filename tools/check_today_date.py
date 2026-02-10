from datetime import date, datetime, timezone, timedelta

# Jakarta timezone (WIB = UTC+7)
WIB = timezone(timedelta(hours=7))


def check_today_date_tool():
    """
    Return today's date in '(MM/DD/YYYY)' format.
    """
    today_date = date.today().strftime("(%m/%d/%Y)")
    return today_date


def get_current_datetime_tool():
    """
    Return the current date and time in Jakarta timezone (WIB, UTC+7).
    Use this when the user asks for the current time, date, day, or any time-related question.
    """
    now = datetime.now(WIB)
    return {
        "date": now.strftime("%m/%d/%Y"),
        "time": now.strftime("%H:%M:%S"),
        "day": now.strftime("%A"),
        "timezone": "WIB (UTC+7)",
        "full": now.strftime("%A, %B %d, %Y %H:%M:%S WIB"),
    }

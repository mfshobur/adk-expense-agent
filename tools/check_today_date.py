from datetime import date

def check_today_date_tool():
    """
    Return today's date in '(MM/DD/YYYY)' format.
    """
    today_date = date.today().strftime("(%m/%d/%Y)")
    return today_date